# Install in Cursor

Cursor loads project skills from `.cursor/skills/` and `.agents/skills/`. It loads user-level skills from `~/.cursor/skills/` and `~/.agents/skills/`. For compatibility it also reads `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, and `~/.codex/skills/`. Each skill is a folder with `SKILL.md`. This matches the skill directories in the Cursor docs.

This repo's canonical copy stays in `skills/`. The installer copies those folders into the directory Cursor actually scans. The check SQL is inside each skill. The Python scripts are optional.

From a clone, in the dbt project:

```bash
bash /path/to/data-trust-skills/scripts/install.sh --cursor .
```

That writes `.cursor/skills/<skill-name>/SKILL.md`. Plain copy does the same:

```bash
mkdir -p .cursor/skills
cp -R /path/to/data-trust-skills/skills/* .cursor/skills/
```

The rule in [`.cursor/rules/data-trust-skills.mdc`](../.cursor/rules/data-trust-skills.mdc) is for people who open this repo itself. `alwaysApply` is false, a description is set, and there are no globs. A separate Cursor session that loads the skills was not run for this release.
