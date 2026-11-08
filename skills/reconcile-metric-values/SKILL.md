---
name: reconcile-metric-values
description: >
  Use when two queries, models, or extracts are supposed to be the same
  metric and you need the numeric gap broken down by time, by segment,
  and by record. Do not use it to decide which definition is correct,
  and do not use it as the first check when the only suspect is a join.
---

# Reconcile metric values

This skill explains a numeric gap. It does not choose a winner. Call the right-hand query the reference and say so.

## Do not use for

- A single query whose join may be duplicating rows. Use `verify-grain-and-joins` first.
- Deciding the business definition, the owner, or the tolerance. Use `define-metric-contract`.
- Timezone rules, except where a date column is already one of the keys and you only need the gap by that date.
- Dashboard layout, filter clicks, or chart formatting.

## Required inputs

- Two read-only `SELECT` statements.
- One numeric metric column, present on both sides, with the same name.
- The key columns that should match. A time column or a segment column has to be one of those keys.
- An optional record key, also one of the keys, used to rank contributors. If you omit it, the helper ranks by the first key.
- A tolerance from a contract, if one exists. Do not invent a tolerance. With no tolerance, any non-zero difference is a mismatch.

## Workflow

1. State which side is the reference. The helper treats the right-hand query as the reference for a relative tolerance.
2. Run:

```bash
uv run python skills/reconcile-metric-values/scripts/reconcile_metric.py \
  --db warehouse.duckdb \
  --left-file left.sql \
  --right-file right.sql \
  --metric revenue \
  --keys order_date,region \
  --time-column order_date \
  --segments region \
  --record-key order_date
```

3. Report the two totals, the signed difference (left minus right), and the absolute difference.
4. Split the gap into left-only keys, right-only keys, and keys whose values disagree.
5. Show the time buckets and segment buckets whose difference is not zero, then the top records.
6. Stop when the residual is inside the supplied tolerance, or when no finer key was provided. The unexplained remainder is an unknown, not a zero.

The decomposition rules are in [references/method.md](references/method.md).

## Stop conditions

- The two queries do not share the metric name and the key columns.
- A requested time or segment column is not a key.
- Either statement is not a single read-only `SELECT`.
- The query budget is exhausted.
- The reference total is zero and the only tolerance is relative. Say that the relative check could not be evaluated.

## Output

### Evidence

Left total, right total, difference, tolerance result, counts of left-only and right-only keys, and the non-zero time, segment, and record rows.

### Assumptions

Which side is the reference. Whether duplicate keys were summed. That matching rows were omitted from the breakdown.

### Unknowns

Keys you could not align, a relative tolerance you could not evaluate, and any slice you did not request.

## Query budget

The default budget is 20 statements. The database file is opened read-only. The helper rejects a statement that is not a single `SELECT` or `WITH`. Use a warehouse role that cannot write when the file is not DuckDB; the keyword filter is only a local guard.
