"""Timezones, daylight saving, period ends, late rows, and fiscal years."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.idents import quote_ident, require_timezone
from data_trust.sql_guard import assert_single_select

_MAX_SCAN_HOURS = 20_000
_STORAGES = {"utc_timestamp", "local_timestamp"}


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _expression(sql: str, label: str) -> str:
    statement = assert_single_select(f"SELECT ({sql})")
    prefix = "SELECT ("
    if not (statement.startswith(prefix) and statement.endswith(")")):
        raise DataTrustError(f"{label} is not a scalar expression")
    return statement[len(prefix) : -1]


def check_time(
    con,
    source_sql: str,
    timestamp_column: str,
    stored_timezone: str | None = None,
    business_timezone: str | None = None,
    model_date_sql: str | None = None,
    storage: str = "utc_timestamp",
    measure_sql: str | None = None,
    id_column: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    declared_boundary: str | None = None,
    event_column: str | None = None,
    loaded_column: str | None = None,
    as_of: str | None = None,
    max_delay_hours: int | None = None,
    fiscal_start_month: int | None = None,
    fiscal_date_sql: str | None = None,
    budget: QueryBudget | None = None,
) -> dict[str, Any]:
    """Run the time checks that were actually requested.

    A timezone comparison needs the stored zone, the business zone, and the
    date expression the model uses. Boundary, lateness, and fiscal checks are
    independent and run only when their inputs are present.
    """
    budget = budget or QueryBudget(25)
    if storage not in _STORAGES:
        raise DataTrustError("storage must be utc_timestamp or local_timestamp")
    quote_ident(timestamp_column)
    if id_column is not None:
        quote_ident(id_column)
    statement = assert_single_select(source_sql)
    budget.consume()
    con.execute(f'CREATE OR REPLACE TEMP VIEW dts_time_source AS {statement}')
    budget.consume()
    columns = [item[0] for item in con.execute("SELECT * FROM dts_time_source LIMIT 0").description]
    if timestamp_column not in columns:
        raise DataTrustError(f"source is missing timestamp column {timestamp_column}")
    if id_column is not None and id_column not in columns:
        raise DataTrustError(f"source is missing id column {id_column}")

    timezone_requested = any(value is not None for value in (stored_timezone, business_timezone, model_date_sql))
    boundary_requested = period_start is not None or period_end is not None
    late_requested = any(value is not None for value in (event_column, loaded_column, as_of, max_delay_hours))
    fiscal_requested = fiscal_start_month is not None
    if not any((timezone_requested, boundary_requested, late_requested, fiscal_requested)):
        raise DataTrustError("no time check was requested")

    findings: list[dict[str, Any]] = []
    unknowns: list[str] = []
    evidence: dict[str, Any] = {"storage": storage}
    assumptions = [
        "Timezone conversion uses DuckDB AT TIME ZONE on this connection.",
        "utc_timestamp means a naive timestamp whose clock is the stored timezone, usually UTC.",
        "local_timestamp means a naive civil time in the business timezone.",
        "A half-open period is [start, end). A closed period is [start, end].",
        "The fiscal year label is the calendar year of the period start.",
    ]

    if timezone_requested:
        if not (stored_timezone and business_timezone and model_date_sql):
            raise DataTrustError("timezone check needs stored_timezone, business_timezone, and model_date_sql")
        stored_timezone = require_timezone(stored_timezone)
        business_timezone = require_timezone(business_timezone)
        if storage == "local_timestamp" and stored_timezone != business_timezone:
            raise DataTrustError("local_timestamp storage requires stored_timezone to equal business_timezone")
        model_expr = _expression(model_date_sql, "model_date_sql")
        measure_expr = _expression(measure_sql, "measure_sql") if measure_sql else "NULL"
        quoted_ts = quote_ident(timestamp_column)
        if storage == "utc_timestamp":
            business_expr = (
                f"(({quoted_ts} AT TIME ZONE '{stored_timezone}') AT TIME ZONE '{business_timezone}')"
            )
        else:
            business_expr = quoted_ts
        id_expr = quote_ident(id_column) if id_column else "NULL"
        budget.consume()
        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW dts_time_classified AS
            SELECT
                {id_expr} AS row_id,
                {quoted_ts} AS ts,
                CAST(({model_expr}) AS DATE) AS model_date,
                CAST({business_expr} AS DATE) AS business_date,
                ({measure_expr}) AS measure_value
            FROM dts_time_source
            """
        )
        budget.consume()
        summary = con.execute(
            """
            SELECT
                count(*) AS rows,
                count(*) FILTER (WHERE model_date <> business_date) AS shifted_rows,
                sum(measure_value) FILTER (WHERE model_date <> business_date) AS shifted_measure,
                count(*) FILTER (WHERE measure_value IS NULL) AS null_measure_rows
            FROM dts_time_classified
            """
        ).fetchone()
        shifted_rows = int(summary[1])
        shifted_measure = _decimal(summary[2]) if measure_sql else None
        evidence.update(
            {
                "stored_timezone": stored_timezone,
                "business_timezone": business_timezone,
                "rows": int(summary[0]),
                "shifted_rows": shifted_rows,
                "shifted_measure": shifted_measure,
            }
        )
        if measure_sql is None:
            unknowns.append("no measure was supplied, so the shifted amount is unknown")
        elif int(summary[3]) > 0:
            unknowns.append(f"{int(summary[3])} rows have a null measure")
        example = None
        if shifted_rows > 0:
            budget.consume()
            example_row = con.execute(
                """
                SELECT row_id, ts, model_date, business_date, measure_value
                FROM dts_time_classified
                WHERE model_date <> business_date
                ORDER BY measure_value DESC NULLS LAST, ts
                LIMIT 1
                """
            ).fetchone()
            example = {
                "id": example_row[0],
                "timestamp": example_row[1],
                "model_date": example_row[2],
                "business_date": example_row[3],
                "measure": _decimal(example_row[4]) if example_row[4] is not None else None,
            }
            evidence["shift_example"] = example
            findings.append(
                {
                    "code": "date_shift",
                    "severity": "fail",
                    "message": (
                        f"{shifted_rows} rows have a model date that differs from the "
                        f"{business_timezone} business date."
                    ),
                    "evidence": {
                        "shifted_rows": shifted_rows,
                        "shifted_measure": shifted_measure,
                        "example": example,
                    },
                }
            )
        _daylight(con, stored_timezone, business_timezone, storage, findings, unknowns, evidence, budget)

    if boundary_requested:
        if period_start is None or period_end is None:
            raise DataTrustError("boundary check needs both period_start and period_end")
        if declared_boundary not in {None, "[start, end)", "[start, end]"}:
            raise DataTrustError("declared_boundary must be '[start, end)' or '[start, end]'")
        quoted_ts = quote_ident(timestamp_column)
        budget.consume()
        row = con.execute(
            f"""
            SELECT
                count(*) FILTER (WHERE {quoted_ts} = CAST(? AS TIMESTAMP)) AS on_endpoint,
                count(*) FILTER (
                    WHERE {quoted_ts} >= CAST(? AS TIMESTAMP) AND {quoted_ts} < CAST(? AS TIMESTAMP)
                ) AS half_open_includes,
                count(*) FILTER (
                    WHERE {quoted_ts} >= CAST(? AS TIMESTAMP) AND {quoted_ts} <= CAST(? AS TIMESTAMP)
                ) AS closed_includes
            FROM dts_time_source
            """,
            [period_end, period_start, period_end, period_start, period_end],
        ).fetchone()
        on_endpoint = int(row[0])
        half_open = int(row[1])
        closed = int(row[2])
        evidence.update(
            {
                "on_endpoint": on_endpoint,
                "half_open_includes": half_open,
                "closed_includes": closed,
                "declared_boundary": declared_boundary,
            }
        )
        if on_endpoint > 0:
            if declared_boundary == "[start, end)":
                included = "excludes"
            elif declared_boundary == "[start, end]":
                included = "includes"
            else:
                included = "does not say whether it includes"
            findings.append(
                {
                    "code": "boundary_endpoint",
                    "severity": "fail",
                    "message": (
                        f"{on_endpoint} rows sit on the period end. "
                        f"[start, end) excludes them ({half_open} rows inside); "
                        f"[start, end] includes them ({closed} rows inside). "
                        f"The declared boundary {included} those rows."
                    ),
                    "evidence": {
                        "on_endpoint": on_endpoint,
                        "half_open_includes": half_open,
                        "closed_includes": closed,
                        "declared_boundary": declared_boundary,
                    },
                }
            )

    if late_requested:
        if None in (event_column, loaded_column, as_of, max_delay_hours):
            raise DataTrustError("late-arrival check needs event_column, loaded_column, as_of, and max_delay_hours")
        quote_ident(event_column)
        quote_ident(loaded_column)
        if event_column not in columns or loaded_column not in columns:
            raise DataTrustError("late-arrival columns are not in the source")
        if int(max_delay_hours) < 0:
            raise DataTrustError("max_delay_hours cannot be negative")
        budget.consume()
        row = con.execute(
            f"""
            SELECT
                count(*) FILTER (
                    WHERE {quote_ident(event_column)} <= CAST(? AS TIMESTAMP)
                      AND {quote_ident(loaded_column)} > CAST(? AS TIMESTAMP)
                ) AS missing_from_snapshot,
                count(*) FILTER (
                    WHERE epoch({quote_ident(loaded_column)}) - epoch({quote_ident(event_column)})
                         > ?
                ) AS beyond_delay
            FROM dts_time_source
            """,
            [as_of, as_of, int(max_delay_hours) * 3600],
        ).fetchone()
        missing = int(row[0])
        beyond = int(row[1])
        evidence.update(
            {
                "missing_from_snapshot": missing,
                "beyond_delay": beyond,
                "as_of": as_of,
                "max_delay_hours": int(max_delay_hours),
            }
        )
        if missing or beyond:
            findings.append(
                {
                    "code": "late_arrival",
                    "severity": "fail",
                    "message": (
                        f"{missing} events had already happened by {as_of} but were loaded later. "
                        f"{beyond} events arrived more than {max_delay_hours} hours after the event."
                    ),
                    "evidence": {
                        "missing_from_snapshot": missing,
                        "beyond_delay": beyond,
                    },
                }
            )

    if fiscal_requested:
        if not isinstance(fiscal_start_month, int) or not 1 <= fiscal_start_month <= 12:
            raise DataTrustError("fiscal_start_month must be an integer from 1 to 12")
        date_expr = _expression(fiscal_date_sql, "fiscal_date_sql") if fiscal_date_sql else quote_ident(timestamp_column)
        budget.consume()
        row = con.execute(
            f"""
            WITH dated AS (
                SELECT CAST(({date_expr}) AS DATE) AS fiscal_date
                FROM dts_time_source
            )
            SELECT
                count(*) AS rows,
                count(*) FILTER (
                    WHERE (
                        CASE
                            WHEN month(fiscal_date) >= ? THEN year(fiscal_date)
                            ELSE year(fiscal_date) - 1
                        END
                    ) <> year(fiscal_date)
                ) AS mismatches
            FROM dated
            """,
            [fiscal_start_month],
        ).fetchone()
        mismatches = int(row[1])
        evidence.update({"fiscal_start_month": fiscal_start_month, "fiscal_mismatches": mismatches, "fiscal_rows": int(row[0])})
        if fiscal_start_month == 1:
            assumptions.append("Fiscal start month is 1, so the fiscal year label equals the calendar year.")
        elif mismatches > 0:
            findings.append(
                {
                    "code": "fiscal_mismatch",
                    "severity": "fail",
                    "message": (
                        f"{mismatches} rows fall in a different fiscal year than their calendar year "
                        f"when the fiscal year starts in month {fiscal_start_month}."
                    ),
                    "evidence": {"fiscal_mismatches": mismatches, "fiscal_start_month": fiscal_start_month},
                }
            )

    return {
        "skill": "test-time-semantics",
        "evidence": evidence,
        "findings": findings,
        "assumptions": assumptions,
        "unknowns": unknowns,
        "query_budget": {"used": budget.used, "limit": budget.limit},
    }


def _daylight(con, stored_timezone, business_timezone, storage, findings, unknowns, evidence, budget: QueryBudget) -> None:
    budget.consume()
    bounds = con.execute("SELECT min(ts), max(ts), count(*) FROM dts_time_classified").fetchone()
    if bounds[2] == 0 or bounds[0] is None:
        unknowns.append("the source has no timestamps, so daylight-saving transitions were not scanned")
        evidence["transitions"] = []
        return
    start = bounds[0] - timedelta(days=2)
    finish = bounds[1] + timedelta(days=2)
    hours = int((finish - start).total_seconds() // 3600) + 2
    if hours > _MAX_SCAN_HOURS:
        unknowns.append(
            f"the timestamp window is {hours} hours, above the { _MAX_SCAN_HOURS } hour daylight-saving scan limit"
        )
        evidence["transitions"] = []
        return
    zone = stored_timezone if storage == "utc_timestamp" else "UTC"
    budget.consume()
    transitions = con.execute(
        f"""
        WITH hours AS (
            SELECT CAST(? AS TIMESTAMP) + n * INTERVAL 1 HOUR AS ts
            FROM range(0, ?) r(n)
        ),
        local AS (
            SELECT
                ts,
                (ts AT TIME ZONE '{zone}') AT TIME ZONE '{business_timezone}' AS local_ts
            FROM hours
        )
        SELECT
            ts,
            local_ts,
            date_diff('hour', lag(local_ts) OVER (ORDER BY ts), local_ts) AS step,
            lag(ts) OVER (ORDER BY ts) AS prev_ts,
            lag(local_ts) OVER (ORDER BY ts) AS prev_local
        FROM local
        QUALIFY step IS NOT NULL AND step <> 1
        ORDER BY ts
        """,
        [start, hours],
    ).fetchall()
    reports = []
    overlap_rows = 0
    gap_rows = 0
    for ts, local_ts, step, prev_ts, prev_local in transitions:
        step = int(step)
        if step == 0 and prev_ts is not None and prev_local is not None:
            local_end = prev_local + timedelta(hours=1)
            count, amount = _count_local_window(con, storage, stored_timezone, business_timezone, prev_local, local_end, budget)
            overlap_rows += count
            reports.append(
                {
                    "kind": "overlap",
                    "utc_start": prev_ts,
                    "utc_end": ts + timedelta(hours=1),
                    "local_start": prev_local,
                    "local_end": local_end,
                    "rows": count,
                    "measure": amount,
                }
            )
        elif step > 1 and prev_local is not None:
            missing_start = prev_local + timedelta(hours=1)
            count, amount = _count_local_window(
                con, storage, stored_timezone, business_timezone, missing_start, local_ts, budget
            )
            gap_rows += count
            reports.append(
                {
                    "kind": "gap",
                    "local_start": missing_start,
                    "local_end": local_ts,
                    "rows": count,
                    "measure": amount,
                }
            )
    evidence["transitions"] = reports
    evidence["overlap_rows"] = overlap_rows
    evidence["gap_rows"] = gap_rows
    if overlap_rows > 0:
        findings.append(
            {
                "code": "dst_overlap",
                "severity": "info",
                "message": (
                    f"{overlap_rows} rows fall in a repeated local hour. "
                    "The offset, not the civil clock, decides which instant they are."
                ),
                "evidence": {"overlap_rows": overlap_rows},
            }
        )
    if gap_rows > 0:
        findings.append(
            {
                "code": "dst_gap",
                "severity": "fail",
                "message": f"{gap_rows} stored timestamps fall in a local hour that does not exist.",
                "evidence": {"gap_rows": gap_rows},
            }
        )


def _count_local_window(con, storage, stored_timezone, business_timezone, start, end, budget: QueryBudget):
    quoted = '"ts"'
    if storage == "utc_timestamp":
        local_expr = f"(({quoted} AT TIME ZONE '{stored_timezone}') AT TIME ZONE '{business_timezone}')"
    else:
        local_expr = quoted
    budget.consume()
    row = con.execute(
        f"""
        SELECT count(*) AS rows, sum(measure_value) AS measure
        FROM dts_time_classified
        WHERE {local_expr} >= CAST(? AS TIMESTAMP)
          AND {local_expr} < CAST(? AS TIMESTAMP)
        """,
        [start, end],
    ).fetchone()
    return int(row[0]), _decimal(row[1])
