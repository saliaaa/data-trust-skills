from decimal import Decimal

import duckdb

from data_trust.reconcile import reconcile


LEFT = """
SELECT region, revenue FROM (
    VALUES
        ('US-East', 100.00::DECIMAL(12, 2)),
        ('EU', 80.00::DECIMAL(12, 2))
) AS v(region, revenue)
"""
RIGHT = """
SELECT region, revenue FROM (
    VALUES
        ('US-East', 100.00::DECIMAL(12, 2)),
        ('EU', 50.00::DECIMAL(12, 2))
) AS v(region, revenue)
"""


def test_segment_gap_is_isolated():
    report = reconcile(
        duckdb.connect(),
        LEFT,
        RIGHT,
        metric="revenue",
        keys=["region"],
        segments=["region"],
        record_key="region",
    )
    assert report["evidence"]["difference"] == Decimal("30.00")
    assert report["evidence"]["by_segment"]["region"] == [
        {
            "value": "EU",
            "left_total": Decimal("80.00"),
            "right_total": Decimal("50.00"),
            "difference": Decimal("30.00"),
        }
    ]
    assert report["findings"][0]["code"] == "metric_mismatch"


def test_equal_queries_have_no_mismatch():
    report = reconcile(duckdb.connect(), LEFT, LEFT, metric="revenue", keys=["region"])
    assert report["evidence"]["difference"] == 0
    assert report["findings"] == []


def test_absolute_tolerance_can_pass():
    report = reconcile(
        duckdb.connect(),
        LEFT,
        RIGHT,
        metric="revenue",
        keys=["region"],
        tolerance_absolute=Decimal("30"),
    )
    assert report["evidence"]["within_tolerance"] is True
    assert report["findings"] == []


def test_left_only_key_is_counted():
    right = """
    SELECT region, revenue FROM (
        VALUES ('US-East', 100.00::DECIMAL(12, 2))
    ) AS v(region, revenue)
    """
    report = reconcile(duckdb.connect(), LEFT, right, metric="revenue", keys=["region"])
    assert report["evidence"]["left_only_keys"] == 1
    assert report["evidence"]["difference"] == Decimal("80.00")
