---
name: test-time-semantics
description: >
  Use when a date, timezone, daylight-saving transition, inclusive period
  end, late-arriving row, or fiscal calendar could move a metric. Do not
  use it to debug join fanout or to write the metric's business definition.
---

# Test time semantics

Times move metrics without changing a join. This skill measures those moves. The conversions below were checked on DuckDB 2.0.0. Another engine can disagree; say which engine ran.

## Do not use for

- Join duplication or dropped keys. Use `verify-grain-and-joins`.
- Choosing the business timezone or the tolerance. Those belong in `define-metric-contract`.
- A gap between two aggregates that is not about time. Use `reconcile-metric-values`.
- Changing the session time zone or the warehouse clock.

## Required inputs

Name the check. Each one has its own inputs, and missing inputs are a stop, not a default.

- Date shift: timestamp column, how it is stored (`utc_timestamp` or `local_timestamp`), stored timezone, business timezone, and the date expression the model actually uses. A measure expression is needed to report an amount. Without it, report the row count and mark the amount unknown.
- Daylight saving is included in a date-shift check. It scans the data window. It is not a separate guess about the calendar.
- Period end: `period_start`, `period_end`, and the declared convention `[start, end)` or `[start, end]` when the model has one.
- Late rows: event timestamp, loaded timestamp, the as-of instant, and the allowed delay in hours.
- Fiscal year: fiscal start month, from 1 to 12. Month 1 means the fiscal label matches the calendar year.

`utc_timestamp` means a naive timestamp whose clock is the stored timezone, usually UTC. `local_timestamp` means a naive civil time in the business timezone. A real `timestamptz` column is not a supported storage mode in this version. Cast it to the mode you mean and say that you did.

## Workflow

1. State the storage mode and both timezones before running anything.
2. Run only the checks whose inputs you have:

```bash
uv run python skills/test-time-semantics/scripts/check_time.py \
  --db warehouse.duckdb \
  --source-file source.sql \
  --timestamp-column ordered_at \
  --storage utc_timestamp \
  --stored-timezone UTC \
  --business-timezone America/New_York \
  --model-date-sql "CAST(ordered_at AS DATE)" \
  --measure-sql line_amount \
  --id-column order_id
```

3. For a date shift, quote `shifted_rows`, `shifted_measure`, and the example row.
4. For daylight saving, separate repeated-hour rows (`dst_overlap`, informational) from stored times that fall in a missing hour (`dst_gap`, a defect). A UTC instant cannot fall in a spring-forward gap. A naive local clock can.
5. For a period end, quote how many rows sit on the endpoint and which convention includes them.
6. For late rows, separate "missing from a snapshot taken at as-of" from "slower than the allowed delay."
7. For a fiscal calendar, quote how many rows have a fiscal year label different from their calendar year.

The conversion and the fiscal rule are in [references/method.md](references/method.md).

## Stop conditions

- No check was fully specified.
- The timezone name is not a simple zone id the helper can pass to DuckDB.
- `local_timestamp` was requested but the stored timezone and the business timezone differ.
- The timestamp window is longer than 20,000 hours. The helper skips the daylight-saving scan, records an unknown, and still returns any other check you asked for.
- The statement is not a single read-only `SELECT`.

## Output

### Evidence

The counts and amounts for the checks that ran, plus one example row when a date moved.

### Assumptions

Storage mode, the DuckDB `AT TIME ZONE` behavior, the half-open or closed convention, and the fiscal-year label rule.

### Unknowns

A missing measure, a window that was too wide to scan, and any check you did not run.

## Warehouse dialects

The helper's conversions were executed with DuckDB `AT TIME ZONE`. DuckDB is the local stand-in. Use the warehouse functions below in the SELECT you ask the helper, or in the SQL you run yourself. Do not assume the three engines agree.

Snowflake `TIMESTAMP_NTZ` is a civil time with no zone. `TIMESTAMP_LTZ` is shown in the session time zone. `TIMESTAMP_TZ` keeps the offset stored with the value. `CONVERT_TIMEZONE('UTC', 'America/New_York', ordered_at_ntz)` turns a `TIMESTAMP_NTZ` that means UTC into another zone. `CONVERT_TIMEZONE('America/New_York', ordered_at_tz)` takes a `TIMESTAMP_TZ` or `TIMESTAMP_LTZ` and returns the clock in the target zone.

Databricks `timestamp` is shown in the session time zone. `timestamp_ntz` is a civil time with no zone. `to_utc_timestamp(ts, zone)` treats `ts` as a clock in `zone` and shifts it to UTC. `from_utc_timestamp(ts, zone)` treats `ts` as UTC and shifts the clock to `zone`.

## Query budget

The default budget is 25 statements. The file is opened read-only. Passing `--budget` higher is allowed only to finish a scan you already started, and the reply must say so.
