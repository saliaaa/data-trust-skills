"""Compare two metric queries and break down the gap."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.reconcile import reconcile
from data_trust.scripting import connect_readonly, emit, fail


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile two calculations of one metric.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--left-file", required=True)
    parser.add_argument("--right-file", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--keys", required=True, help="Comma-separated key columns.")
    parser.add_argument("--time-column")
    parser.add_argument("--segments", help="Comma-separated segment columns. Each must also be a key.")
    parser.add_argument("--record-key")
    parser.add_argument("--tolerance-absolute")
    parser.add_argument("--tolerance-relative")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--budget", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        report = reconcile(
            connect_readonly(args.db),
            Path(args.left_file).read_text(),
            Path(args.right_file).read_text(),
            metric=args.metric,
            keys=_split(args.keys),
            time_column=args.time_column,
            segments=_split(args.segments),
            record_key=args.record_key,
            tolerance_absolute=Decimal(args.tolerance_absolute) if args.tolerance_absolute else None,
            tolerance_relative=Decimal(args.tolerance_relative) if args.tolerance_relative else None,
            limit=args.limit,
            budget=QueryBudget(args.budget),
        )
        return emit(report)
    except (DataTrustError, OSError, ArithmeticError, duckdb.Error) as exc:
        return fail(exc)


if __name__ == "__main__":
    raise SystemExit(main())
