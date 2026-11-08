-- Gross item revenue on the America/New_York calendar date.
-- Refunds are not subtracted and are not joined.
SELECT
    CAST(
        (o.ordered_at AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York'
        AS DATE
    ) AS order_date,
    c.region AS region,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY
    CAST(
        (o.ordered_at AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York'
        AS DATE
    ),
    c.region
