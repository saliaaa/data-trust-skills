# Grain checks

Run these read-only statements yourself. Replace `analytics` and the table names with the model you are checking. One statement at a time.

How to run:

- dbt: `dbt show --inline '<statement>' --limit 50`
- Or `dbt compile`, then run the SELECT in a Snowflake worksheet or a Databricks SQL editor.
- If a dbt MCP server is already connected, use its SQL tool. Do not install one just for this check.

Do not run `MERGE`, `INSERT`, `UPDATE`, or `DELETE`. On Databricks, `MERGE` is how many incremental models write. Compare the grain of the rows before that write with the grain of the table after a merge the user already ran.

The DuckDB script in `scripts/check_grain.py` is an optional extra for the demo in the data-trust-skills repo. A dbt project does not need it.

## Snowflake

Candidate key. `duplicate_extra_rows` and `null_keys` must both be 0.

```sql
SELECT
    COUNT(*) AS row_count,
    COUNT(*) - COUNT(order_item_id) AS null_keys,
    COUNT(DISTINCT order_item_id) AS distinct_keys,
    COUNT(*) - COUNT(DISTINCT order_item_id) AS duplicate_extra_rows
FROM analytics.fct_order_items;
```

Rows whose grain key is repeated. `QUALIFY` keeps only those rows.

```sql
SELECT *
FROM analytics.fct_order_items
QUALIFY COUNT(*) OVER (PARTITION BY order_item_id) > 1
ORDER BY order_item_id
LIMIT 20;
```

Fanout. Compare the line grain before and after the extra join. `multiplied_amount - deduped_amount` is the inflation.

```sql
WITH items AS (
    SELECT
        oi.order_item_id,
        oi.order_id,
        oi.quantity * oi.unit_price AS line_amount
    FROM analytics.order_items AS oi
    INNER JOIN analytics.orders AS o
        ON o.order_id = oi.order_id
    WHERE o.status = 'completed'
),
with_refunds AS (
    SELECT i.order_item_id, i.line_amount
    FROM items AS i
    LEFT JOIN analytics.refunds AS r
        ON r.order_id = i.order_id
)
SELECT
    (SELECT COUNT(*) FROM items) AS before_rows,
    (SELECT COUNT(*) FROM with_refunds) AS after_rows,
    (SELECT SUM(line_amount) FROM items) AS deduped_amount,
    (SELECT SUM(line_amount) FROM with_refunds) AS multiplied_amount;
```

Dropped parent keys.

```sql
SELECT o.order_id
FROM analytics.orders AS o
WHERE o.status = 'completed'
  AND NOT EXISTS (
      SELECT 1
      FROM analytics.order_items AS i
      WHERE i.order_id = o.order_id
  )
LIMIT 20;
```

## Databricks SQL

Same questions. Use `HAVING` instead of `QUALIFY`.

```sql
SELECT
    COUNT(*) AS row_count,
    COUNT(*) - COUNT(order_item_id) AS null_keys,
    COUNT(DISTINCT order_item_id) AS distinct_keys,
    COUNT(*) - COUNT(DISTINCT order_item_id) AS duplicate_extra_rows
FROM analytics.fct_order_items;
```

```sql
SELECT order_item_id, COUNT(*) AS copies
FROM analytics.fct_order_items
GROUP BY order_item_id
HAVING COUNT(*) > 1
ORDER BY copies DESC
LIMIT 1;
```

```sql
WITH items AS (
    SELECT
        oi.order_item_id,
        oi.order_id,
        oi.quantity * oi.unit_price AS line_amount
    FROM analytics.order_items AS oi
    INNER JOIN analytics.orders AS o
        ON o.order_id = oi.order_id
    WHERE o.status = 'completed'
),
with_refunds AS (
    SELECT i.order_item_id, i.line_amount
    FROM items AS i
    LEFT JOIN analytics.refunds AS r
        ON r.order_id = i.order_id
)
SELECT
    (SELECT COUNT(*) FROM items) AS before_rows,
    (SELECT COUNT(*) FROM with_refunds) AS after_rows,
    (SELECT SUM(line_amount) FROM items) AS deduped_amount,
    (SELECT SUM(line_amount) FROM with_refunds) AS multiplied_amount;
```

```sql
SELECT o.order_id
FROM analytics.orders AS o
WHERE o.status = 'completed'
  AND NOT EXISTS (
      SELECT 1
      FROM analytics.order_items AS i
      WHERE i.order_id = o.order_id
  )
LIMIT 20;
```
