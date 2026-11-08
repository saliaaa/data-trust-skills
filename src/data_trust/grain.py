"""Candidate keys, join fanout, dropped rows, and mixed grain."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.idents import quote_ident, require_idents
from data_trust.sql_guard import assert_single_select

_RELATIONSHIPS = {"base", "one_to_one", "many_to_one", "one_to_many"}


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _view(name: str) -> str:
    quote_ident(name)
    return quote_ident(f"dts_{name}")


def _columns(con, view_sql_name: str, budget: QueryBudget) -> list[str]:
    budget.consume()
    cursor = con.execute(f"SELECT * FROM {view_sql_name} LIMIT 0")
    return [item[0] for item in cursor.description]


def _require_columns(present: list[str], needed: list[str], label: str) -> None:
    missing = [name for name in needed if name not in present]
    if missing:
        raise DataTrustError(f"{label} is missing columns: {', '.join(missing)}")


def _pack(columns: list[str]) -> str:
    fields = ", ".join(f"{quote_ident(column)} := {quote_ident(column)}" for column in columns)
    return f"struct_pack({fields})"


def _key_stats(con, view_sql_name: str, columns: list[str], budget: QueryBudget) -> dict[str, Any]:
    packed = _pack(columns)
    null_predicate = " OR ".join(f"{quote_ident(column)} IS NULL" for column in columns)
    not_null = " AND ".join(f"{quote_ident(column)} IS NOT NULL" for column in columns)
    budget.consume()
    row = con.execute(
        f"""
        WITH keyed AS (
            SELECT {packed} AS grain_key,
                   CASE WHEN {null_predicate} THEN 1 ELSE 0 END AS key_is_null
            FROM {view_sql_name}
        ),
        groups AS (
            SELECT grain_key, count(*) AS copies
            FROM keyed
            WHERE key_is_null = 0
            GROUP BY 1
        )
        SELECT
            (SELECT count(*) FROM keyed) AS row_count,
            (SELECT coalesce(sum(key_is_null), 0) FROM keyed) AS null_key_rows,
            (SELECT count(*) FROM groups) AS distinct_keys,
            (SELECT count(*) FROM groups WHERE copies > 1) AS duplicate_keys,
            (SELECT coalesce(sum(copies - 1), 0) FROM groups) AS extra_rows,
            (SELECT coalesce(max(copies), 0) FROM groups) AS max_multiplicity
        """
    ).fetchone()
    stats = {
        "rows": int(row[0]),
        "null_key_rows": int(row[1]),
        "distinct_keys": int(row[2]),
        "duplicate_keys": int(row[3]),
        "extra_rows": int(row[4]),
        "max_multiplicity": int(row[5]),
        "example": None,
    }
    if stats["extra_rows"] > 0:
        budget.consume()
        example = con.execute(
            f"""
            SELECT {packed} AS grain_key, count(*) AS copies
            FROM {view_sql_name}
            WHERE {not_null}
            GROUP BY 1
            HAVING count(*) > 1
            ORDER BY copies DESC, grain_key
            LIMIT 1
            """
        ).fetchone()
        stats["example"] = {"key": dict(example[0]), "copies": int(example[1])}
    return stats


def _measure(con, view_sql_name: str, columns: list[str], measure: str, budget: QueryBudget) -> dict[str, Any]:
    quote_ident(measure)
    selected = ", ".join(quote_ident(column) for column in columns)
    budget.consume()
    row = con.execute(
        f"""
        WITH base AS (
            SELECT {selected}, {quote_ident(measure)} AS measure_value
            FROM {view_sql_name}
        ),
        per_key AS (
            SELECT
                min(measure_value) AS one_value,
                min(measure_value) = max(measure_value) AS stable
            FROM base
            GROUP BY {selected}
        )
        SELECT
            (SELECT sum(measure_value) FROM base) AS multiplied_sum,
            (SELECT sum(one_value) FROM per_key) AS deduped_sum,
            (SELECT coalesce(bool_and(stable), TRUE) FROM per_key) AS stable
        """
    ).fetchone()
    multiplied = _decimal(row[0])
    deduped = _decimal(row[1])
    return {
        "multiplied_sum": multiplied,
        "deduped_sum": deduped,
        "extra_revenue": multiplied - deduped,
        "stable": bool(row[2]),
    }


def _dropped(con, parent_view: str, child_view: str, columns: list[str], budget: QueryBudget) -> dict[str, Any]:
    selected = ", ".join(quote_ident(column) for column in columns)
    not_null = " AND ".join(f"{quote_ident(column)} IS NOT NULL" for column in columns)
    budget.consume()
    dropped = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT DISTINCT {selected} FROM {parent_view} WHERE {not_null}
            EXCEPT
            SELECT DISTINCT {selected} FROM {child_view} WHERE {not_null}
        )
        """
    ).fetchone()[0]
    example = None
    if int(dropped) > 0:
        budget.consume()
        row = con.execute(
            f"""
            SELECT * FROM (
                SELECT DISTINCT {selected} FROM {parent_view} WHERE {not_null}
                EXCEPT
                SELECT DISTINCT {selected} FROM {child_view} WHERE {not_null}
            )
            LIMIT 1
            """
        ).fetchone()
        example = {column: row[index] for index, column in enumerate(columns)}
    return {"dropped_keys": int(dropped), "example": example}


def analyze_join_path(con, steps: list[dict[str, Any]], budget: QueryBudget | None = None) -> dict[str, Any]:
    """Walk join steps and report grain failures.

    Each step is a SELECT at the grain that should be unique after that join.
    ``relationship`` is ``base`` for the first step. Later steps are
    ``one_to_one``, ``many_to_one``, or ``one_to_many``. A ``one_to_many``
    step may add rows. Any repeated grain key is fanout, whatever the label
    says. ``measure`` is optional and must already be a column of the step.
    """
    if not steps:
        raise DataTrustError("join path needs at least one step")
    budget = budget or QueryBudget(30)
    findings: list[dict[str, Any]] = []
    unknowns: list[str] = []
    reports: list[dict[str, Any]] = []
    seen: dict[str, str] = {}

    for index, step in enumerate(steps):
        name = step.get("name")
        if not isinstance(name, str):
            raise DataTrustError("each step needs a name")
        quote_ident(name)
        if name in seen:
            raise DataTrustError(f"duplicate step name: {name}")
        grain = require_idents(list(step.get("grain") or []), f"step {name} grain")
        relationship = step.get("relationship", "base" if index == 0 else None)
        if relationship not in _RELATIONSHIPS:
            raise DataTrustError(f"step {name} has an unsupported relationship")
        if index == 0 and relationship != "base":
            raise DataTrustError("the first step relationship must be base")
        if index > 0 and relationship == "base":
            raise DataTrustError(f"step {name} cannot use relationship base")
        parent_name = step.get("parent")
        parent_key = list(step.get("parent_key") or [])
        if index > 0:
            if parent_name not in seen:
                raise DataTrustError(f"step {name} parent is not a previous step")
            require_idents(parent_key, f"step {name} parent_key")
        statement = assert_single_select(str(step.get("sql") or ""))
        view_sql_name = _view(name)
        budget.consume()
        con.execute(f"CREATE OR REPLACE TEMP VIEW {view_sql_name} AS {statement}")
        present = _columns(con, view_sql_name, budget)
        _require_columns(present, grain, f"step {name}")
        if parent_key:
            _require_columns(present, parent_key, f"step {name}")
        measure = step.get("measure")
        if measure is not None:
            quote_ident(str(measure))
            _require_columns(present, [str(measure)], f"step {name}")

        stats = _key_stats(con, view_sql_name, grain, budget)
        report: dict[str, Any] = {
            "name": name,
            "relationship": relationship,
            "grain": grain,
            "rows": stats["rows"],
            "key": stats,
        }
        if stats["null_key_rows"] > 0:
            findings.append(
                {
                    "code": "key_nulls",
                    "severity": "fail",
                    "message": (
                        f"Step {name} has {stats['null_key_rows']} rows with a null grain key "
                        f"({', '.join(grain)})."
                    ),
                    "evidence": {"step": name, "null_key_rows": stats["null_key_rows"], "grain": grain},
                }
            )
            unknowns.append(f"step {name} has null grain keys, so uniqueness does not cover those rows")
        if stats["duplicate_keys"] > 0:
            example = stats["example"] or {}
            findings.append(
                {
                    "code": "key_not_unique",
                    "severity": "fail",
                    "message": (
                        f"Step {name} grain ({', '.join(grain)}) is not unique: "
                        f"{stats['duplicate_keys']} keys repeat, {stats['extra_rows']} extra rows, "
                        f"max copies {stats['max_multiplicity']}."
                    ),
                    "evidence": {
                        "step": name,
                        "extra_rows": stats["extra_rows"],
                        "duplicate_keys": stats["duplicate_keys"],
                        "max_multiplicity": stats["max_multiplicity"],
                        "example": example,
                    },
                }
            )
            if index > 0:
                findings.append(
                    {
                        "code": "fanout",
                        "severity": "fail",
                        "message": (
                            f"Join step {name} repeats grain ({', '.join(grain)}). "
                            f"Extra rows: {stats['extra_rows']}."
                        ),
                        "evidence": {
                            "step": name,
                            "extra_rows": stats["extra_rows"],
                            "max_multiplicity": stats["max_multiplicity"],
                            "rows": stats["rows"],
                            "example": example,
                            "relationship": relationship,
                        },
                    }
                )

        if index > 0 and relationship != "one_to_many":
            parent_rows = next(item["rows"] for item in reports if item["name"] == parent_name)
            if stats["rows"] > parent_rows and stats["duplicate_keys"] == 0:
                findings.append(
                    {
                        "code": "fanout",
                        "severity": "fail",
                        "message": (
                            f"Step {name} was labeled {relationship} but grew from "
                            f"{parent_rows} rows to {stats['rows']}."
                        ),
                        "evidence": {
                            "step": name,
                            "parent_rows": parent_rows,
                            "rows": stats["rows"],
                            "extra_rows": stats["rows"] - parent_rows,
                            "relationship": relationship,
                        },
                    }
                )
            report["parent_rows"] = parent_rows

        if parent_key:
            parent_view = seen[parent_name]
            _require_columns(_columns(con, parent_view, budget), parent_key, f"parent {parent_name}")
            dropped = _dropped(con, parent_view, view_sql_name, parent_key, budget)
            report["dropped"] = dropped
            if dropped["dropped_keys"] > 0:
                findings.append(
                    {
                        "code": "dropped_rows",
                        "severity": "fail",
                        "message": (
                            f"Step {name} drops {dropped['dropped_keys']} parent keys "
                            f"({', '.join(parent_key)}) from {parent_name}."
                        ),
                        "evidence": {
                            "step": name,
                            "parent": parent_name,
                            "dropped_keys": dropped["dropped_keys"],
                            "example": dropped["example"],
                            "parent_key": parent_key,
                        },
                    }
                )

        if measure is not None:
            measured = _measure(con, view_sql_name, grain, str(measure), budget)
            report["measure"] = measured
            if not measured["stable"]:
                unknowns.append(
                    f"step {name} measure {measure} is not constant across copies of a grain key"
                )
            if measured["extra_revenue"] != 0:
                fanout_evidence = {
                    "step": name,
                    "measure": measure,
                    "extra_revenue": measured["extra_revenue"],
                    "multiplied_sum": measured["multiplied_sum"],
                    "deduped_sum": measured["deduped_sum"],
                    "extra_rows": stats["extra_rows"],
                }
                findings.append(
                    {
                        "code": "measure_inflated_by_fanout",
                        "severity": "fail",
                        "message": (
                            f"Sum of {measure} on step {name} is {measured['multiplied_sum']}, "
                            f"which is {measured['extra_revenue']} above one copy per grain key."
                        ),
                        "evidence": fanout_evidence,
                    }
                )
                for finding in findings:
                    if finding["code"] == "fanout" and finding["evidence"].get("step") == name:
                        finding["evidence"]["extra_revenue"] = measured["extra_revenue"]

        reports.append(report)
        seen[name] = view_sql_name

    return {
        "skill": "verify-grain-and-joins",
        "evidence": {"steps": reports},
        "findings": findings,
        "assumptions": [
            "The declared grain is the column set that must be unique at that step, before a later GROUP BY.",
            "one_to_many may add rows. A repeated grain key is fanout even when the step is labeled one_to_many.",
            "Dropped rows are non-null parent keys that do not appear in the child step.",
            "When a measure is named, extra revenue is the step sum minus one copy of that measure per grain key.",
        ],
        "unknowns": unknowns,
        "query_budget": {"used": budget.used, "limit": budget.limit},
    }


def check_mixed_grain(
    con,
    source_sql: str,
    detail_column: str,
    fine_key: list[str],
    coarse_key: list[str],
    budget: QueryBudget | None = None,
) -> dict[str, Any]:
    """Flag a relation that stacks a detail grain and a header grain.

    Detail rows are those where ``detail_column`` is not null. Header rows are
    those where it is null. Both populations must be non-empty.
    """
    budget = budget or QueryBudget(30)
    quote_ident(detail_column)
    require_idents(fine_key, "fine_key")
    require_idents(coarse_key, "coarse_key")
    statement = assert_single_select(source_sql)
    view_sql_name = _view("mixed")
    budget.consume()
    con.execute(f"CREATE OR REPLACE TEMP VIEW {view_sql_name} AS {statement}")
    present = _columns(con, view_sql_name, budget)
    _require_columns(present, [detail_column, *fine_key, *coarse_key], "mixed-grain source")
    detail = f"{quote_ident(detail_column)} IS NOT NULL"
    header = f"{quote_ident(detail_column)} IS NULL"

    def population_stats(predicate: str, key: list[str]) -> dict[str, int]:
        packed = _pack(key)
        not_null = " AND ".join(f"{quote_ident(column)} IS NOT NULL" for column in key)
        budget.consume()
        row = con.execute(
            f"""
            WITH subset AS (
                SELECT * FROM {view_sql_name} WHERE {predicate}
            ),
            groups AS (
                SELECT {packed} AS grain_key, count(*) AS copies
                FROM subset
                WHERE {not_null}
                GROUP BY 1
            )
            SELECT
                (SELECT count(*) FROM subset) AS rows,
                (SELECT coalesce(sum(copies - 1), 0) FROM groups) AS extra_rows,
                (SELECT count(*) FROM subset WHERE NOT ({not_null})) AS null_key_rows
            """
        ).fetchone()
        return {"rows": int(row[0]), "extra_rows": int(row[1]), "null_key_rows": int(row[2])}

    detail_stats = population_stats(detail, fine_key)
    header_stats = population_stats(header, coarse_key)
    findings: list[dict[str, Any]] = []
    evidence = {
        "detail_column": detail_column,
        "fine_key": fine_key,
        "coarse_key": coarse_key,
        "detail_rows": detail_stats["rows"],
        "header_rows": header_stats["rows"],
        "detail_extra_rows": detail_stats["extra_rows"],
        "header_extra_rows": header_stats["extra_rows"],
    }
    if detail_stats["rows"] > 0 and header_stats["rows"] > 0:
        findings.append(
            {
                "code": "mixed_grain",
                "severity": "fail",
                "message": (
                    f"The relation mixes grains: {detail_stats['rows']} rows have "
                    f"{detail_column} populated and {header_stats['rows']} rows leave it null."
                ),
                "evidence": evidence,
            }
        )
    return {
        "skill": "verify-grain-and-joins",
        "evidence": evidence,
        "findings": findings,
        "assumptions": [
            "Detail rows are the rows where the detail column is not null.",
            "Header rows are the rows where the detail column is null.",
            "A uniform table, where one of those populations is empty, is not mixed grain.",
        ],
        "unknowns": [],
        "query_budget": {"used": budget.used, "limit": budget.limit},
    }
