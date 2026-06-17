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

echo "==> Restoring config, SOUL.md (TARS identity), and personas"
# SOUL.md is the PRIMARY identity. Without it you get stock 'Hermes', not TARS.
# This is NOT optional. Copy it every time.
cp "$CONFIG_SRC/config.yaml" "$HERMES_HOME/config.yaml"
cp "$CONFIG_SRC/SOUL.md"     "$HERMES_HOME/SOUL.md"
cp "$CONFIG_SRC/MEMORY.md"   "$HERMES_HOME/MEMORY.md" 2>/dev/null || true
mkdir -p "$HERMES_HOME/personas"
cp "$CONFIG_SRC/personas/"*.md "$HERMES_HOME/personas/"

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
