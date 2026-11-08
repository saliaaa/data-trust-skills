"""Seeded synthetic shop data for the broken-revenue demo.

The generator is deterministic. Explicit orders carry the two defects:
a refund join that repeats line items, and UTC timestamps that fall on the
previous America/New_York calendar date. Filler orders use 15:00 UTC and at
most one refund, so they do not add either defect.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from decimal import Decimal

SEED = 20260315
REGIONS = ("US-East", "US-West", "EU", "APAC")
PRICES = (
    Decimal("10.00"),
    Decimal("12.50"),
    Decimal("25.00"),
    Decimal("49.50"),
    Decimal("100.00"),
)


def build_rows(seed: int = SEED):
    rng = random.Random(seed)
    customers = [
        {
            "customer_id": f"c{index:03d}",
            "region": REGIONS[(index - 1) % len(REGIONS)],
            "email": f"customer{index:03d}@example.test",
            "created_at": datetime(2023, 5, 1, 12, 0) + timedelta(days=index * 3),
        }
        for index in range(1, 13)
    ]
    orders: list[dict] = []
    items: list[dict] = []
    refunds: list[dict] = []

    def add_order(order_id, customer_id, ordered_at, status, lines, refund_count=0):
        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "ordered_at": ordered_at,
                "status": status,
            }
        )
        for number, (quantity, price) in enumerate(lines, start=1):
            items.append(
                {
                    "order_item_id": f"{order_id}-i{number}",
                    "order_id": order_id,
                    "sku": f"sku-{number}",
                    "quantity": quantity,
                    "unit_price": price,
                }
            )
        for number in range(1, refund_count + 1):
            refunds.append(
                {
                    "refund_id": f"{order_id}-r{number}",
                    "order_id": order_id,
                    "amount": Decimal("5.00"),
                    "refunded_at": ordered_at + timedelta(days=number),
                }
            )

    add_order(
        "ord_fanout_1",
        "c001",
        datetime(2024, 6, 15, 15, 0),
        "completed",
        [(1, Decimal("40.00")), (1, Decimal("60.00"))],
        refund_count=3,
    )
    add_order(
        "ord_fanout_2",
        "c006",
        datetime(2024, 6, 16, 16, 0),
        "completed",
        [(1, Decimal("25.00"))],
        refund_count=2,
    )
    add_order(
        "ord_tz_1",
        "c002",
        datetime(2024, 1, 15, 3, 30),
        "completed",
        [(1, Decimal("80.00"))],
    )
    add_order(
        "ord_tz_2",
        "c007",
        datetime(2024, 3, 10, 4, 15),
        "completed",
        [(1, Decimal("15.50"))],
    )
    add_order(
        "ord_tz_3",
        "c009",
        datetime(2024, 7, 4, 3, 59),
        "completed",
        [(1, Decimal("10.00"))],
    )
    add_order(
        "ord_dst_overlap",
        "c003",
        datetime(2024, 11, 3, 5, 30),
        "completed",
        [(1, Decimal("20.00"))],
    )
    for index in range(1, 5):
        add_order(
            f"ord_cancelled_{index}",
            "c004",
            datetime(2024, 4, index, 15, 0),
            "cancelled",
            [(1, Decimal("12.50"))],
        )

    for index in range(1, 25):
        customer = customers[(index * 3) % len(customers)]
        ordered_at = datetime(2024, 2, 1, 15, 0) + timedelta(days=index * 3)
        line_count = rng.randint(1, 3)
        lines = [(rng.randint(1, 3), rng.choice(PRICES)) for _ in range(line_count)]
        add_order(
            f"ord_fill_{index:03d}",
            customer["customer_id"],
            ordered_at,
            "completed",
            lines,
            refund_count=1 if rng.random() < 0.25 else 0,
        )

    return {
        "customers": customers,
        "orders": orders,
        "order_items": items,
        "refunds": refunds,
    }


def populate(con, seed: int = SEED) -> dict:
    """Create the four source tables on an open DuckDB connection."""
    rows = build_rows(seed)
    con.execute(
        """
        CREATE OR REPLACE TABLE customers (
            customer_id VARCHAR,
            region VARCHAR,
            email VARCHAR,
            created_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE orders (
            order_id VARCHAR,
            customer_id VARCHAR,
            ordered_at TIMESTAMP,
            status VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE order_items (
            order_item_id VARCHAR,
            order_id VARCHAR,
            sku VARCHAR,
            quantity INTEGER,
            unit_price DECIMAL(12, 2)
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE refunds (
            refund_id VARCHAR,
            order_id VARCHAR,
            amount DECIMAL(12, 2),
            refunded_at TIMESTAMP
        )
        """
    )
    con.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?)",
        [(row["customer_id"], row["region"], row["email"], row["created_at"]) for row in rows["customers"]],
    )
    con.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?)",
        [
            (row["order_id"], row["customer_id"], row["ordered_at"], row["status"])
            for row in rows["orders"]
        ],
    )
    con.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
        [
            (row["order_item_id"], row["order_id"], row["sku"], row["quantity"], row["unit_price"])
            for row in rows["order_items"]
        ],
    )
    con.executemany(
        "INSERT INTO refunds VALUES (?, ?, ?, ?)",
        [
            (row["refund_id"], row["order_id"], row["amount"], row["refunded_at"])
            for row in rows["refunds"]
        ],
    )
    return rows
