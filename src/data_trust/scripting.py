"""Shared JSON output for the skill helper scripts."""

from __future__ import annotations

import json
import sys

import duckdb

from data_trust.errors import DataTrustError
from data_trust.plain import to_plain


def connect_readonly(path: str):
    if not path or path == ":memory:":
        raise DataTrustError("pass a database file; the helper opens it read-only")
    return duckdb.connect(path, read_only=True)


def emit(report: dict) -> int:
    json.dump(to_plain(report), sys.stdout, indent=2)
    sys.stdout.write("\n")
    failed = any(item.get("severity") == "fail" for item in report.get("findings", []))
    return 2 if failed else 0


def fail(exc: Exception) -> int:
    json.dump({"error": str(exc)}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1
