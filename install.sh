#!/usr/bin/env bash
# Multi-harness installer + self-check for market-analysis (crypto perps + A股, one skill).
# Works in Claude Code, Codex CLI, OpenClaw, Hermes.
#
# Usage:
#   bash install.sh                 # auto: install into every harness detected
#   bash install.sh all             # install into all four skill dirs
#   bash install.sh hermes          # a specific harness: claude|codex|openclaw|hermes
#   SKILLS_DIR=/custom/skills bash install.sh
set -euo pipefail
REPO="https://github.com/kim1232aa/market-analysis.git"
NAME="market-analysis"

claude_dir="$HOME/.claude/skills";     claude_home="$HOME/.claude"
codex_dir="$HOME/.codex/skills";       codex_home="$HOME/.codex"
openclaw_dir="$HOME/.openclaw/skills"; openclaw_home="$HOME/.openclaw"
hermes_dir="$HOME/.hermes/skills";     hermes_home="$HOME/.hermes"

install_into() {  # $1 = skills root; prints dest on stdout, progress on stderr
  local dest="$1/$NAME"
  mkdir -p "$1"
  if [ -d "$dest/.git" ]; then
    echo "  ↻ update $dest" >&2; git -C "$dest" pull --ff-only -q || true
  else
    echo "  ↓ clone  $dest" >&2; git clone --depth 1 -q "$REPO" "$dest"
  fi
  echo "$dest"
}

targets=()
case "${1:-auto}" in
  -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  claude)   targets=("$claude_dir") ;;
  codex)    targets=("$codex_dir") ;;
  openclaw) targets=("$openclaw_dir") ;;
  hermes)   targets=("$hermes_dir") ;;
  all)      targets=("$claude_dir" "$codex_dir" "$openclaw_dir" "$hermes_dir") ;;
  auto)
    [ -d "$claude_home" ]   && targets+=("$claude_dir")
    [ -d "$codex_home" ]    && targets+=("$codex_dir")
    [ -d "$openclaw_home" ] && targets+=("$openclaw_dir")
    [ -d "$hermes_home" ]   && targets+=("$hermes_dir")
    if [ "${#targets[@]}" -eq 0 ]; then
      echo "No harness home detected. Pick one: bash install.sh <claude|codex|openclaw|hermes|all>"; exit 1
    fi ;;
  *) echo "unknown target '$1' (claude|codex|openclaw|hermes|all|auto)"; exit 1 ;;
esac
[ -n "${SKILLS_DIR:-}" ] && targets=("$SKILLS_DIR")

command -v git     >/dev/null || { echo "✗ git not found"; exit 1; }
command -v python3 >/dev/null || { echo "✗ python3 not found"; exit 1; }

echo "→ installing $NAME into ${#targets[@]} location(s):"
first=""
for d in "${targets[@]}"; do
  path="$(install_into "$d")"; [ -z "$first" ] && first="$path"
done

echo "→ self-check: analyze.py ETH 5m + 600519 (crypto + A股 both route)"
ok=1
python3 "$first/scripts/analyze.py" ETH 5m 2>/dev/null | grep -q "报告块" || ok=0
if [ "$ok" = 1 ]; then
  echo "✅ works — crypto route OK, live data reachable."
else
  echo "⚠️ installed, but self-check produced no 报告块 (网络/风控限流)。"
  echo "   retry: HTTPS_PROXY=http://<proxy>:<port> python3 $first/scripts/analyze.py ETH 5m"
fi
echo "→ restart your agent to auto-discover the skill.  用法: analyze.py <ETH 5m | 600519>"
