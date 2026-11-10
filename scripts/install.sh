#!/usr/bin/env bash
# Copy the skill folders into a project. No API key and no package install.
# Usage: scripts/install.sh --cursor|--claude|--codex [target-dir]
# target-dir defaults to the current directory.
set -euo pipefail

usage() {
  echo "Usage: install.sh --cursor|--claude|--codex [target-dir]" >&2
  echo "  --cursor  project skills in <target>/.cursor/skills/" >&2
  echo "  --claude  project skills in <target>/.claude/skills/" >&2
  echo "  --codex   project skills in <target>/.agents/skills/" >&2
  exit 2
}

CLIENT=""
if [[ $# -lt 1 ]]; then
  usage
fi
case "$1" in
  --cursor) CLIENT="cursor" ;;
  --claude) CLIENT="claude" ;;
  --codex) CLIENT="codex" ;;
  *) usage ;;
esac
TARGET="${2:-.}"

case "$CLIENT" in
  cursor) DEST="${TARGET}/.cursor/skills" ;;
  claude) DEST="${TARGET}/.claude/skills" ;;
  codex) DEST="${TARGET}/.agents/skills" ;;
esac

cleanup() {
  if [[ -n "${CLONE_DIR:-}" && -d "$CLONE_DIR" ]]; then
    rm -rf "$CLONE_DIR"
  fi
}
trap cleanup EXIT

resolve_source() {
  local script_dir repo_skills
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_skills="$(cd "$script_dir/.." && pwd)/skills"
    if [[ -d "$repo_skills/verify-grain-and-joins" ]]; then
      printf '%s\n' "$repo_skills"
      return
    fi
  fi
  CLONE_DIR="$(mktemp -d)"
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/saliaaa/data-trust-skills.git "$CLONE_DIR/repo"
  git -C "$CLONE_DIR/repo" sparse-checkout set skills
  printf '%s\n' "$CLONE_DIR/repo/skills"
}

SOURCE="$(resolve_source)"
mkdir -p "$DEST"
for skill in verify-grain-and-joins reconcile-metric-values test-time-semantics define-metric-contract; do
  if [[ ! -f "$SOURCE/$skill/SKILL.md" ]]; then
    echo "missing $SOURCE/$skill/SKILL.md" >&2
    exit 1
  fi
  rm -rf "$DEST/$skill"
  cp -R "$SOURCE/$skill" "$DEST/$skill"
done

echo "installed ${CLIENT} skills into ${DEST}"
