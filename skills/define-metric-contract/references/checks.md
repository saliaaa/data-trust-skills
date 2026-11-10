# Contract check

The contract file is the check. Required fields are listed in [fields.md](fields.md). A filled-in example is [example.contract.yaml](example.contract.yaml). Do not invent `owner` or `tolerance`.

The DuckDB script in `scripts/validate_contract.py` is an optional extra. You can review the YAML without it.

After the file exists, this read-only count shows whether the population predicate returns rows. It does not prove the metric is implemented.

How to run:

- dbt: `dbt show --inline '<statement>' --limit 5`
- Or run the SELECT in a Snowflake worksheet or a Databricks SQL editor.
- If a dbt MCP server is already connected, use its SQL tool.

## Snowflake

```sql
SELECT COUNT(*) AS population_rows
FROM analytics.orders
WHERE status = 'completed';
```

Name the timestamp type in the contract before you pick a conversion: `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ`, or `TIMESTAMP_TZ`. The time skill has the matching `CONVERT_TIMEZONE` form.

## Databricks SQL

```sql
SELECT COUNT(*) AS population_rows
FROM analytics.orders
WHERE status = 'completed';
```

Name `timestamp` or `timestamp_ntz` in the contract. The time skill then uses `from_utc_timestamp` or `to_utc_timestamp`.
