# Install in Claude Code

The skill files live in [`skills/`](../skills/verify-grain-and-joins/SKILL.md). [`plugin.json`](../.claude-plugin/plugin.json) names the plugin, and [`marketplace.json`](../.claude-plugin/marketplace.json) points the marketplace at `./`, the repository root. Claude Code's default plugin layout scans `skills/` next to `.claude-plugin/`. This repo does not set an extra `skills` path, so that scan is not registered twice.

These commands are the ones described in the Claude Code plugin docs. They were not executed while this release was prepared:

```bash
claude plugin marketplace add saliaaa/data-trust-skills
claude plugin install data-trust-skills@data-trust-skills
```

A local checkout can be registered as a directory marketplace:

```bash
claude plugin marketplace add /path/to/data-trust-skills
```

A one-session load, also from those docs and also not executed here, is `claude --plugin-dir /path/to/data-trust-skills`.

The helper commands in each skill assume the working directory is a checkout of this repo, with `uv sync` already run. A marketplace install's working directory was not tested.
