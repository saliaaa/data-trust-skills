# Rubric

The runner in [run_evals.py](run_evals.py) does not score a model. It checks that each helper script reports the defect in the matching fixture. One of those fixtures is [refund-join-fanout.yaml](cases/refund-join-fanout.yaml).

A written reply that follows a skill should still meet all of the following:

1. Evidence is numeric and comes from a query result or a contract file.
2. Assumptions are labeled as assumptions.
3. Unknowns are labeled as unknowns, including a missing owner or tolerance.
4. A defect claim names one counterexample key or row.
5. The reply stays inside the skill's query budget and does not write to the warehouse.
6. The reply stops when a required input is missing instead of inventing it.

A reply that names a cause without a measured number fails item 1.
