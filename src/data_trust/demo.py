"""Run the synthetic broken-revenue demo."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import duckdb
import yaml

from data_trust.budget import QueryBudget
from data_trust.contract import validate_contract
from data_trust.grain import analyze_join_path
from data_trust.lint import lint_grouped_select
from data_trust.reconcile import reconcile
from data_trust.time_semantics import check_time

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "broken-revenue-demo"
SEED = 20260315

ORDER_BUGGY = """
SELECT
    o.order_id,
    c.region,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
LEFT JOIN refunds AS r
    ON o.order_id = r.order_id
WHERE o.status = 'completed'
GROUP BY o.order_id, c.region
"""

ORDER_CORRECT = """
SELECT
    o.order_id,
    c.region,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY o.order_id, c.region
"""

DAY_UTC = """
SELECT
    CAST(o.ordered_at AS DATE) AS order_date,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.status = 'completed'
GROUP BY 1
"""

DAY_BUSINESS = """
SELECT
    CAST(
        (o.ordered_at AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York'
        AS DATE
    ) AS order_date,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.status = 'completed'
GROUP BY 1
"""

TIME_SOURCE = """
SELECT
    o.order_id,
    o.ordered_at,
    oi.quantity * oi.unit_price AS line_amount
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.status = 'completed'
"""


def _load_generate():
    path = DEMO_DIR / "generate.py"
    spec = importlib.util.spec_from_file_location("broken_revenue_generate", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def money(value: Decimal) -> str:
    return f"{Decimal(value).quantize(Decimal('0.01'))}"


def load_demo(con, seed: int = SEED) -> None:
    generate = _load_generate()
    generate.populate(con, seed)
    buggy = (DEMO_DIR / "models" / "buggy_revenue.sql").read_text()
    correct = (DEMO_DIR / "models" / "correct_revenue.sql").read_text()
    con.execute(f"CREATE OR REPLACE TABLE buggy_revenue AS {buggy}")
    con.execute(f"CREATE OR REPLACE TABLE correct_revenue AS {correct}")


def _basic_failures(con, table: str) -> list[str]:
    failures = []
    duplicate_groups = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT order_date, region
            FROM {table}
            GROUP BY 1, 2
            HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    if duplicate_groups:
        failures.append("order_date + region is not unique")
    nulls = con.execute(
        f"""
        SELECT count(*) FROM {table}
        WHERE order_date IS NULL OR region IS NULL OR revenue IS NULL
        """
    ).fetchone()[0]
    if nulls:
        failures.append("order_date, region, or revenue is null")
    negatives = con.execute(
        f"SELECT count(*) FROM {table} WHERE revenue < 0"
    ).fetchone()[0]
    if negatives:
        failures.append("revenue is negative")
    return failures


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def analyze(con, seed: int = SEED) -> dict:
    steps = json.loads((DEMO_DIR / "join_steps.json").read_text())
    contract = yaml.safe_load((DEMO_DIR / "gross_item_revenue.contract.yaml").read_text())
    buggy_sql = (DEMO_DIR / "models" / "buggy_revenue.sql").read_text()
    correct_sql = (DEMO_DIR / "models" / "correct_revenue.sql").read_text()
    counts = {
        name: int(con.execute(f"SELECT count(*) FROM {name}").fetchone()[0])
        for name in ("customers", "orders", "order_items", "refunds")
    }
    counts["completed_orders"] = int(
        con.execute("SELECT count(*) FROM orders WHERE status = 'completed'").fetchone()[0]
    )
    buggy_total = _decimal(con.execute("SELECT sum(revenue) FROM buggy_revenue").fetchone()[0])
    correct_total = _decimal(con.execute("SELECT sum(revenue) FROM correct_revenue").fetchone()[0])
    grain = analyze_join_path(con, steps, QueryBudget(40))
    timing = check_time(
        con,
        TIME_SOURCE,
        timestamp_column="ordered_at",
        stored_timezone="UTC",
        business_timezone="America/New_York",
        model_date_sql="CAST(ordered_at AS DATE)",
        storage="utc_timestamp",
        measure_sql="line_amount",
        id_column="order_id",
        budget=QueryBudget(40),
    )
    orders = reconcile(
        con,
        ORDER_BUGGY,
        ORDER_CORRECT,
        metric="revenue",
        keys=["order_id", "region"],
        segments=["region"],
        record_key="order_id",
        budget=QueryBudget(20),
    )
    days = reconcile(
        con,
        DAY_UTC,
        DAY_BUSINESS,
        metric="revenue",
        keys=["order_date"],
        time_column="order_date",
        record_key="order_date",
        budget=QueryBudget(20),
    )
    fanout = next(item for item in grain["findings"] if item["code"] == "measure_inflated_by_fanout")
    example_key = None
    for finding in grain["findings"]:
        if finding["code"] == "fanout" and finding["evidence"].get("example"):
            example_key = finding["evidence"]["example"]
            break
    counterexample = None
    if example_key is not None:
        item_id = example_key["key"]["order_item_id"]
        order_id = con.execute(
            "SELECT order_id FROM order_items WHERE order_item_id = ?",
            [item_id],
        ).fetchone()[0]
        item_rows = con.execute(
            """
            SELECT order_item_id, quantity, unit_price
            FROM order_items
            WHERE order_id = ?
            ORDER BY order_item_id
            """,
            [order_id],
        ).fetchall()
        refund_rows = con.execute(
            "SELECT refund_id, amount FROM refunds WHERE order_id = ? ORDER BY refund_id",
            [order_id],
        ).fetchall()
        counterexample = {
            "order_id": order_id,
            "order_item_id": item_id,
            "copies": example_key["copies"],
            "items": [
                {"order_item_id": row[0], "quantity": row[1], "unit_price": _decimal(row[2])}
                for row in item_rows
            ],
            "refunds": [{"refund_id": row[0], "amount": _decimal(row[1])} for row in refund_rows],
        }
    shifted = con.execute(
        """
        SELECT row_id, ts, model_date, business_date, sum(measure_value) AS revenue
        FROM dts_time_classified
        WHERE model_date <> business_date
        GROUP BY 1, 2, 3, 4
        ORDER BY revenue DESC, row_id
        """
    ).fetchall()
    return {
        "seed": seed,
        "duckdb_version": duckdb.__version__,
        "rows": counts,
        "basic_tests": {
            "buggy": _basic_failures(con, "buggy_revenue"),
            "correct": _basic_failures(con, "correct_revenue"),
        },
        "lint": {
            "buggy": lint_grouped_select(buggy_sql),
            "correct": lint_grouped_select(correct_sql),
        },
        "contract_valid": validate_contract(contract)["valid"],
        "totals": {
            "buggy": buggy_total,
            "correct": correct_total,
            "inflation": buggy_total - correct_total,
        },
        "grain": grain,
        "time": timing,
        "orders": orders,
        "days": days,
        "fanout_extra_revenue": fanout["evidence"]["extra_revenue"],
        "counterexample": counterexample,
        "shifted_orders": [
            {
                "order_id": row[0],
                "ordered_at": row[1],
                "model_date": row[2],
                "business_date": row[3],
                "revenue": _decimal(row[4]),
            }
            for row in shifted
        ],
    }


def _timezone_lines(result: dict) -> list[str]:
    time_evidence = result["time"]["evidence"]
    day_evidence = result["days"]["evidence"]
    lines = [
        "root cause 2: timezone boundary",
        "  stored: UTC naive timestamp",
        "  business timezone: America/New_York",
        "  model date expression: CAST(ordered_at AS DATE)",
        f"  shifted line rows: {time_evidence['shifted_rows']}",
        f"  revenue on shifted rows: {money(time_evidence['shifted_measure'])}",
    ]
    for shifted in result["shifted_orders"]:
        lines.append(
            "  shifted order: "
            f"{shifted['order_id']} ordered_at {shifted['ordered_at']} "
            f"model_date {shifted['model_date']} business_date {shifted['business_date']} "
            f"revenue {money(shifted['revenue'])}"
        )
    moved = sum((abs(row["difference"]) for row in day_evidence["by_time"]), Decimal("0")) / 2
    lines.extend(
        [
            f"  day-level revenue moved: {money(moved)}",
            "  the timezone bug does not change the grand total",
        ]
    )
    return lines


def _day_lines(result: dict) -> list[str]:
    day_evidence = result["days"]["evidence"]
    lines = [
        "reconcile calendar days, deduped UTC date minus America/New_York date",
        f"  total difference: {money(day_evidence['difference'])}",
        "  days with a difference:",
    ]
    for row in day_evidence["by_time"]:
        lines.append(
            f"    {row['value']}: utc {money(row['left_total'])} "
            f"business {money(row['right_total'])} difference {money(row['difference'])}"
        )
    return lines


def format_timezone_report(result: dict) -> str:
    """The timezone section of the full demo, with the same figures."""
    lines = [
        "data-trust-skills demo",
        f"seed: {result['seed']}",
        f"engine: duckdb {result['duckdb_version']} (in memory)",
        "metric: gross_item_revenue",
        "section: timezone",
        "",
        *_timezone_lines(result),
        "",
        *_day_lines(result),
        "",
    ]
    return "\n".join(lines)


def format_report(result: dict) -> str:
    totals = result["totals"]
    time_evidence = result["time"]["evidence"]
    order_evidence = result["orders"]["evidence"]
    lines = [
        "data-trust-skills demo",
        f"seed: {result['seed']}",
        f"engine: duckdb {result['duckdb_version']} (in memory)",
        "metric: gross_item_revenue",
        "",
        "dataset",
        f"  customers: {result['rows']['customers']}",
        f"  orders: {result['rows']['orders']}",
        f"  completed_orders: {result['rows']['completed_orders']}",
        f"  order_items: {result['rows']['order_items']}",
        f"  refunds: {result['rows']['refunds']}",
        "",
        "buggy model",
        "  file: examples/broken-revenue-demo/models/buggy_revenue.sql",
        f"  basic tests: {_status(result['basic_tests']['buggy'])}",
        "  basic test rules: unique order_date + region, no nulls, revenue >= 0",
        f"  sql lint: {_status(result['lint']['buggy'])}",
        "  sql lint rules: no SELECT *, no CROSS JOIN, GROUP BY present",
        "",
        "totals",
        f"  buggy: {money(totals['buggy'])}",
        f"  correct: {money(totals['correct'])}",
        f"  inflation: {money(totals['inflation'])}",
        "",
        "root cause 1: join fanout",
        "  step: refunds_joined",
        "  intended grain: order_item_id",
        "  labeled relationship: many_to_one",
        f"  extra rows: {_fanout_extra_rows(result)}",
        f"  extra revenue: {money(result['fanout_extra_revenue'])}",
    ]
    example = result["counterexample"]
    if example is not None:
        lines.extend(
            [
                "  counterexample:",
                f"    order_id: {example['order_id']}",
                f"    repeated order_item_id: {example['order_item_id']}",
                f"    copies of that item: {example['copies']}",
                f"    line items: {_items(example['items'])}",
                f"    refund rows: {len(example['refunds'])}",
            ]
        )
    lines.extend(
        [
            "",
            *_timezone_lines(result),
            "",
            "daylight-saving scan",
            f"  repeated-hour rows: {time_evidence.get('overlap_rows', 0)}",
            f"  missing-hour rows: {time_evidence.get('gap_rows', 0)}",
            "",
            "reconcile orders, buggy minus correct",
            f"  difference: {money(order_evidence['difference'])}",
            "  by region:",
        ]
    )
    for row in order_evidence["by_segment"]["region"]:
        lines.append(
            f"    {row['value']}: buggy {money(row['left_total'])} "
            f"correct {money(row['right_total'])} difference {money(row['difference'])}"
        )
    lines.append("  orders with a difference:")
    for row in order_evidence["top_records"]:
        lines.append(
            f"    {row['record']}: buggy {money(row['left_metric'])} "
            f"correct {money(row['right_metric'])} difference {money(row['difference'])}"
        )
    lines.extend(["", *_day_lines(result), "", "assumptions",
            "  - The reference metric is completed-order line amounts, with no refund join, on the America/New_York date.",
            "  - Gross item revenue does not subtract refunds.",
            "  - Extra revenue is the refund-join sum minus one copy of each line amount.",
            "  - Day-level revenue moved is half the sum of absolute daily differences.",
            "  - The daylight-saving scan uses the order timestamps, padded by two days.",
            "  - No tolerance was applied to the demo difference.",
            "unknowns",
            "  - none",
            "",
        ]
    )
    return "\n".join(lines)


def _fanout_extra_rows(result: dict) -> int:
    for finding in result["grain"]["findings"]:
        if finding["code"] == "fanout":
            return int(finding["evidence"]["extra_rows"])
    return 0


def _status(issues: list[str]) -> str:
    if not issues:
        return "pass"
    return "fail (" + "; ".join(issues) + ")"


def _items(items: list[dict]) -> str:
    return ", ".join(
        f"{item['order_item_id']} qty {item['quantity']} price {money(item['unit_price'])}" for item in items
    )


def run_demo(seed: int = SEED) -> dict:
    con = duckdb.connect()
    load_demo(con, seed)
    return analyze(con, seed)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the seeded synthetic revenue demo.")
    parser.add_argument(
        "--timezone",
        action="store_true",
        help="Print only the timezone section. Figures match the full demo.",
    )
    args = parser.parse_args(argv)
    result = run_demo()
    text = format_timezone_report(result) if args.timezone else format_report(result)
    print(text, end="")
    return 0
