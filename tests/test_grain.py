import duckdb
import pytest

from data_trust.budget import QueryBudget
from data_trust.errors import DataTrustError
from data_trust.grain import analyze_join_path, check_mixed_grain


def test_one_to_many_with_a_unique_child_grain_is_not_fanout():
    con = duckdb.connect()
    con.execute("CREATE TABLE orders (order_id VARCHAR)")
    con.execute("CREATE TABLE items (order_item_id VARCHAR, order_id VARCHAR, line_amount INTEGER)")
    con.execute("INSERT INTO orders VALUES ('o1')")
    con.execute("INSERT INTO items VALUES ('i1', 'o1', 10), ('i2', 'o1', 15)")
    report = analyze_join_path(
        con,
        [
            {
                "name": "orders",
                "relationship": "base",
                "grain": ["order_id"],
                "sql": "SELECT order_id FROM orders",
            },
            {
                "name": "items",
                "relationship": "one_to_many",
                "parent": "orders",
                "parent_key": ["order_id"],
                "grain": ["order_item_id"],
                "measure": "line_amount",
                "sql": "SELECT order_id, order_item_id, line_amount FROM items",
            },
        ],
    )
    assert report["findings"] == []


def test_refund_join_inflates_the_measure():
    con = duckdb.connect()
    con.execute("CREATE TABLE items (order_item_id VARCHAR, order_id VARCHAR, line_amount INTEGER)")
    con.execute("CREATE TABLE refunds (refund_id VARCHAR, order_id VARCHAR)")
    con.execute("INSERT INTO items VALUES ('i1', 'o1', 40), ('i2', 'o1', 60)")
    con.execute("INSERT INTO refunds VALUES ('r1', 'o1'), ('r2', 'o1')")
    report = analyze_join_path(
        con,
        [
            {
                "name": "items",
                "relationship": "base",
                "grain": ["order_item_id"],
                "measure": "line_amount",
                "sql": "SELECT order_item_id, order_id, line_amount FROM items",
            },
            {
                "name": "with_refunds",
                "relationship": "many_to_one",
                "parent": "items",
                "parent_key": ["order_item_id"],
                "grain": ["order_item_id"],
                "measure": "line_amount",
                "sql": """
                    SELECT i.order_item_id, i.order_id, i.line_amount
                    FROM items AS i
                    LEFT JOIN refunds AS r ON i.order_id = r.order_id
                """,
            },
        ],
    )
    codes = {item["code"] for item in report["findings"]}
    assert "fanout" in codes
    assert "measure_inflated_by_fanout" in codes
    inflated = next(item for item in report["findings"] if item["code"] == "measure_inflated_by_fanout")
    assert inflated["evidence"]["extra_revenue"] == 100


def test_inner_join_reports_the_dropped_key():
    con = duckdb.connect()
    con.execute("CREATE TABLE orders (order_id VARCHAR)")
    con.execute("CREATE TABLE customers (customer_id VARCHAR)")
    con.execute("INSERT INTO orders VALUES ('o1'), ('o2')")
    con.execute("INSERT INTO customers VALUES ('o1')")
    report = analyze_join_path(
        con,
        [
            {
                "name": "orders",
                "relationship": "base",
                "grain": ["order_id"],
                "sql": "SELECT order_id FROM orders",
            },
            {
                "name": "with_customer",
                "relationship": "many_to_one",
                "parent": "orders",
                "parent_key": ["order_id"],
                "grain": ["order_id"],
                "sql": """
                    SELECT o.order_id
                    FROM orders AS o
                    INNER JOIN customers AS c ON o.order_id = c.customer_id
                """,
            },
        ],
    )
    dropped = next(item for item in report["findings"] if item["code"] == "dropped_rows")
    assert dropped["evidence"]["dropped_keys"] == 1
    assert dropped["evidence"]["example"]["order_id"] == "o2"


def test_mixed_grain_and_a_uniform_table():
    con = duckdb.connect()
    con.execute("CREATE TABLE stacked (order_item_id VARCHAR, sales_date DATE, amount INTEGER)")
    con.execute(
        """
        INSERT INTO stacked VALUES
            ('i1', DATE '2024-01-01', 10),
            (NULL, DATE '2024-01-01', 10)
        """
    )
    mixed = check_mixed_grain(
        con,
        "SELECT order_item_id, sales_date, amount FROM stacked",
        "order_item_id",
        ["order_item_id"],
        ["sales_date"],
    )
    assert {item["code"] for item in mixed["findings"]} == {"mixed_grain"}

    con.execute("DELETE FROM stacked WHERE order_item_id IS NULL")
    uniform = check_mixed_grain(
        con,
        "SELECT order_item_id, sales_date, amount FROM stacked",
        "order_item_id",
        ["order_item_id"],
        ["sales_date"],
    )
    assert uniform["findings"] == []


def test_null_grain_key_is_reported():
    con = duckdb.connect()
    con.execute("CREATE TABLE events (order_id VARCHAR)")
    con.execute("INSERT INTO events VALUES ('o1'), (NULL)")
    report = analyze_join_path(
        con,
        [
            {
                "name": "events",
                "relationship": "base",
                "grain": ["order_id"],
                "sql": "SELECT order_id FROM events",
            }
        ],
    )
    assert any(item["code"] == "key_nulls" for item in report["findings"])


def test_write_statement_and_budget_stop():
    con = duckdb.connect()
    con.execute("CREATE TABLE events (order_id VARCHAR)")
    con.execute("INSERT INTO events VALUES ('o1')")
    with pytest.raises(DataTrustError):
        analyze_join_path(
            con,
            [
                {
                    "name": "events",
                    "relationship": "base",
                    "grain": ["order_id"],
                    "sql": "DELETE FROM events",
                }
            ],
        )
    with pytest.raises(DataTrustError, match="budget"):
        analyze_join_path(
            con,
            [
                {
                    "name": "events",
                    "relationship": "base",
                    "grain": ["order_id"],
                    "sql": "SELECT order_id FROM events",
                }
            ],
            QueryBudget(1),
        )
