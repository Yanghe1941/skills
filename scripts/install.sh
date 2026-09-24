#!/usr/bin/env bash
# Install a skill from this repo into an agent's skills directory.
# 把本仓库的技能安装到指定 Agent 的技能目录。
#
#   ./scripts/install.sh <skill|--all> [--tool claude|codex|cursor|gemini|agents] [--project] [--link]
#
#   --tool     target agent (default: claude)            目标工具，默认 claude
#   --project  install into ./<tool dir> instead of ~     装到当前项目而非全局
#   --link     symlink instead of copy (for development)  用软链接代替复制（开发时用）
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="claude"; SCOPE="user"; MODE="copy"; TARGETS=()

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --tool) TOOL="${2:-}"; shift 2 ;;
    --project) SCOPE="project"; shift ;;
    --link) MODE="link"; shift ;;
    --all) for d in "$REPO"/skills/*/; do TARGETS+=("$(basename "$d")"); done; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage 1 ;;
    *) TARGETS+=("$1"); shift ;;
  esac
done
[ ${#TARGETS[@]} -gt 0 ] || usage 1

case "$TOOL" in
  claude) SUB=".claude/skills" ;;
  codex|agents) SUB=".agents/skills" ;;
  cursor) SUB=".cursor/skills" ;;
  gemini) SUB=".gemini/skills" ;;
  *) echo "Unknown tool: $TOOL (claude|codex|cursor|gemini|agents)" >&2; exit 1 ;;
esac
if [ "$SCOPE" = "project" ]; then DEST="$PWD/$SUB"; else DEST="$HOME/$SUB"; fi
mkdir -p "$DEST"

for name in "${TARGETS[@]}"; do
  src="$REPO/skills/$name"
  [ -f "$src/SKILL.md" ] || { echo "✗ $name: no skills/$name/SKILL.md" >&2; exit 1; }
  if [ -e "$DEST/$name" ] || [ -L "$DEST/$name" ]; then
    echo "• $name: already exists at $DEST/$name — skipped (remove it first to reinstall)"
    continue
  fi
  if [ "$MODE" = "link" ]; then ln -s "$src" "$DEST/$name"; else cp -R "$src" "$DEST/$name"; fi
  echo "✓ $name → $DEST/$name ($MODE)"
done
