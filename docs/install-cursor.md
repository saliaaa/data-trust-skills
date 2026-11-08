# Install in Cursor

Cursor project rules live in [`.cursor/rules/`](../.cursor/rules/data-trust-skills.mdc). The rule in this repo sets `alwaysApply: false` and a description, and it does not set `globs`. That is the "apply intelligently" shape in the Cursor rules docs: the agent can pull the rule in when the description matches.

The rule points at the canonical [`skills/`](../skills/verify-grain-and-joins/SKILL.md) folder. Cursor's skill loader looks in `.cursor/skills/`, `.agents/skills/`, and a few compatibility directories. It does not scan a top-level `skills/` directory. This repo does not copy the skills into those directories.

Opening this repo is the setup that was written down. A separate Cursor session that loads the rule was not run for this release.

To point another project at a clone without copying the files:

```bash
mkdir -p .cursor/rules
# Write a short rule whose body names the absolute path of each SKILL.md
# in the clone. Keep the canonical files where they are.
```
