"""Assert an install.sh layout has the four skills and valid frontmatter."""

from __future__ import annotations

import sys
from pathlib import Path

SKILLS = (
    "verify-grain-and-joins",
    "reconcile-metric-values",
    "test-time-semantics",
    "define-metric-contract",
)
LAYOUTS = (".cursor/skills", ".claude/skills", ".agents/skills")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_installed_skills.py TARGET", file=sys.stderr)
        return 2
    root = Path(argv[1])
    errors: list[str] = []
    for layout in LAYOUTS:
        for name in SKILLS:
            skill = root / layout / name / "SKILL.md"
            if not skill.is_file():
                errors.append(f"missing {skill}")
                continue
            text = skill.read_text()
            if not text.startswith("---\n"):
                errors.append(f"{skill}: frontmatter missing")
                continue
            end = text.find("\n---\n", 4)
            if end < 0:
                errors.append(f"{skill}: frontmatter not closed")
                continue
            block = text[4:end]
            fields = {}
            for line in block.splitlines():
                if ":" in line and not line.startswith(" "):
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            if fields.get("name") != name:
                errors.append(f"{skill}: name is {fields.get('name')!r}")
            description = fields.get("description", "")
            if description in {"", ">", "|"} and "description:" not in block:
                errors.append(f"{skill}: description missing")
            if "description:" not in block:
                errors.append(f"{skill}: description missing")
            checks = root / layout / name / "references" / "checks.md"
            if not checks.is_file():
                errors.append(f"missing {checks}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"installed skills ok under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
