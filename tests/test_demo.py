from decimal import Decimal
from pathlib import Path

import duckdb

from data_trust.demo import analyze, format_report, load_demo, run_demo
from data_trust.lint import lint_grouped_select

ROOT = Path(__file__).resolve().parents[1]


def test_demo_numbers_and_green_basic_checks():
    con = duckdb.connect()
    load_demo(con)
    line_sum = con.execute(
        """
        SELECT sum(oi.quantity * oi.unit_price)
        FROM orders AS o
        INNER JOIN order_items AS oi ON o.order_id = oi.order_id
        WHERE o.status = 'completed'
        """
    ).fetchone()[0]
    result = analyze(con)
    assert result["totals"]["correct"] == line_sum
    assert result["totals"]["buggy"] == Decimal("3377.50")
    assert result["totals"]["correct"] == Decimal("3152.50")
    assert result["totals"]["inflation"] == Decimal("225.00")
    assert result["fanout_extra_revenue"] == Decimal("225.00")
    assert result["time"]["evidence"]["shifted_measure"] == Decimal("105.50")
    assert result["time"]["evidence"]["shifted_rows"] == 3
    assert result["days"]["evidence"]["difference"] == 0
    assert result["basic_tests"]["buggy"] == []
    assert result["basic_tests"]["correct"] == []
    assert result["lint"]["buggy"] == []
    assert result["lint"]["correct"] == []
    assert result["contract_valid"] is True
    codes = {item["code"] for item in result["grain"]["findings"]}
    assert "fanout" in codes
    assert "dropped_rows" not in codes
    text = format_report(result)
    assert "inflation: 225.00" in text
    assert "extra rows: 5" in text
    assert "revenue on shifted rows: 105.50" in text
    assert "unknowns" in text
    assert "assumptions" in text


def test_model_files_contain_the_intended_defects():
    buggy = (ROOT / "examples" / "broken-revenue-demo" / "models" / "buggy_revenue.sql").read_text()
    correct = (ROOT / "examples" / "broken-revenue-demo" / "models" / "correct_revenue.sql").read_text()
    assert "LEFT JOIN refunds" in buggy
    assert "CAST(o.ordered_at AS DATE)" in buggy
    assert "join refunds" not in correct.lower()
    assert "America/New_York" in correct
    assert lint_grouped_select(buggy) == []
    assert "SELECT * is present" in lint_grouped_select("SELECT * FROM orders") 


def test_run_demo_matches_analyze():
    result = run_demo()
    assert result["rows"]["customers"] == 12
    assert result["rows"]["orders"] == 34
    assert result["rows"]["completed_orders"] == 30
    assert result["rows"]["order_items"] == 59
    assert result["rows"]["refunds"] == 12
