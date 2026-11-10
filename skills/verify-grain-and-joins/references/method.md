# Grain method

## Candidate key

A candidate key is unique and not null on the relation you named. The helper reports both failures separately. Null keys are not counted as duplicates, because SQL `GROUP BY` collapses them into one bucket and that bucket is not a real key.

## Join steps

Each step is the full `SELECT` after that join, not a diff. The first step uses `"relationship": "base"`. Later steps name a `parent`, a `parent_key`, and one of:

| Relationship | Row count may grow | Grain key may repeat |
| --- | --- | --- |
| `one_to_one` | no | no |
| `many_to_one` | no | no |
| `one_to_many` | yes | no |

"Grain key may repeat" is always no. If the child grain is `order_item_id` and a refund join repeats `order_item_id`, that is fanout even when someone labeled the step `one_to_many`.

`parent_key` is how dropped rows are counted: distinct non-null parent keys in the parent step, minus those still present in the child.

## Measure inflation

Name a measure only when the step already exposes it as a column. The helper sums it, then sums one copy per grain key. The difference is the amount a later `SUM` would add because of the repeated rows. If the copies of one key do not all hold the same measure, the deduped sum is marked unstable and the reply must list that as an unknown.

## Mixed grain

Use `--mixed` when one table holds both detail rows and header rows.

```json
{
  "source_sql": "SELECT * FROM stacked_sales",
  "detail_column": "order_item_id",
  "fine_key": ["order_item_id"],
  "coarse_key": ["sales_date"]
}
```

Detail rows are the rows where `detail_column` is not null. Header rows are the rows where it is null. Both populations have to be non-empty. A normal fact table, where the detail column is always filled, is not mixed grain.

## Step file

```json
[
  {
    "name": "orders",
    "relationship": "base",
    "grain": ["order_id"],
    "sql": "SELECT order_id FROM orders"
  },
  {
    "name": "items",
    "relationship": "one_to_many",
    "parent": "orders",
    "parent_key": ["order_id"],
    "grain": ["order_item_id"],
    "measure": "line_amount",
    "sql": "SELECT order_id, order_item_id, line_amount FROM order_lines"
  }
]
```

Identifiers are letters, digits, and underscores. The `SELECT` cannot contain a second statement.

## How to read the JSON

- `findings[].code` is `key_nulls`, `key_not_unique`, `fanout`, `dropped_rows`, `measure_inflated_by_fanout`, or `mixed_grain`.
- `severity: fail` means the reply should not call the row set safe.
- `evidence.steps[]` still lists row counts for steps that passed. A pass is the absence of a finding, not a hidden flag.
- `query_budget.used` is the number of statements the helper issued, including its own bookkeeping views.
