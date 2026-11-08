-- Buggy on purpose.
-- The date is the UTC calendar date, and refunds are joined before the sum.
SELECT
    CAST(o.ordered_at AS DATE) AS order_date,
    c.region AS region,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
INNER JOIN customers AS c
    ON o.customer_id = c.customer_id
LEFT JOIN refunds AS r
    ON o.order_id = r.order_id
WHERE o.status = 'completed'
GROUP BY
    CAST(o.ordered_at AS DATE),
    c.region
