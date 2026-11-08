# Contributing

Issues and pull requests are welcome. The work in this repo is original. Do not paste text or code from another skill pack, including packs published by tool vendors.

## Local check

```bash
uv sync
make ci
```

`make ci` validates every `SKILL.md`, runs pytest, and runs the fixture evals. A change that updates the demo's numbers has to update the README from a fresh `make demo` run. Do not type a result from memory.

## A new skill

Use a new directory under `skills/<kebab-name>/` with:

- `SKILL.md` whose frontmatter `name` matches the directory and whose description says when to use it
- `references/` for the longer method
- `scripts/` for a helper, when a deterministic check is possible

The skill body needs the headings the validator looks for: do not use, required inputs, workflow, stop, output, and query budget. Keep the default path read-only. Add a fixture under `evals/cases/` when the helper can catch a known defect, and add a pytest for the library function.

## Data

Fixtures and demos use synthetic rows only. Do not add a real company, a real customer, or a dump from a private system. Generic names such as `example.test` are the standard here.

## Dependencies

Pin direct dependencies in `pyproject.toml` and refresh `uv.lock` with `uv lock`. The default path is local DuckDB. Do not add a hosted warehouse as a requirement.
