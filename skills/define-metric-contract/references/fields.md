# Contract fields

The helper accepts the fields below and rejects unknown keys, so a typo cannot pass as a comment.

| Field | Rule |
| --- | --- |
| `metric` | Non-empty string. |
| `version` | Integer, 1 or greater. |
| `owner` | Non-empty string. Never invent one. |
| `description` | Optional non-empty string. |
| `grain` | Non-empty list of column names. |
| `numerator` | `expression`, `source`, and `aggregation`. |
| `denominator` | The same mapping, or `null` when the metric is not a ratio. The key itself is required. |
| `population` | `description` and `predicate`. |
| `exclusions` | List of strings. May be empty. |
| `dimensions` | Non-empty list of `name` and `expression`. |
| `time.timezone` | Business timezone name. |
| `time.boundary` | `[start, end)` or `[start, end]`. |
| `time.stored_timezone` | Optional. |
| `time.fiscal_start_month` | Optional integer from 1 to 12. |
| `tolerance.absolute` | Optional non-negative number. At least one of absolute or relative is required. |
| `tolerance.relative` | Optional non-negative number. Compared with the reference total by the reconcile skill. |
| `notes` | Optional non-empty string. |

Aggregations are `sum`, `count`, `count_distinct`, `min`, `max`, and `avg`.

A filled-in synthetic example is [example.contract.yaml](example.contract.yaml).

## Skeleton

```yaml
metric: gross_item_revenue
version: 1
owner: metric-owner
grain:
  - order_date
numerator:
  expression: quantity * unit_price
  source: order_items
  aggregation: sum
denominator: null
population:
  description: Completed orders.
  predicate: orders.status = 'completed'
exclusions: []
dimensions:
  - name: order_date
    expression: business calendar date of the order
time:
  timezone: America/New_York
  boundary: "[start, end)"
tolerance:
  absolute: "0.01"
```

Quote boundary values. In YAML, a leading `[` starts a flow sequence.

The validator does not run the predicate or the expression. It checks that they are non-empty strings.
