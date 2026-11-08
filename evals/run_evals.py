"""Run the helper scripts against broken fixtures and check the diagnosis.

This does not call a model. It checks that the skill scripts detect each
fixture's defect on their own.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / "cases"
SCRIPTS = {
    "verify-grain-and-joins": ROOT / "skills" / "verify-grain-and-joins" / "scripts" / "check_grain.py",
    "reconcile-metric-values": ROOT / "skills" / "reconcile-metric-values" / "scripts" / "reconcile_metric.py",
    "test-time-semantics": ROOT / "skills" / "test-time-semantics" / "scripts" / "check_time.py",
    "define-metric-contract": ROOT / "skills" / "define-metric-contract" / "scripts" / "validate_contract.py",
}
FLAGS = {
    "timestamp_column": "--timestamp-column",
    "stored_timezone": "--stored-timezone",
    "business_timezone": "--business-timezone",
    "model_date_sql": "--model-date-sql",
    "storage": "--storage",
    "measure_sql": "--measure-sql",
    "id_column": "--id-column",
    "period_start": "--period-start",
    "period_end": "--period-end",
    "declared_boundary": "--declared-boundary",
    "event_column": "--event-column",
    "loaded_column": "--loaded-column",
    "as_of": "--as-of",
    "max_delay_hours": "--max-delay-hours",
    "fiscal_start_month": "--fiscal-start-month",
    "fiscal_date_sql": "--fiscal-date-sql",
    "metric": "--metric",
    "time_column": "--time-column",
    "record_key": "--record-key",
    "tolerance_absolute": "--tolerance-absolute",
    "tolerance_relative": "--tolerance-relative",
    "limit": "--limit",
}


def main() -> int:
    paths = sorted(CASES.glob("*.yaml"))
    if not paths:
        print("no cases found")
        return 1
    failed = 0
    for path in paths:
        case = yaml.safe_load(path.read_text())
        ok, detail = run_case(case)
        print(f"{case['id']} {'pass' if ok else 'fail'}")
        if not ok:
            failed += 1
            print(detail)
    print(f"{len(paths) - failed} passed, {failed} failed")
    return 1 if failed else 0


def run_case(case: dict) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        command = [sys.executable, str(SCRIPTS[case["skill"]])]
        if case["skill"] != "define-metric-contract":
            database = tmp / "case.duckdb"
            con = duckdb.connect(str(database))
            _execute_script(con, case.get("setup_sql") or "SELECT 1")
            con.close()
            command.extend(["--db", str(database)])
        command.extend(_arguments(case, tmp))
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return False, completed.stderr + completed.stdout
        return _expect(case, payload, completed.returncode, completed.stderr)


def _arguments(case: dict, tmp: Path) -> list[str]:
    skill = case["skill"]
    args = case.get("arguments") or {}
    command: list[str] = []
    if skill == "verify-grain-and-joins":
        if "steps" in case:
            path = tmp / "steps.json"
            path.write_text(json.dumps(case["steps"]))
            command.extend(["--steps", str(path)])
        if "mixed" in case:
            path = tmp / "mixed.json"
            path.write_text(json.dumps(case["mixed"]))
            command.extend(["--mixed", str(path)])
    elif skill == "reconcile-metric-values":
        left = tmp / "left.sql"
        right = tmp / "right.sql"
        left.write_text(case["left_sql"])
        right.write_text(case["right_sql"])
        command.extend(["--left-file", str(left), "--right-file", str(right)])
        if isinstance(args.get("keys"), list):
            command.extend(["--keys", ",".join(args["keys"])])
        if isinstance(args.get("segments"), list):
            command.extend(["--segments", ",".join(args["segments"])])
    elif skill == "test-time-semantics":
        source = tmp / "source.sql"
        source.write_text(case["source_sql"])
        command.extend(["--source-file", str(source)])
    elif skill == "define-metric-contract":
        path = tmp / "contract.yaml"
        path.write_text(case["contract_yaml"])
        command.extend(["--contract", str(path)])
    for key, value in args.items():
        if key in {"keys", "segments"}:
            continue
        flag = FLAGS[key]
        command.extend([flag, str(value)])
    return command


def _expect(case: dict, payload: dict, returncode: int, stderr: str) -> tuple[bool, str]:
    expect = case["expect"]
    problems = []
    if "error" in payload:
        problems.append(payload["error"])
    expected_code = expect.get("exit_code", 2)
    if returncode != expected_code:
        problems.append(f"exit {returncode}, expected {expected_code}")
    codes = {item.get("code") for item in payload.get("findings", [])}
    missing = [code for code in expect.get("finding_codes", []) if code not in codes]
    if missing:
        problems.append(f"missing findings {missing}; saw {sorted(codes)}")
    if "valid" in expect and payload.get("valid") is not expect["valid"]:
        problems.append(f"valid is {payload.get('valid')}")
    if "error_contains" in expect:
        text = " ".join(payload.get("evidence", {}).get("errors", []))
        if expect["error_contains"] not in text:
            problems.append(f"errors do not mention {expect['error_contains']!r}: {text}")
    for key, minimum in (expect.get("min_values") or {}).items():
        values = _numbers(payload, key)
        if not values or max(values) < Decimal(str(minimum)):
            problems.append(f"{key} max {values} is below {minimum}")
    for key, expected in (expect.get("equals") or {}).items():
        values = _numbers(payload, key)
        if Decimal(str(expected)) not in values:
            problems.append(f"{key} values {values} do not include {expected}")
    if problems:
        return False, "\n".join(problems) + "\n" + stderr + json.dumps(payload, indent=2)
    return True, ""


def _numbers(payload, key: str) -> list[Decimal]:
    found: list[Decimal] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for name, value in node.items():
                if name == key and not isinstance(value, bool):
                    found.append(Decimal(str(value)))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def _execute_script(con, sql: str) -> None:
    for statement in sql.split(";"):
        if statement.strip():
            con.execute(statement)


if __name__ == "__main__":
    raise SystemExit(main())
