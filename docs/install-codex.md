# Install in Codex

Codex reads `SKILL.md` directories from `.agents/skills/` in the repository and from `$HOME/.agents/skills/`. The current Build skills documentation also says symlinked skill folders are followed. This was read from that documentation. On 2026-11-08 Codex CLI 0.167.0 was installed in the release environment. `codex login status` printed `Not logged in`. The skill trigger was not run (no credentials).

This repo keeps the only copy under [`skills/`](../skills/verify-grain-and-joins/SKILL.md). From a checkout, a symlink is the install, not a second copy:

```bash
mkdir -p .agents/skills
ln -s ../../skills/verify-grain-and-joins .agents/skills/verify-grain-and-joins
ln -s ../../skills/reconcile-metric-values .agents/skills/reconcile-metric-values
ln -s ../../skills/test-time-semantics .agents/skills/test-time-semantics
ln -s ../../skills/define-metric-contract .agents/skills/define-metric-contract
```

Those links are not committed. Create them in the checkout where you want Codex to see the skills. The helper commands still expect that checkout to be the working directory, because the scripts import the shared library under `src/`.
