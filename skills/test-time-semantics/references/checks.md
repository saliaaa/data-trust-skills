# Time checks

Run one statement. Replace the table, the timestamp column, and the measure. Do not change the session time zone as part of the check.

How to run:

- dbt: `dbt show --inline '<statement>' --limit 50`
- Or run the SELECT in a Snowflake worksheet or a Databricks SQL editor.
- If a dbt MCP server is already connected, use its SQL tool.

The DuckDB script in `scripts/check_time.py` is an optional extra for the demo repo. A dbt project does not need it. The conversions below are the ones to run on the warehouse. They are not the same as DuckDB `AT TIME ZONE`.

## Snowflake

`TIMESTAMP_NTZ` stored as a UTC clock. Three-argument `CONVERT_TIMEZONE` turns that clock into America/New_York. `shifted_amount` is the measure that lands on the wrong calendar day. The grand total of the table does not change.

```sql
SELECT
    COUNT(*) AS shifted_rows,
    SUM(line_amount) AS shifted_amount
FROM analytics.order_items
WHERE CAST(ordered_at AS DATE)
    <> CAST(CONVERT_TIMEZONE('UTC', 'America/New_York', ordered_at) AS DATE);
```

`TIMESTAMP_TZ` or `TIMESTAMP_LTZ`. Two-argument `CONVERT_TIMEZONE` returns the clock in the target zone. `TIMESTAMP_LTZ` is shown in the session time zone. `TIMESTAMP_TZ` keeps the offset stored with the value.

```sql
SELECT
    COUNT(*) AS shifted_rows,
    SUM(line_amount) AS shifted_amount
FROM analytics.order_items
WHERE CAST(ordered_at AS DATE)
    <> CAST(CONVERT_TIMEZONE('America/New_York', ordered_at) AS DATE);
```

One example row:

```sql
SELECT
    order_id,
    ordered_at,
    CAST(ordered_at AS DATE) AS model_date,
    CAST(CONVERT_TIMEZONE('UTC', 'America/New_York', ordered_at) AS DATE) AS business_date,
    line_amount
FROM analytics.order_items
WHERE CAST(ordered_at AS DATE)
    <> CAST(CONVERT_TIMEZONE('UTC', 'America/New_York', ordered_at) AS DATE)
ORDER BY line_amount DESC
LIMIT 1;
```

## Databricks SQL

`timestamp` is shown in the session time zone. `timestamp_ntz` is a civil time with no zone. `from_utc_timestamp` treats the input clock as UTC and shifts it to the named zone. `to_utc_timestamp` does the opposite: it treats the input clock as already being in that zone.

Use `from_utc_timestamp` when the column is a UTC instant, or a `timestamp_ntz` whose clock is UTC.

```sql
SELECT
    COUNT(*) AS shifted_rows,
    SUM(line_amount) AS shifted_amount
FROM analytics.order_items
WHERE CAST(ordered_at AS DATE)
    <> CAST(from_utc_timestamp(ordered_at, 'America/New_York') AS DATE);
```

Use `to_utc_timestamp` only when the column is a civil time in America/New_York and you need the UTC instant. That is the inverse check, not the default.
