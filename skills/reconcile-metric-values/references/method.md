# Reconciliation method

Both queries are aggregated to the declared keys before they are compared. If a side already contained duplicate keys, those duplicates are summed and the reply must say so. Summing duplicates hides a grain problem. When the duplicate count is not zero, run `verify-grain-and-joins` on that side before trusting the breakdown.

## Difference

`difference = left total - right total`.

A positive difference means the left side is larger. The reference for a relative tolerance is the right side:

`relative = abs(difference) / abs(right total)`

when the right total is not zero.

If both an absolute and a relative tolerance are supplied, the difference is inside tolerance when it meets either one. Say that in Assumptions. A contract that wants both limits at once is a stricter rule than this helper implements, and the reply should not claim that stricter rule was checked.

Matching key rows are omitted from `by_time`, `by_segment`, and `top_records`. Their count is `equal_keys`.

## What the buckets mean

- `left_only_keys`: the key is present on the left and missing on the right. The whole left amount is part of the gap.
- `right_only_keys`: the mirror image.
- `value_mismatch_keys`: both sides have the key and the metric differs.

A date shift often shows up as a left-only day and a right-only day whose amounts cancel in the grand total. Do not call that cancellation "no difference" without showing the days.

## Records

`top_records` is ordered by the absolute row difference, then by the key. The default limit is 20. If the limit cuts the list off and the shown rows do not add up to the total difference, say that the tail was not printed.

## Output fields

`within_tolerance` is `true`, `false`, or `null`. `null` means no tolerance was supplied. A finding with code `metric_mismatch` is emitted when the difference is not zero and the tolerance was not met.
