from decimal import Decimal

import duckdb

from data_trust.time_semantics import check_time


def test_utc_morning_moves_to_the_previous_business_date():
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE events AS
        SELECT * FROM (
            VALUES
                ('o1', TIMESTAMP '2024-01-15 03:30:00', 80.00::DECIMAL(12, 2)),
                ('o2', TIMESTAMP '2024-01-15 15:00:00', 10.00::DECIMAL(12, 2))
        ) AS v(order_id, ordered_at, line_amount)
        """
    )
    report = check_time(
        con,
        "SELECT order_id, ordered_at, line_amount FROM events",
        timestamp_column="ordered_at",
        stored_timezone="UTC",
        business_timezone="America/New_York",
        model_date_sql="CAST(ordered_at AS DATE)",
        measure_sql="line_amount",
        id_column="order_id",
    )
    assert report["evidence"]["shifted_rows"] == 1
    assert report["evidence"]["shifted_measure"] == Decimal("80.00")
    assert report["evidence"]["shift_example"]["id"] == "o1"


def test_local_gap_and_utc_overlap():
    gap = duckdb.connect()
    gap.execute(
        """
        CREATE TABLE events AS
        SELECT TIMESTAMP '2024-03-10 02:30:00' AS ts, 10.00::DECIMAL(12, 2) AS amount
        """
    )
    gap_report = check_time(
        gap,
        "SELECT ts, amount FROM events",
        timestamp_column="ts",
        stored_timezone="America/New_York",
        business_timezone="America/New_York",
        model_date_sql="CAST(ts AS DATE)",
        storage="local_timestamp",
        measure_sql="amount",
    )
    assert any(item["code"] == "dst_gap" for item in gap_report["findings"])
    assert gap_report["evidence"]["gap_rows"] == 1

    overlap = duckdb.connect()
    overlap.execute(
        """
        CREATE TABLE events AS
        SELECT TIMESTAMP '2024-11-03 05:30:00' AS ordered_at, 20.00::DECIMAL(12, 2) AS amount
        """
    )
    overlap_report = check_time(
        overlap,
        "SELECT ordered_at, amount FROM events",
        timestamp_column="ordered_at",
        stored_timezone="UTC",
        business_timezone="America/New_York",
        model_date_sql="CAST(ordered_at AS DATE)",
        measure_sql="amount",
    )
    overlap_finding = next(item for item in overlap_report["findings"] if item["code"] == "dst_overlap")
    assert overlap_finding["severity"] == "info"
    assert overlap_report["evidence"]["shifted_rows"] == 0


def test_period_end_late_rows_and_fiscal_year():
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE events AS
        SELECT * FROM (
            VALUES
                (TIMESTAMP '2024-01-15 12:00:00', TIMESTAMP '2024-01-15 12:00:00'),
                (TIMESTAMP '2024-02-01 00:00:00', TIMESTAMP '2024-02-10 00:00:00')
        ) AS v(event_at, loaded_at)
        """
    )
    boundary = check_time(
        con,
        "SELECT event_at, loaded_at FROM events",
        timestamp_column="event_at",
        period_start="2024-01-01 00:00:00",
        period_end="2024-02-01 00:00:00",
        declared_boundary="[start, end]",
    )
    assert boundary["evidence"]["on_endpoint"] == 1
    assert boundary["evidence"]["half_open_includes"] == 1
    assert boundary["evidence"]["closed_includes"] == 2

    late = check_time(
        con,
        "SELECT event_at, loaded_at FROM events",
        timestamp_column="event_at",
        event_column="event_at",
        loaded_column="loaded_at",
        as_of="2024-02-01 00:00:00",
        max_delay_hours=48,
    )
    assert late["evidence"]["missing_from_snapshot"] == 1
    assert late["evidence"]["beyond_delay"] == 1

    fiscal = check_time(
        con,
        "SELECT event_at FROM events",
        timestamp_column="event_at",
        fiscal_start_month=4,
    )
    assert fiscal["evidence"]["fiscal_mismatches"] == 2

    calendar = check_time(
        con,
        "SELECT event_at FROM events",
        timestamp_column="event_at",
        fiscal_start_month=1,
    )
    assert calendar["evidence"]["fiscal_mismatches"] == 0
    assert calendar["findings"] == []
