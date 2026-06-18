# Hermes 2nd Brain Backup

Complete local Hermes Agent v0.16.0 setup: Ollama (qwen3-fast), native WebUI, Gateway, and TARS personality. Auto-starts on reboot via launchd.

**Status:** Production-ready, auto-starting on reboot.

## TL;DR — Restore Everything

```bash
git clone https://github.com/chriswdixon/hermes-2nd-brain.git
cd hermes-2nd-brain
./hermes-config/restore.sh
```

That script rebuilds the agent, the WebUI, the venvs, the model, the config, the TARS identity, and the launchd services — then health-checks the result. If you only read one thing, read that.

## Current Architecture (what's actually running)

This is a **native macOS setup** — not Docker. Three moving parts:

- **Hermes Agent v0.16.0** — `~/.hermes/hermes-agent`, Python **3.13** venv
- **Hermes WebUI** ([nesquena/hermes-webui](https://github.com/nesquena/hermes-webui)) — `~/.hermes/webui`, Python **3.13** venv, serves http://localhost:8787
- **Ollama** — running `qwen3-fast:latest` on http://127.0.0.1:11434

Identity is **TARS**, defined in `SOUL.md` (see the warning below — this is the part that breaks).

### Key facts (these bit us; don't relearn them the hard way)

| Thing | Correct value | Common wrong value |
|-------|---------------|--------------------|
| Model | `qwen3-fast` | ~~qwen3.6~~ (23GB; overkill for this setup) |
| Provider | `ollama` | ~~ollama-launch~~ (needs an API key that doesn't exist) |
| WebUI port | `8787` | ~~9119~~ (that's the agent's own `hermes dashboard`, different thing) |
| Python | `3.13` | ~~3.14~~ (agent requires `<3.14`) |
| Identity source | `~/.hermes/SOUL.md` | ~~config.yaml personalities~~ (those feed the selector, NOT the default identity) |
| Services | `com.hermes.gateway`, `com.hermes.webui` | ~~com.hermes.agent~~ (removed — that was `ollama launch`) |

### ⚠️ SOUL.md is the identity. It is NOT optional.

The agent's primary identity comes from `~/.hermes/SOUL.md`, loaded before anything in `config.yaml`. A fresh `git clone` of hermes-agent ships a generic Hermes `SOUL.md`. **If you forget to overwrite it with the TARS one from this repo, you get "I'm Hermes! How can I help?" instead of TARS** — and you'll waste an hour editing config keys that do nothing. The `persona_prompt_file` key under `agent:` is a TTS setting and has zero effect on the chat persona. Don't chase it.

The backup TARS `SOUL.md` lives at `hermes-config/hermes/SOUL.md`. Restore it every time.

## Running Services

```bash
# Status
launchctl list | grep hermes
# Expect: com.hermes.gateway, com.hermes.webui, ai.hermes.gateway

# Health
curl -s http://localhost:8787/health   # -> "status": "ok"

# Logs
tail -f /tmp/hermes-gateway.err
tail -f /tmp/hermes-webui-launcher.err
```

### Restart

```bash
# Gateway (preferred — it manages its own supervised restart)
hermes gateway restart

# Either service via launchd
for s in com.hermes.gateway com.hermes.webui; do
  launchctl bootout  "gui/$(id -u)" ~/Library/LaunchAgents/$s.plist 2>/dev/null
  launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/$s.plist
done
```

> Don't start a gateway by hand with `hermes gateway run` while the launchd one is alive — it refuses, and forcing it leaves an orphan that can corrupt the kanban DB. Use `hermes gateway restart`.

## Repo Contents

```
hermes-config/
├── restore.sh                 # Full rebuild script (start here)
├── hermes/
│   ├── config.yaml            # Agent config: qwen3-fast via ollama, TARS default
│   ├── SOUL.md                # TARS identity — THE primary persona source
│   ├── MEMORY.md              # Persistent memory snapshot
│   └── personas/              # Persona reference docs
│       ├── persona.md         #   full TARS definition
│       ├── agent-persona.md
│       └── tars-personality.md
├── launchd/                   # Auto-start services (macOS)
│   ├── com.hermes.gateway.plist
│   └── com.hermes.webui.plist
├── models/
│   └── qwen3-fast.Modelfile   # Active model definition — run `ollama create qwen3-fast -f` to rebuild
└── webui-docker/              # Legacy Docker setup (unused; kept for reference)
```

## Manual Restore (if you don't trust the script)

```bash
# 0. Prereqs
brew install python@3.13 ollama
ollama pull qwen3-fast:latest

# 1. Agent
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
python3.13 -m venv venv && ./venv/bin/pip install -e .
./venv/bin/pip install mcp          # MCP client SDK (both venvs need it)

# 2. Config + identity (SOUL.md is mandatory — see warning above)
#    Do this BEFORE postinstall so the setup wizard is skipped.
cp hermes-config/hermes/config.yaml ~/.hermes/config.yaml
cp hermes-config/hermes/SOUL.md     ~/.hermes/SOUL.md
mkdir -p ~/.hermes/personas
cp hermes-config/hermes/personas/*.md ~/.hermes/personas/

# 3. Non-Python deps + PATH link
#    postinstall creates ~/.hermes/node (provides npx for context-a8c) plus
#    browser/ripgrep/ffmpeg. Without it, npx-based MCP servers can't spawn.
./venv/bin/hermes postinstall
mkdir -p ~/.local/bin
ln -sf ~/.hermes/hermes-agent/venv/bin/hermes ~/.local/bin/hermes

# 4. WebUI (install the agent editable INTO the webui venv — it imports it)
git clone https://github.com/nesquena/hermes-webui.git ~/.hermes/webui
cd ~/.hermes/webui
python3.13 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -e ~/.hermes/hermes-agent
./venv/bin/pip install mcp

# 6. Auto-start
cp hermes-config/launchd/*.plist ~/Library/LaunchAgents/
for s in com.hermes.gateway com.hermes.webui; do
  launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/$s.plist
done

# 7. Verify + one-time Notion OAuth (token is per-machine, not in backup)
sleep 5 && curl -s http://localhost:8787/health
export PATH="$HOME/.hermes/node/bin:$HOME/.local/bin:$PATH"
hermes mcp login notion && hermes gateway restart
```

## config.yaml — the parts that matter

```yaml
agent:
  default_model: qwen3-fast
  personality: tars          # selects from personalities{} for the picker;
                             # the ACTUAL default identity is SOUL.md
  personalities:
    tars: "..."              # short TARS blurb for the selector
    helpful: "..."
  max_turns: 60
model:
  provider: ollama           # NOT ollama-launch
  base_url: http://127.0.0.1:11434/v1
  api_key: ollama
  default: qwen3-fast
  context_length: 65536      # override: real window is 40960 but Hermes requires ≥64K to boot
  max_tokens: 8192           # must be well below context_length; 32768 caused truncation loops
```

## MCP Servers

Two are configured in `config.yaml`:

| Server | Transport | Auth | Provides |
|--------|-----------|------|----------|
| `context-a8c` | `npx @automattic/mcp-context-a8c` | self-managed | Linear, Slack, P2, WordPress.com (via load-provider / execute-tool) |
| `notion` | `https://mcp.notion.com/mcp` | OAuth (browser) | Notion search / pages / databases |

> **⚠️ Notion integration: use `ntn` CLI, NOT the MCP server.** The Notion MCP (both the `mcp.notion.com/mcp` remote and the `@notionhq/notion-mcp-server` local npx variant) exposes ~50 tools and floods the context window regardless of `tool_search` settings. qwen3-fast handles this poorly and becomes unreliable. The working approach is the `ntn` Notion CLI as a Hermes skill — set `NOTION_API_KEY` in the environment and let the model call it as a shell command. The Notion MCP config blocks in `config.yaml` are kept for reference but should remain disabled.

Two non-obvious requirements, both now handled by `restore.sh`:

1. **`mcp` Python SDK** must be installed in **both** venvs (agent + webui), or you get `requires the 'mcp' Python SDK`. `pip install mcp`.
2. **The gateway needs `npx` on its PATH.** launchd runs with a minimal PATH, so the gateway plist sets `PATH` to include `~/.hermes/node/bin`. Without it, npx-based servers (context-a8c) silently fail to spawn.

### ⚠️ tool_search deferral hides MCP tools from the model

`config.yaml` sets `tools.tool_search.enabled: "off"`. **Do not set it back to `auto`.** In `auto` mode, once tool schemas exceed ~10% of context, Hermes *defers* the MCP tools behind a `tool_search` meta-tool — the model has to "search" for them instead of seeing them directly. qwen3-fast doesn't reliably use that indirection, so it reports "I don't have a notion tool" even though the tools loaded fine. `"off"` exposes all ~48 tools directly.

Symptom if this regresses: `hermes mcp test notion` works, the tools show enabled, but the chat model insists it can't see them.

**OAuth tokens are per-machine and are NOT in this backup.** After a restore, authenticate interactively (needs a terminal + browser):

```bash
export PATH="$HOME/.hermes/node/bin:$HOME/.local/bin:$PATH"
hermes mcp login notion        # opens browser for OAuth
hermes mcp test context-a8c    # verify (self-auths)
hermes mcp list                # check enabled/disabled
hermes mcp configure notion    # enable once authenticated
```

`notion` ships **disabled** in the backup config because it can't connect until you've logged in. Enable it after `hermes mcp login notion` succeeds.

## Model Notes

`qwen3-fast:latest` is a custom Ollama model built from the Modelfile at `hermes-config/models/qwen3-fast.Modelfile`. It's a lighter/faster quantization than `qwen3.6` (5.2GB vs 23GB). The model's actual context window is **40,960 tokens** — below Hermes's 64K minimum gate, so `config.yaml` sets `context_length: 65536` to bypass the check. This is intentional and harmless; Ollama will still cap at 40960 internally.

**Critical: set `max_tokens: 8192`**, not the default 32768. With a 40K context window, a 32K `max_tokens` leaves almost no room for the prompt, and Hermes enters an endless truncation-continuation loop (`Response remained truncated after 3 continuation attempts`). 8192 is a safe ceiling.

```bash
# Build or rebuild the model from the Modelfile
ollama create qwen3-fast -f hermes-config/models/qwen3-fast.Modelfile
hermes gateway restart

# Or update the base model and rebuild
ollama pull qwen3:latest
ollama create qwen3-fast -f hermes-config/models/qwen3-fast.Modelfile
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "I'm Hermes! How can I help?" | Stock SOUL.md | `cp hermes-config/hermes/SOUL.md ~/.hermes/SOUL.md && hermes gateway restart` |
| "Provider 'ollama-launch' ... no API key" | Wrong provider in config | Set `provider: ollama`, restart gateway |
| "No LLM provider configured" | Gateway running stale config | `hermes gateway restart` |
| "AIAgent not available -- check sys.path" | WebUI venv missing the agent | `~/.hermes/webui/venv/bin/pip install -e ~/.hermes/hermes-agent` |
| `requires a different Python: 3.14` | venv built with 3.14 | Rebuild venv with `python3.13` |
| MCP `requires the 'mcp' Python SDK` | SDK missing from venv | `~/.hermes/{hermes-agent,webui}/venv/bin/pip install mcp` |
| npx-based MCP server won't spawn under gateway | launchd minimal PATH lacks npx | gateway plist sets `PATH` incl. `~/.hermes/node/bin`; restart gateway |
| MCP OAuth "non-interactive environment" | No cached token | Run `hermes mcp login <name>` in a real terminal |
| Model says "I don't have a notion tool" but `mcp test` works | `tool_search` deferring MCP tools | Set `tools.tool_search.enabled: "off"`, restart gateway + webui |
| context-a8c won't spawn in webui chat | webui plist PATH lacks npx | webui plist `PATH` includes `~/.hermes/node/bin`; restart webui |
| WebUI 500 / blank | `ctl.sh` can't find python | launchd plist runs `webui/venv/bin/python server.py` directly (see `hermes-config/launchd/`) |
| `exit status 126` on `ollama launch` | Gateway service issue | Check `/tmp/hermes-gateway.err`, then `hermes gateway restart` |
| "Response remained truncated after 3 continuation attempts" | `max_tokens` too high relative to context window | Set `max_tokens: 8192` in config (both top-level and `model:` block); restart gateway |
| "Model has context window below minimum 64,000 required" | Hermes boot gate rejects small models | Set `model.context_length: 65536` in config to override; Ollama still caps at real limit |

## Backup Your Changes

```bash
cd ~/.hermes
# Live files are synced into the backup tree before committing:
cp config.yaml hermes-config/hermes/config.yaml
cp SOUL.md     hermes-config/hermes/SOUL.md
cp ~/Library/LaunchAgents/com.hermes.*.plist hermes-config/launchd/
git add -A && git commit -m "Update Hermes config" && git push
```

## Security

The `.gitignore` blocks `.env`, keys, tokens, model blobs, and runtime state (`state.db`, `kanban.db`, sessions, logs). Review it before adding files. Never commit credentials.

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) · [docs](https://hermes-agent.nousresearch.com/)
- [Hermes WebUI (nesquena)](https://github.com/nesquena/hermes-webui)
- [Ollama](https://ollama.com/)

## Notes

- Native launchd setup (Docker dir kept only for reference).
- Two venvs, both Python 3.13: one for the agent, one for the webui (which also has the agent installed editable so it can import it).
- WebUI password auth is off (localhost only).
