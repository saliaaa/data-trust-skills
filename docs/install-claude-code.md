# Install in Claude Code

Two routes. Neither needs this repo's Python package. The check SQL is inside each skill folder.

Marketplace, from the Claude Code plugin docs:

```bash
claude plugin marketplace add saliaaa/data-trust-skills
claude plugin install data-trust-skills@data-trust-skills
```

[`.claude-plugin/plugin.json`](../.claude-plugin/plugin.json) names the plugin. [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) points at `./`. Claude Code scans `skills/` next to that manifest.

Project skills without the marketplace, which is also where `scripts/install.sh --claude` writes:

```bash
bash /path/to/data-trust-skills/scripts/install.sh --claude .
```

That copies into `.claude/skills/`. User-level skills live in `~/.claude/skills/`.

What was run on 2026-11-10 with Claude Code 2.1.319, not logged in:

- `claude plugin validate` on this checkout passed. It warned that the plugin has no icon. No icon was added.
- `claude plugin marketplace add /path/to/this/checkout` and `claude plugin install data-trust-skills@data-trust-skills` both succeeded.
- `claude plugin marketplace add saliaaa/data-trust-skills` failed: `Marketplace file not found` on the default branch. That command works only after this file is on the default branch.
