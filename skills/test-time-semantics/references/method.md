# Time method

## Date shift

For `utc_timestamp`, the business timestamp is:

```sql
(ordered_at AT TIME ZONE '<stored timezone>') AT TIME ZONE '<business timezone>'
```

The business date is that value cast to `DATE`. The model date is whatever expression the model uses, also cast to `DATE`. A row counts as shifted when those two dates differ. `shifted_measure` sums the measure on those rows only.

For `local_timestamp`, the stored value is already the civil time. The business date is the calendar date of that value. The useful checks are then the missing hour and the model's own expression, which may still differ.

These expressions were executed on DuckDB 2.0.0. DuckDB's `AT TIME ZONE` on a naive timestamp interprets that clock in the named zone. Do not assume another engine matches it.

## Daylight saving

The helper builds an hourly series from two days before the earliest timestamp to two days after the latest, converts each hour into the business zone, and looks at the local-hour step.

- A step of 2 is a spring-forward gap. The missing local interval is reported. Stored UTC instants do not land in it. A `local_timestamp` whose civil time sits in that interval is a `dst_gap` defect, because that civil time did not happen.
- A step of 0 is a fall-back overlap. Rows whose local civil time is inside the repeated hour are `dst_overlap`. The finding is informational: the clock label is ambiguous until an offset is known. It is not, by itself, a statement that the total is wrong.

The scan stops above 20,000 hours and leaves the transitions unknown.

## Period ends

`[start, end)` includes `start` and excludes `end`. `[start, end]` includes both. Rows exactly equal to `end` are the ones the two conventions disagree on. The helper counts them even when a convention was declared, so the reply can say how many rows the declaration keeps.

## Late rows

`missing_from_snapshot` counts events at or before the as-of instant whose loaded timestamp is after that instant. `beyond_delay` counts rows whose loaded timestamp is more than the allowed number of hours after the event, using epoch seconds. A row can be in both counts.

## Fiscal year

The fiscal year label is the calendar year in which that fiscal year starts. If the fiscal year starts in month `M`:

- a date in month `M` or later is fiscal year = calendar year
- a date before month `M` is fiscal year = calendar year - 1

`M = 1` produces no mismatches. A mismatch is not automatically a bug. It is a bug when the model uses the calendar year for a metric whose contract says otherwise.
