"""Check timezones, period ends, late rows, and fiscal years."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.scripting import connect_readonly, emit, fail
from data_trust.time_semantics import check_time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check time semantics for a timestamp column.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--timestamp-column", required=True)
    parser.add_argument("--stored-timezone")
    parser.add_argument("--business-timezone")
    parser.add_argument("--model-date-sql")
    parser.add_argument("--storage", default="utc_timestamp")
    parser.add_argument("--measure-sql")
    parser.add_argument("--id-column")
    parser.add_argument("--period-start")
    parser.add_argument("--period-end")
    parser.add_argument("--declared-boundary")
    parser.add_argument("--event-column")
    parser.add_argument("--loaded-column")
    parser.add_argument("--as-of")
    parser.add_argument("--max-delay-hours", type=int)
    parser.add_argument("--fiscal-start-month", type=int)
    parser.add_argument("--fiscal-date-sql")
    parser.add_argument("--budget", type=int, default=25)
    args = parser.parse_args(argv)
    try:
        report = check_time(
            connect_readonly(args.db),
            Path(args.source_file).read_text(),
            timestamp_column=args.timestamp_column,
            stored_timezone=args.stored_timezone,
            business_timezone=args.business_timezone,
            model_date_sql=args.model_date_sql,
            storage=args.storage,
            measure_sql=args.measure_sql,
            id_column=args.id_column,
            period_start=args.period_start,
            period_end=args.period_end,
            declared_boundary=args.declared_boundary,
            event_column=args.event_column,
            loaded_column=args.loaded_column,
            as_of=args.as_of,
            max_delay_hours=args.max_delay_hours,
            fiscal_start_month=args.fiscal_start_month,
            fiscal_date_sql=args.fiscal_date_sql,
            budget=QueryBudget(args.budget),
        )
        return emit(report)
    except (DataTrustError, OSError, duckdb.Error) as exc:
        return fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())
