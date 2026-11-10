# Install in Codex

Codex reads `.agents/skills/<name>/SKILL.md` in the project and `$HOME/.agents/skills/` for the user. Symlinked skill folders are followed. This was read from the Build skills documentation. Codex was not started against this repo for this release.

From a clone of this repo, in the dbt project:

```bash
bash /path/to/data-trust-skills/scripts/install.sh --codex .
```

That copies the four skill folders into `.agents/skills/`. A plain copy is the same:

```bash
mkdir -p .agents/skills
cp -R /path/to/data-trust-skills/skills/* .agents/skills/
```

The check SQL is inside each skill. The Python scripts are optional and are not required in the dbt project.
