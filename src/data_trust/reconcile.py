"""Compare two calculations of one metric."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.idents import quote_ident, require_idents
from data_trust.sql_guard import assert_single_select


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _zero(value: Decimal | None) -> Decimal:
    return Decimal("0") if value is None else value


def _materialize(con, view: str, sql: str, budget: QueryBudget) -> list[str]:
    statement = assert_single_select(sql)
    quoted = quote_ident(view)
    budget.consume()
    con.execute(f"CREATE OR REPLACE TEMP VIEW {quoted} AS {statement}")
    budget.consume()
    cursor = con.execute(f"SELECT * FROM {quoted} LIMIT 0")
    return [item[0] for item in cursor.description]


def _require(present: list[str], needed: list[str], label: str) -> None:
    missing = [name for name in needed if name not in present]
    if missing:
        raise DataTrustError(f"{label} is missing columns: {', '.join(missing)}")


def _duplicate_keys(con, view: str, keys: list[str], budget: QueryBudget) -> int:
    packed = "struct_pack(" + ", ".join(f"{quote_ident(key)} := {quote_ident(key)}" for key in keys) + ")"
    budget.consume()
    row = con.execute(
        f"""
        SELECT count(*) - count(DISTINCT {packed})
        FROM {quote_ident(view)}
        """
    ).fetchone()
    return int(row[0])


def reconcile(
    con,
    left_sql: str,
    right_sql: str,
    metric: str,
    keys: list[str],
    time_column: str | None = None,
    segments: list[str] | None = None,
    record_key: str | None = None,
    tolerance_absolute: Decimal | None = None,
    tolerance_relative: Decimal | None = None,
    limit: int = 20,
    budget: QueryBudget | None = None,
) -> dict[str, Any]:
    """Full-outer-join two metric results and decompose the gap.

    The right-hand query is the reference for a relative tolerance.
    Duplicate keys on either side are summed before the comparison.
    """
    if limit < 1:
        raise DataTrustError("record limit must be at least 1")
    budget = budget or QueryBudget(20)
    quote_ident(metric)
    keys = require_idents(list(keys), "keys")
    segments = list(segments or [])
    for segment in segments:
        quote_ident(segment)
        if segment not in keys:
            raise DataTrustError(f"segment {segment} must be one of the keys")
    if time_column is not None:
        quote_ident(time_column)
        if time_column not in keys:
            raise DataTrustError("time_column must be one of the keys")
    if record_key is not None:
        quote_ident(record_key)
        if record_key not in keys:
            raise DataTrustError("record_key must be one of the keys")
    else:
        record_key = keys[0]

    left_columns = _materialize(con, "dts_left", left_sql, budget)
    right_columns = _materialize(con, "dts_right", right_sql, budget)
    _require(left_columns, [*keys, metric], "left query")
    _require(right_columns, [*keys, metric], "right query")

    assumptions = [
        "The right-hand query is the reference total for a relative tolerance.",
        "A difference is inside tolerance when it meets the absolute limit or the relative limit.",
        "Rows that match exactly are omitted from the breakdowns.",
    ]
    unknowns: list[str] = []
    left_dupes = _duplicate_keys(con, "dts_left", keys, budget)
    right_dupes = _duplicate_keys(con, "dts_right", keys, budget)
    if left_dupes or right_dupes:
        assumptions.append(
            f"Duplicate keys were summed before comparing "
            f"(left extra rows {left_dupes}, right extra rows {right_dupes})."
        )

    key_sql = ", ".join(quote_ident(key) for key in keys)
    budget.consume()
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW dts_left_agg AS
        SELECT {key_sql}, sum({quote_ident(metric)}) AS metric
        FROM dts_left
        GROUP BY {key_sql}
        """
    )
    budget.consume()
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW dts_right_agg AS
        SELECT {key_sql}, sum({quote_ident(metric)}) AS metric
        FROM dts_right
        GROUP BY {key_sql}
        """
    )
    coalesced = ", ".join(
        f"coalesce(l.{quote_ident(key)}, r.{quote_ident(key)}) AS {quote_ident(key)}" for key in keys
    )
    join_on = " AND ".join(f"l.{quote_ident(key)} = r.{quote_ident(key)}" for key in keys)
    budget.consume()
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW dts_joined AS
        SELECT {coalesced},
               l.metric AS left_metric,
               r.metric AS right_metric
        FROM dts_left_agg l
        FULL OUTER JOIN dts_right_agg r
            ON {join_on}
        """
    )
    budget.consume()
    totals = con.execute(
        """
        SELECT
            sum(left_metric) AS left_total,
            sum(right_metric) AS right_total,
            count(*) FILTER (WHERE left_metric IS NULL) AS right_only_keys,
            count(*) FILTER (WHERE right_metric IS NULL) AS left_only_keys,
            count(*) FILTER (
                WHERE left_metric IS NOT NULL AND right_metric IS NOT NULL AND left_metric <> right_metric
            ) AS value_mismatch_keys,
            count(*) FILTER (
                WHERE left_metric IS NOT NULL AND right_metric IS NOT NULL AND left_metric = right_metric
            ) AS equal_keys,
            count(*) FILTER (
                WHERE left_metric IS NULL AND right_metric IS NULL
            ) AS null_metric_keys
        FROM dts_joined
        """
    ).fetchone()
    left_total = _zero(_decimal(totals[0]))
    right_total = _zero(_decimal(totals[1]))
    difference = left_total - right_total
    absolute = abs(difference)
    relative = None if right_total == 0 else absolute / abs(right_total)
    if right_total == 0 and tolerance_relative is not None and difference != 0:
        unknowns.append("relative tolerance was not evaluated because the reference total is 0")

    within: bool | None
    if tolerance_absolute is None and tolerance_relative is None:
        within = None
        assumptions.append("No tolerance was supplied, so a non-zero difference is a mismatch.")
    else:
        within = difference == 0
        if tolerance_absolute is not None and absolute <= tolerance_absolute:
            within = True
        if tolerance_relative is not None and relative is not None and relative <= tolerance_relative:
            within = True

    def breakdown(column: str) -> list[dict[str, Any]]:
        budget.consume()
        rows = con.execute(
            f"""
            SELECT {quote_ident(column)} AS bucket,
                   sum(left_metric) AS left_total,
                   sum(right_metric) AS right_total,
                   coalesce(sum(left_metric), 0) - coalesce(sum(right_metric), 0) AS difference
            FROM dts_joined
            GROUP BY 1
            HAVING coalesce(sum(left_metric), 0) - coalesce(sum(right_metric), 0) <> 0
            ORDER BY abs(coalesce(sum(left_metric), 0) - coalesce(sum(right_metric), 0)) DESC, bucket
            """
        ).fetchall()
        return [
            {
                "value": row[0],
                "left_total": _zero(_decimal(row[1])),
                "right_total": _zero(_decimal(row[2])),
                "difference": _decimal(row[3]),
            }
            for row in rows
        ]

    by_time = breakdown(time_column) if time_column else []
    by_segment = {segment: breakdown(segment) for segment in segments}
    budget.consume()
    record_rows = con.execute(
        f"""
        SELECT {key_sql},
               left_metric,
               right_metric,
               coalesce(left_metric, 0) - coalesce(right_metric, 0) AS difference
        FROM dts_joined
        WHERE coalesce(left_metric, 0) - coalesce(right_metric, 0) <> 0
        ORDER BY abs(coalesce(left_metric, 0) - coalesce(right_metric, 0)) DESC, {key_sql}
        LIMIT {int(limit)}
        """
    ).fetchall()
    top_records = []
    for row in record_rows:
        key_values = {key: row[index] for index, key in enumerate(keys)}
        top_records.append(
            {
                "key": key_values,
                "record": key_values.get(record_key),
                "left_metric": _decimal(row[len(keys)]),
                "right_metric": _decimal(row[len(keys) + 1]),
                "difference": _decimal(row[len(keys) + 2]),
            }
        )

    findings: list[dict[str, Any]] = []
    evidence = {
        "metric": metric,
        "keys": keys,
        "left_total": left_total,
        "right_total": right_total,
        "difference": difference,
        "absolute_difference": absolute,
        "relative_difference": relative,
        "within_tolerance": within,
        "left_only_keys": int(totals[3]),
        "right_only_keys": int(totals[2]),
        "value_mismatch_keys": int(totals[4]),
        "equal_keys": int(totals[5]),
        "by_time": by_time,
        "by_segment": by_segment,
        "top_records": top_records,
        "tolerance_absolute": tolerance_absolute,
        "tolerance_relative": tolerance_relative,
    }
    if difference != 0 and within is not True:
        findings.append(
            {
                "code": "metric_mismatch",
                "severity": "fail",
                "message": (
                    f"Left total {left_total} minus right total {right_total} is {difference}."
                ),
                "evidence": {
                    "difference": difference,
                    "left_total": left_total,
                    "right_total": right_total,
                    "absolute_difference": absolute,
                    "relative_difference": relative,
                },
            }
        )
    return {
        "skill": "reconcile-metric-values",
        "evidence": evidence,
        "findings": findings,
        "assumptions": assumptions,
        "unknowns": unknowns,
        "query_budget": {"used": budget.used, "limit": budget.limit},
    }
