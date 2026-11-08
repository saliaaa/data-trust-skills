"""Keep the README attached to commands that were actually run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from data_trust.demo import money, run_demo

ROOT = Path(__file__).resolve().parents[1]


def test_readme_quotes_the_demo_and_every_eval_case():
    readme = (ROOT / "README.md").read_text()
    result = run_demo()
    assert f"buggy: {money(result['totals']['buggy'])}" in readme
    assert f"correct: {money(result['totals']['correct'])}" in readme
    assert f"inflation: {money(result['totals']['inflation'])}" in readme
    assert f"revenue on shifted rows: {money(result['time']['evidence']['shifted_measure'])}" in readme
    assert "not real business data" in readme
    assert "Snowflake" in readme and "Databricks" in readme
    assert "docs/ecosystem.md" in readme
    assert "agent-comparison" not in readme
    assert "official" not in readme.lower()
    for path in sorted((ROOT / "evals" / "cases").glob("*.yaml")):
        case_id = yaml.safe_load(path.read_text())["id"]
        assert f"{case_id} pass" in readme


def test_eval_runner_exits_zero():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run_evals.py")],
        check=False,
        cwd=ROOT,
    )
    assert completed.returncode == 0


def test_skill_validator_exits_zero():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_skills.py")],
        check=False,
        cwd=ROOT,
    )
    assert completed.returncode == 0
