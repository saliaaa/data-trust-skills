"""Read-only grain, fanout, dropped-row, and mixed-grain check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.grain import analyze_join_path, check_mixed_grain
from data_trust.scripting import connect_readonly, emit, fail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check grain, fanout, dropped rows, and mixed grain.")
    parser.add_argument("--db", required=True, help="DuckDB file. Opened read-only.")
    parser.add_argument("--steps", help="JSON file of join steps.")
    parser.add_argument("--mixed", help="JSON file with source_sql, detail_column, fine_key, and coarse_key.")
    parser.add_argument("--budget", type=int, default=30)
    args = parser.parse_args(argv)
    if not args.steps and not args.mixed:
        return fail(DataTrustError("pass --steps, --mixed, or both"))
    try:
        con = connect_readonly(args.db)
        budget = QueryBudget(args.budget)
        report = None
        if args.steps:
            steps = json.loads(Path(args.steps).read_text())
            report = analyze_join_path(con, steps, budget)
        if args.mixed:
            mixed = json.loads(Path(args.mixed).read_text())
            mixed_report = check_mixed_grain(
                con,
                mixed["source_sql"],
                mixed["detail_column"],
                mixed["fine_key"],
                mixed["coarse_key"],
                budget,
            )
            report = _merge(report, mixed_report)
        assert report is not None
        return emit(report)
    except (DataTrustError, OSError, json.JSONDecodeError, KeyError, duckdb.Error) as exc:
        return fail(exc)


def _merge(base: dict | None, extra: dict) -> dict:
    if base is None:
        return extra
    base["findings"].extend(extra["findings"])
    base["unknowns"].extend(extra["unknowns"])
    base["evidence"]["mixed_grain"] = extra["evidence"]
    base["query_budget"] = extra["query_budget"]
    return base


if __name__ == "__main__":
    raise SystemExit(main())
