# Agent comparison

Optional. CI does not run this. It needs your own agent login for Cursor, Claude Code, or Codex. Nothing else in this repo does.

This harness asks an agent CLI the same question with the skills loaded and again without them. It scores the reply text for the root cause, the inflation amount when the case names one, listed false-positive phrases, and write-like actions.

It does not invent a model result. If no CLI is installed, or none of them is logged in, the JSON status is `pending` and `results` is empty. The checked-in file for 2026-11-08 is that pending probe.

## Run

From the repository root, with `cursor-agent`, `claude`, or `codex` on `PATH` and already logged in:

```bash
python evals/agent-comparison/run_comparison.py \
  --run \
  --runs 3 \
  --output evals/agent-comparison/results/latest.json \
  --transcript-dir evals/agent-comparison/transcripts
```

`--runs` is the repeat count per case per condition. Use more than one when you want a spread. The script records the CLI version. It does not invent a model name; a completed row leaves `model` null unless a future change parses it from the transcript.

Omit `--run` to probe install and login only.

Login is per client:

- Cursor: `cursor-agent login` or `CURSOR_API_KEY`
- Claude Code: `claude auth login` or `ANTHROPIC_API_KEY`
- Codex: `codex login` or the Codex credential that `codex login status` recognizes

With-skills uses a copy of this repo, including `skills/`, the Cursor rule, the Claude plugin directory, and symlinks under `.agents/skills/`. Without-skills uses a copy that drops `skills/`, `.cursor/`, `.claude-plugin/`, and `.agents/`. Cursor runs in `--mode ask`. Claude Code uses `--permission-mode plan` and, for the with-skills copy, `--plugin-dir`. Codex exec uses `--sandbox read-only`.

Cases are [cases.json](cases.json). Scoring rules are [score.py](score.py).

The checked-in result for 2026-11-08 is [results/2026-11-08.json](results/2026-11-08.json). That file is a pending probe, not a score.
