---
name: verify-grain-and-joins
description: >
  Use when a join or a published table may have the wrong number of rows.
  Prove a candidate key, measure fanout, find parent keys that disappear,
  or detect a table that stacks two grains. Use it before trusting a sum
  that sits on a join. Do not use it to compare two finished metric queries,
  to test timezones, or to invent a metric definition.
---

# Verify grain and joins

A sum is only as trustworthy as the row set underneath it. This skill checks that row set. It does not decide what the metric should mean.

## Do not use for

- Comparing two queries that already return the metric. Use `reconcile-metric-values`.
- Timezones, period ends, late rows, or fiscal calendars. Use `test-time-semantics`.
- Writing the business definition. Use `define-metric-contract`.
- Query speed, warehouse privileges, or a semantic-layer UI.

## Required inputs

- A read-only database file, or a connection the helper did not open for writes.
- The intended grain: the columns that must be unique at the step you care about, before a later `GROUP BY` hides duplicates.
- Either join steps or a mixed-grain spec.
- For each join step: a `SELECT`, a relationship (`base`, `one_to_one`, `many_to_one`, or `one_to_many`), the parent step, and the parent key.
- A measure column, already computed in the step, when you need the extra amount and not only the extra rows.

Stop and ask if the grain is missing. Do not guess it from a column name.

## Workflow

1. Restate the grain in one sentence: "one row per `order_item_id` before the daily sum."
2. Run the statements in [references/checks.md](references/checks.md). Pick the Snowflake block or the Databricks block. Use `dbt show --inline`, the warehouse SQL editor, or a dbt MCP SQL tool that is already connected.
3. Read null keys and duplicate keys before the join story.
4. Treat a repeated grain key as fanout. A `one_to_many` label does not excuse it. Quote `multiplied_amount - deduped_amount` when the check returns both sums.
5. Treat parent keys that disappear as dropped rows.
6. Put one counterexample key in the reply whenever a finding exists.

Details are in [references/method.md](references/method.md). The script in `scripts/check_grain.py` is an optional DuckDB extra for the demo repo. A dbt project does not need it.

## Stop conditions

- The grain was not named and there is no contract that names it.
- The statement is not a single `SELECT` or `WITH`.
- A step's grain columns are not in its result.
- The query budget is exhausted. Report the steps already measured and stop.
- Two steps have no parent key in common, so dropped keys cannot be counted.

## Output

Use these three headings and do not put a number under Evidence unless the helper returned it.

### Evidence

Finding code, step name, row counts, extra rows, extra amount, and one example key.

### Assumptions

The relationship labels you supplied. A `one_to_many` label allows the row count to grow. It does not excuse a repeated grain key.

### Unknowns

Null grain keys, a measure that is not constant across copies, and any step you did not run.

## Warehouse dialects

Snowflake and Databricks statements are in [references/checks.md](references/checks.md). Snowflake uses `QUALIFY` to keep repeated keys. Databricks uses `HAVING`. Do not run `MERGE`. On Databricks, compare the grain before a `MERGE` the user already ran with the grain of the table after it.

## Query budget

The default budget is 30 statements. The helper opens the file read-only and rejects anything other than a single `SELECT` or `WITH`. That keyword filter is not a privilege. Use a database role that cannot write.

Raise `--budget` only when the path has more steps than the default can count, and say that you raised it.
