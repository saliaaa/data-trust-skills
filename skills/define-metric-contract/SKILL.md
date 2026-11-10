---
name: define-metric-contract
description: >
  Use when a metric needs a written contract: numerator, denominator,
  population, exclusions, grain, dimensions, owner, timezone, and
  tolerance. Do not use it to prove a query matches that contract.
  That proof is a reconcile plus the grain and time checks.
---

# Define a metric contract

A contract is the spec later checks compare against. This skill writes and validates that spec. It does not certify an implementation.

## Do not use for

- Proving a SQL model matches the contract. Use `verify-grain-and-joins`, `test-time-semantics`, and `reconcile-metric-values`.
- Choosing a dashboard layout or a chart type.
- Inventing an owner, a tolerance, or a population the user has not stated.

## Required inputs

Ask for anything missing. Do not fill it in.

- Metric name and version.
- Owner. A team name or a role is enough. A blank owner is invalid.
- Grain: the columns of one output row.
- Numerator: expression, source, and aggregation (`sum`, `count`, `count_distinct`, `min`, `max`, or `avg`).
- Denominator: the same shape, or an explicit null when the metric is not a ratio.
- Population: a description and a predicate.
- Exclusions: a list of strings. An empty list is allowed and means the population predicate is the whole filter.
- Dimensions: at least one, each with a name and an expression.
- Time: business timezone and boundary, either `[start, end)` or `[start, end]`.
- Tolerance: absolute, relative, or both. Zero is allowed. A missing tolerance is not.

Write the file only after the user has asked for a file and has confirmed the owner and the tolerance.

## Workflow

1. Collect the required fields. Stop on owner or tolerance rather than guessing.
2. Draft the YAML from [references/fields.md](references/fields.md). A synthetic example is [references/example.contract.yaml](references/example.contract.yaml).
3. Check every required field in that reference. The optional script `scripts/validate_contract.py` does the same check for the demo repo. A dbt project does not need it.
4. If you need a row count for the population, run the statement in [references/checks.md](references/checks.md) with `dbt show --inline`, the warehouse SQL editor, or a dbt MCP SQL tool that is already connected.
5. Tell the user that a valid file still does not prove a query implements it.

## Stop conditions

- Owner or tolerance is unknown.
- The user has not asked you to write a file. Show the draft in the reply instead.
- The helper reports an error. Do not hand-wave the error into a pass.

## Output

### Evidence

The validation result: `valid`, and each error string when it is not.

### Assumptions

A null denominator means "not a ratio." An empty exclusion list means the population predicate stands alone. Validation did not query a warehouse.

### Unknowns

Whether any query, model, or dashboard implements the contract. That stays unknown until the other checks run.

## Warehouse dialects

The contract names the type. It does not embed a vendor function. Snowflake: `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ`, or `TIMESTAMP_TZ`. Databricks: `timestamp` or `timestamp_ntz`. The population count for either warehouse is in [references/checks.md](references/checks.md).

## Query budget

Validation issues no SQL. The budget is 0. Do not connect to a warehouse as part of this skill.
