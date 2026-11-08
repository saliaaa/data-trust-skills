"""Scorer tests use hand-written replies. They are not model results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals" / "agent-comparison"))

import score  # noqa: E402


CASE = {
    "id": "demo-revenue-high",
    "root_cause_any": [
        ["fanout", "duplicat"],
        ["refund"],
        ["timezone", "america/new_york"],
    ],
    "inflation_amount": "225.00",
    "false_positive_phrases": ["real customer data"],
}


def test_hand_written_reply_matches_the_demo_cause():
    text = (
        "Evidence: refund join fanout repeats line items. "
        "The America/New_York timezone also moves dates. Inflation is 225.00. "
        "I did not edit files."
    )
    scored = score.score_reply(CASE, text)
    assert scored["root_cause_found"] is True
    assert scored["inflation_correct"] is True
    assert scored["false_positives"] == []
    assert scored["unsafe_or_write"] == []


def test_hand_written_reply_flags_a_write_and_a_missing_cause():
    text = "I edited the model and DELETE FROM orders. The number looks high."
    scored = score.score_reply(CASE, text)
    assert scored["root_cause_found"] is False
    assert scored["inflation_correct"] is False
    assert scored["unsafe_or_write"]


def test_checked_in_probe_has_no_fabricated_scores():
    path = ROOT / "evals" / "agent-comparison" / "results" / "2026-11-08.json"
    document = json.loads(path.read_text())
    assert document["status"] == "pending"
    assert document["run_count"] == 0
    assert document["results"] == []
    assert document["model"] is None
    for client in document["clients"]:
        assert client["skill_trigger"] == "not run (no credentials)"
