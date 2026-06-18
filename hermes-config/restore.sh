#!/usr/bin/env bash
#
# Hermes 2nd Brain — full restore script.
# Rebuilds the entire local Hermes setup from this backup repo:
#   - Hermes Agent (Python 3.13 venv)
#   - Hermes WebUI (nesquena/hermes-webui, Python 3.13 venv)
#   - qwen3.6 via local Ollama
#   - TARS identity (SOUL.md — this is the part everyone forgets)
#   - launchd auto-start for gateway + webui
#
# Run from the repo root:  ./hermes-config/restore.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HOME}/.hermes"
CONFIG_SRC="${REPO_DIR}/hermes-config/hermes"
PY="python3.13"

echo "==> Checking prerequisites"
command -v "$PY" >/dev/null || { echo "ERROR: python3.13 not found. brew install python@3.13"; exit 1; }
command -v ollama >/dev/null || { echo "ERROR: ollama not found. Install from https://ollama.com"; exit 1; }

echo "==> Pulling model: qwen3.6:latest"
ollama pull qwen3.6:latest

echo "==> Cloning Hermes Agent"
mkdir -p "$HERMES_HOME"
if [ ! -d "$HERMES_HOME/hermes-agent/.git" ]; then
  git clone https://github.com/NousResearch/hermes-agent.git "$HERMES_HOME/hermes-agent"
fi
echo "==> Building Hermes Agent venv (Python 3.13)"
cd "$HERMES_HOME/hermes-agent"
"$PY" -m venv venv
./venv/bin/pip install -q -e .
# MCP client SDK — required for any MCP server (context-a8c, notion, etc.)
./venv/bin/pip install -q mcp

echo "==> Restoring config, SOUL.md (TARS identity), and personas (before postinstall so setup is skipped)"
# SOUL.md is the PRIMARY identity. Without it you get stock 'Hermes', not TARS.
# This is NOT optional. Copy it every time. Restored here (before postinstall)
# so 'hermes postinstall' sees a valid config and does not drop into the
# interactive setup wizard.
cp "$CONFIG_SRC/config.yaml" "$HERMES_HOME/config.yaml"
cp "$CONFIG_SRC/SOUL.md"     "$HERMES_HOME/SOUL.md"
cp "$CONFIG_SRC/MEMORY.md"   "$HERMES_HOME/MEMORY.md" 2>/dev/null || true
mkdir -p "$HERMES_HOME/personas"
cp "$CONFIG_SRC/personas/"*.md "$HERMES_HOME/personas/"

echo "==> Bootstrapping non-Python deps (node/npx, browser, ripgrep, ffmpeg)"
# Creates ~/.hermes/node — provides npx, which context-a8c (stdio MCP) needs.
# Without this, npx-based MCP servers silently fail to spawn.
./venv/bin/hermes postinstall || echo "  (postinstall reported issues — check node: ls ~/.hermes/node/bin)"

echo "==> Linking 'hermes' onto PATH (~/.local/bin)"
mkdir -p "${HOME}/.local/bin"
ln -sf "$HERMES_HOME/hermes-agent/venv/bin/hermes" "${HOME}/.local/bin/hermes"

echo "==> Cloning Hermes WebUI"
if [ ! -d "$HERMES_HOME/webui/.git" ]; then
  git clone https://github.com/nesquena/hermes-webui.git "$HERMES_HOME/webui"
fi
echo "==> Building WebUI venv (Python 3.13) + installing agent editable into it"
cd "$HERMES_HOME/webui"
"$PY" -m venv venv
./venv/bin/pip install -q -r requirements.txt
# WebUI must import the agent — install it editable INTO the webui venv too.
./venv/bin/pip install -q -e "$HERMES_HOME/hermes-agent"
# MCP client SDK in the webui venv as well (it spawns MCP servers via the agent).
./venv/bin/pip install -q mcp

echo "==> Installing launchd services (gateway + webui auto-start)"
cp "${REPO_DIR}/hermes-config/launchd/com.hermes.gateway.plist" "${HOME}/Library/LaunchAgents/"
cp "${REPO_DIR}/hermes-config/launchd/com.hermes.webui.plist"   "${HOME}/Library/LaunchAgents/"

for svc in com.hermes.gateway com.hermes.webui; do
  launchctl bootout "gui/$(id -u)" "${HOME}/Library/LaunchAgents/${svc}.plist" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${HOME}/Library/LaunchAgents/${svc}.plist"
done

echo "==> Waiting for WebUI health"
sleep 5
if curl -s http://localhost:8787/health | grep -q '"status": "ok"'; then
  echo "==> SUCCESS. WebUI healthy at http://localhost:8787"
else
  echo "==> WARNING: WebUI health check did not return ok. Check /tmp/hermes-gateway.err"
fi

echo ""
echo "Done. Open http://localhost:8787 — you should be greeted by TARS, not Hermes."
echo "If it says 'Hermes', SOUL.md didn't land. Re-run: cp $CONFIG_SRC/SOUL.md $HERMES_HOME/SOUL.md && hermes gateway restart"
echo ""
echo "MCP servers (context-a8c, notion) are already enabled in config.yaml."
echo "tool_search is set to 'auto' with a 30% threshold (~58k tokens at 196k context)."
echo "OAuth tokens are per-machine and NOT in this backup. One manual step for Notion:"
echo "    export PATH=\"\$HOME/.hermes/node/bin:\$HOME/.local/bin:\$PATH\""
echo "    hermes mcp login notion     # opens browser (one-time)"
echo "    hermes mcp test notion      # expect: Connected, 16 tools"
echo "    hermes mcp test context-a8c # expect: Connected, self-auths"
echo "    hermes gateway restart      # pick up the new token"
echo "Then in the WebUI start a NEW chat (old sessions have a frozen toolset)."
