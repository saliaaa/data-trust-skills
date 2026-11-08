"""Validate skill frontmatter, relative links, and the thin client packaging.

Absolute http(s) links are not fetched. CI uses this script for the links
that can be resolved inside the repository.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADINGS = (
    "do not use",
    "required inputs",
    "workflow",
    "stop",
    "output",
    "query budget",
)
MARKDOWN_ROOTS = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "docs",
    "skills",
    "examples",
    "evals",
)


def main() -> int:
    errors: list[str] = []
    skill_dirs = sorted(path for path in SKILLS.iterdir() if path.is_dir() and not path.name.startswith("."))
    if len(skill_dirs) != 4:
        errors.append(f"expected 4 skill directories, found {len(skill_dirs)}")
    for skill_dir in skill_dirs:
        errors.extend(_skill(skill_dir))
    errors.extend(_packaging())
    for path in _markdown_files():
        errors.extend(_links(path))
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"validated {len(skill_dirs)} skills and {len(_markdown_files())} markdown files")
    return 0


def _skill(skill_dir: Path) -> list[str]:
    errors = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [f"{skill_dir.name}: SKILL.md is missing"]
    if not (skill_dir / "references").is_dir():
        errors.append(f"{skill_dir.name}: references/ is missing")
    scripts = list((skill_dir / "scripts").glob("*.py")) if (skill_dir / "scripts").is_dir() else []
    if not scripts:
        errors.append(f"{skill_dir.name}: scripts/ has no Python helper")
    text = skill_file.read_text()
    try:
        meta, body = _frontmatter(text)
    except ValueError as exc:
        return [f"{skill_dir.name}: {exc}"]
    name = meta.get("name")
    description = meta.get("description")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{skill_dir.name}: frontmatter name is missing")
    elif name != skill_dir.name:
        errors.append(f"{skill_dir.name}: frontmatter name is {name!r}")
    elif not NAME.match(name):
        errors.append(f"{skill_dir.name}: name is not kebab-case")
    if not isinstance(description, str) or len(description.strip()) < 40:
        errors.append(f"{skill_dir.name}: frontmatter description is missing or too short")
    headings = "\n".join(line.lower() for line in body.splitlines() if line.startswith("#"))
    for required in HEADINGS:
        if required not in headings:
            errors.append(f"{skill_dir.name}: heading containing {required!r} is missing")
    return errors


def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("frontmatter is missing")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed")
    loaded = yaml.safe_load(text[4:end])
    if not isinstance(loaded, dict):
        raise ValueError("frontmatter is not a mapping")
    return loaded, text[end + 5 :]


def _packaging() -> list[str]:
    errors = []
    plugin_path = ROOT / ".claude-plugin" / "plugin.json"
    market_path = ROOT / ".claude-plugin" / "marketplace.json"
    rule_path = ROOT / ".cursor" / "rules" / "data-trust-skills.mdc"
    for path in (plugin_path, market_path, rule_path):
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
    if plugin_path.is_file():
        plugin = json.loads(plugin_path.read_text())
        if plugin.get("name") != "data-trust-skills":
            errors.append("plugin.json name is not data-trust-skills")
        if not plugin.get("description") or not plugin.get("version"):
            errors.append("plugin.json needs description and version")
    if market_path.is_file():
        market = json.loads(market_path.read_text())
        if not market.get("name") or not market.get("owner") or not market.get("plugins"):
            errors.append("marketplace.json needs name, owner, and plugins")
        else:
            source = market["plugins"][0].get("source")
            if source != "./":
                errors.append("marketplace plugin source is not ./")
    if rule_path.is_file():
        rule = rule_path.read_text()
        if "alwaysApply: false" not in rule or "description:" not in rule:
            errors.append("Cursor rule must set description and alwaysApply: false")
        if "skills/" not in rule:
            errors.append("Cursor rule does not point at skills/")
    return errors


def _markdown_files() -> list[Path]:
    files: list[Path] = []
    for item in MARKDOWN_ROOTS:
        path = ROOT / item
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
    return files


def _links(path: Path) -> list[str]:
    errors = []
    text = path.read_text()
    slugs = _slugs(text)
    for match in LINK.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        anchor = None
        file_part = target
        if "#" in target:
            file_part, anchor = target.split("#", 1)
        if not file_part:
            if anchor and anchor not in slugs:
                errors.append(f"{path.relative_to(ROOT)}: missing anchor #{anchor}")
            continue
        resolved = (path.parent / file_part).resolve()
        if not resolved.is_file():
            errors.append(f"{path.relative_to(ROOT)}: broken link {target}")
            continue
        if anchor:
            target_slugs = _slugs(resolved.read_text())
            if anchor not in target_slugs:
                errors.append(f"{path.relative_to(ROOT)}: missing anchor {target}")
    return errors


def _slugs(text: str) -> set[str]:
    slugs = set()
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        title = line.lstrip("#").strip().lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", title)
        slug = re.sub(r"\s+", "-", slug).strip("-")
        slugs.add(slug)
    return slugs


if __name__ == "__main__":
    raise SystemExit(main())
