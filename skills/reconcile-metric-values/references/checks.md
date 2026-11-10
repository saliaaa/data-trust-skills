# Reconcile two calculations

The right-hand side is the reference. Replace the two queries with the old model and the new model, both aggregated to the same keys. Run one statement. Do not write.

How to run:

- dbt: `dbt show --inline '<statement>' --limit 50`
- Or run the SELECT in a Snowflake worksheet or a Databricks SQL editor after `dbt compile`.
- If a dbt MCP server is already connected, use its SQL tool.

The DuckDB script in `scripts/reconcile_metric.py` is an optional extra for the demo repo. A dbt project does not need it.

If the old rows are already in the warehouse, the old side can be a time-travel read instead of a second model query.

## Snowflake

Day difference, new minus old. A non-zero `difference` with a `0` total still means days moved.

```sql
WITH new_side AS (
    SELECT order_date, SUM(revenue) AS revenue
    FROM analytics.fct_orders
    GROUP BY order_date
),
old_side AS (
    SELECT order_date, SUM(revenue) AS revenue
    FROM analytics.fct_orders AT(TIMESTAMP => '2024-11-01 00:00:00'::TIMESTAMP_TZ)
    GROUP BY order_date
)
SELECT
    COALESCE(n.order_date, o.order_date) AS order_date,
    n.revenue AS new_revenue,
    o.revenue AS old_revenue,
    COALESCE(n.revenue, 0) - COALESCE(o.revenue, 0) AS difference
FROM new_side AS n
FULL OUTER JOIN old_side AS o
    ON n.order_date = o.order_date
WHERE COALESCE(n.revenue, 0) <> COALESCE(o.revenue, 0)
ORDER BY ABS(COALESCE(n.revenue, 0) - COALESCE(o.revenue, 0)) DESC;
```

The other Snowflake time-travel form is `BEFORE(STATEMENT => '<query_id>')` on the old table, in place of `AT(TIMESTAMP => ...)`.

Totals:

```sql
WITH compared AS (
    SELECT
        COALESCE(n.revenue, 0) AS new_revenue,
        COALESCE(o.revenue, 0) AS old_revenue
    FROM new_side AS n
    FULL OUTER JOIN old_side AS o
        ON n.order_date = o.order_date
)
SELECT
    SUM(new_revenue) AS new_total,
    SUM(old_revenue) AS old_total,
    SUM(new_revenue) - SUM(old_revenue) AS difference
FROM compared;
```

Put the `new_side` and `old_side` CTEs from the first statement above this totals query, or save the day result and sum it.

## Databricks SQL

Same shape. For a Delta table, the old side is a version or a timestamp, not a Snowflake `AT` clause.

```sql
WITH new_side AS (
    SELECT order_date, SUM(revenue) AS revenue
    FROM analytics.fct_orders
    GROUP BY order_date
),
old_side AS (
    SELECT order_date, SUM(revenue) AS revenue
    FROM analytics.fct_orders VERSION AS OF 12
    GROUP BY order_date
)
SELECT
    COALESCE(n.order_date, o.order_date) AS order_date,
    n.revenue AS new_revenue,
    o.revenue AS old_revenue,
    COALESCE(n.revenue, 0) - COALESCE(o.revenue, 0) AS difference
FROM new_side AS n
FULL OUTER JOIN old_side AS o
    ON n.order_date = o.order_date
WHERE COALESCE(n.revenue, 0) <> COALESCE(o.revenue, 0)
ORDER BY ABS(COALESCE(n.revenue, 0) - COALESCE(o.revenue, 0)) DESC;
```

`TIMESTAMP AS OF '2024-11-01T00:00:00.000Z'` can replace `VERSION AS OF 12`.
