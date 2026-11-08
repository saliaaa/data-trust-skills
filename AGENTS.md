# Agents working in this repo

The product is the skill pack under `skills/`. Each skill is one directory with `SKILL.md`, `references/`, and a helper script. Do not copy those directories into `.cursor/`, `.claude/`, or `.agents/`. Client packaging stays thin: the Claude plugin manifest, the marketplace file, and the Cursor rule.

## Checks

From a checkout, after `uv sync`:

```bash
make ci
make demo
```

`make demo` is the synthetic revenue case. If the printed totals change, replace the README sample with the new output. Do not invent a figure, and do not add a percentage the command did not print.

## Behavior the skills require

- Read-only SQL. The helpers reject other statements, and a new helper should too.
- A query budget with a hard stop.
- Replies split into evidence, assumptions, and unknowns.
- No invented owner and no invented tolerance in a metric contract.
- Synthetic data only. No real company, employer, or customer rows.

## Evals

`evals/run_evals.py` checks the helper scripts against fixtures. It does not call a model. Do not add a harness that calls a hosted agent.

## Dependencies

Python and DuckDB. Pin new direct dependencies. Keep the default path local.
