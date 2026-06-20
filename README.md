# Hermes 2nd Brain Backup

Complete local Hermes Agent v0.16.0 setup: Ollama (qwen3.6), native WebUI, Gateway, and TARS personality. Auto-starts on reboot via launchd. API keys stored in Bitwarden Secrets Manager.

**Status:** Production-ready, auto-starting on reboot.

## TL;DR -- Restore Everything

```bash
git clone git@github.com:chriswdixon/hermes-2nd-brain.git
cd hermes-2nd-brain
./hermes-config/restore.sh
```

That script rebuilds the agent, the WebUI, the venvs, the model, the config, the TARS identity, and the launchd services, then health-checks the result. If you only read one thing, read that.

After restore, two manual steps:
1. Put the BWS access token back in both launchd plists (see Secrets Management below)
2. Re-auth context-a8c: `hermes mcp login context-a8c`

## Current Architecture

Native macOS setup. No Docker. Three moving parts:

- **Hermes Agent v0.16.0** -- `~/.hermes/hermes-agent`, Python 3.13 venv
- **Hermes WebUI** ([nesquena/hermes-webui](https://github.com/nesquena/hermes-webui)) -- `~/.hermes/webui`, Python 3.13 venv, serves http://localhost:8787
- **Ollama** -- running `qwen3.6:latest` on http://127.0.0.1:11434

Identity is **TARS**, defined in `SOUL.md`. See the warning below.

### Key facts

| Thing | Correct value | Common wrong value |
|-------|---------------|--------------------|
| Model | `qwen36` (qwen3.6:latest) | ~~qwen3-fast~~ (removed; context window too small) |
| Provider | `ollama` | ~~ollama-launch~~ (demands a nonexistent API key) |
| WebUI port | `8787` | ~~9119~~ (that's the agent's own `hermes dashboard`, different thing) |
| Python | `3.13` | ~~3.14~~ (agent requires `<3.14`) |
| Identity source | `~/.hermes/SOUL.md` | ~~config.yaml personalities~~ (those feed the selector, not the default identity) |
| Services | `com.hermes.gateway`, `com.hermes.webui` | ~~com.hermes.agent~~ (removed) |
| tool_search | `auto` | ~~off~~ (only needed if Notion MCP floods context) |

### SOUL.md is the identity. It is not optional.

The agent's primary identity comes from `~/.hermes/SOUL.md`, loaded before anything in `config.yaml`. A fresh `git clone` of hermes-agent ships a generic Hermes `SOUL.md`. If you forget to overwrite it with the TARS one from this repo, you get "I'm Hermes! How can I help?" instead of TARS. The `persona_prompt_file` key under `agent:` is a TTS setting and has zero effect on the chat persona.

The backup TARS `SOUL.md` lives at `hermes-config/hermes/SOUL.md`. Restore it every time.

## Secrets Management

API keys live in Bitwarden Secrets Manager, never in `config.yaml` or this repo. Three layers:

**1. Bitwarden Secrets Manager (BWS)**

Secrets are in a BWS project called "AI Toolage". The `bws` CLI pulls them at runtime. The machine account access token lives in the macOS login Keychain under `bws_access_token`.

```bash
bw-secret list                    # list secrets by name (no values)
bw-secret value NOTION_API_KEY    # fetch a value
```

`bw-secret` works fine interactively but cannot be used from launchd -- the Keychain is not accessible without a login session.

**2. launchd plists carry the BWS access token**

Because launchd runs outside the login session, the BWS access token is injected directly into both plists under `EnvironmentVariables`:

```xml
<key>BWS_ACCESS_TOKEN</key>
<string>0.xxx...</string>
```

This is not in the backup. After a restore, get the token from vault.bitwarden.com and add it to both plists manually, then reload (see below).

**3. MCP wrapper scripts fetch secrets at spawn time**

MCP servers that need credentials use wrapper scripts instead of config entries. The wrapper fetches the secret from BWS using `BWS_ACCESS_TOKEN` from the environment and execs the real binary. The API key never touches disk.

See `hermes-config/hermes/scripts/notion-mcp.sh` for the pattern.

### Reloading launchd after plist changes

`hermes gateway restart` restarts the process but does NOT reload the plist environment. If you change anything in a plist, you must bootout and bootstrap:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist

launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hermes.webui.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.webui.plist
```

Verify the environment loaded:

```bash
launchctl print gui/$(id -u)/com.hermes.gateway | grep BWS
```

## Running Services

```bash
# Status
launchctl list | grep hermes

# Health
curl -s http://localhost:8787/health

# Logs
tail -f /tmp/hermes-gateway.err
tail -f /tmp/hermes-webui-launcher.err
```

### Restart

```bash
# Process only (plist env unchanged)
hermes gateway restart

# Full reload (use this after plist changes)
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist
```

## Repo Contents

```
hermes-config/
├── restore.sh                   # Full rebuild script (start here)
├── hermes/
│   ├── config.yaml              # Agent config: qwen3.6 via ollama, TARS default
│   ├── SOUL.md                  # TARS identity -- the primary persona source
│   ├── TARS.md                  # Full setup writeup / blog post draft
│   ├── MEMORY.md                # Persistent memory snapshot
│   ├── scripts/
│   │   └── notion-mcp.sh        # Notion MCP wrapper (fetches key from BWS at spawn)
│   └── personas/                # Persona reference docs
├── launchd/                     # Auto-start services (macOS)
│   ├── com.hermes.gateway.plist
│   └── com.hermes.webui.plist
├── models/
│   └── qwen3-fast.Modelfile     # Legacy model (kept for reference; qwen3.6 is current)
└── webui-docker/                # Legacy Docker setup (unused; kept for reference)
```

## config.yaml -- the parts that matter

```yaml
model:
  provider: ollama           # NOT ollama-launch
  base_url: http://127.0.0.1:11434/v1
  api_key: ollama
  default: qwen36
  context_length: 65536      # qwen3.6 has 128K real; Hermes requires >=64K to boot
  max_tokens: 8192           # higher causes truncation-continuation loops

mcp_servers:
  context-a8c:
    command: /Users/mrchriswdixon/.hermes/scripts/context-a8c.sh
    enabled: true
  notion:
    command: /Users/mrchriswdixon/.hermes/scripts/notion-mcp.sh
    enabled: true
```

## MCP Servers

| Server | Transport | Auth | Provides |
|--------|-----------|------|----------|
| `context-a8c` | wrapper script -> npx | OAuth (self-managed) | Linear, Slack, P2, WordPress.com |
| `notion` | wrapper script -> notion-mcp-server | API key via BWS | Notion pages, databases, search |

### Notion MCP gotcha

The Notion MCP dumps ~50 tools into context at once. With `tools.tool_search.enabled: auto`, Hermes defers those schemas behind a meta-tool once context hits 10% usage. qwen3.6 won't use the indirection and reports "I don't have a notion tool." Setting `tool_search` to `off` exposes all tools directly. Current config leaves it at `auto` -- switch to `off` if Notion stops responding.

### context-a8c gotcha

Both launchd plists need `~/.hermes/node/bin` on PATH explicitly or npx can't spawn. This is already in the plists. Don't remove it.

## Manual Restore (if you don't trust the script)

```bash
# 0. Prereqs
brew install python@3.13 ollama
ollama pull qwen3.6:latest

# 1. Agent
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
python3.13 -m venv venv && ./venv/bin/pip install -e .
./venv/bin/pip install mcp

# 2. Config + identity (SOUL.md is mandatory -- do this before postinstall)
cp hermes-config/hermes/config.yaml ~/.hermes/config.yaml
cp hermes-config/hermes/SOUL.md ~/.hermes/SOUL.md
mkdir -p ~/.hermes/personas
cp hermes-config/hermes/personas/*.md ~/.hermes/personas/

# 3. Non-Python deps + PATH link
./venv/bin/hermes postinstall
mkdir -p ~/.local/bin
ln -sf ~/.hermes/hermes-agent/venv/bin/hermes ~/.local/bin/hermes

# 4. MCP wrapper scripts
mkdir -p ~/.hermes/scripts
cp hermes-config/hermes/scripts/*.sh ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*.sh

# 5. WebUI
git clone https://github.com/nesquena/hermes-webui.git ~/.hermes/webui
cd ~/.hermes/webui
python3.13 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -e ~/.hermes/hermes-agent
./venv/bin/pip install mcp

# 6. Auto-start
# Plists are not in the repo (they contain BWS_ACCESS_TOKEN).
# Copy them from a local backup, or recreate them and add BWS_ACCESS_TOKEN
# manually before loading. Get the token from vault.bitwarden.com.
for s in com.hermes.gateway com.hermes.webui; do
  launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/$s.plist
done

# 7. Verify
sleep 5 && curl -s http://localhost:8787/health
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "I'm Hermes! How can I help?" | Stock SOUL.md | `cp hermes-config/hermes/SOUL.md ~/.hermes/SOUL.md && hermes gateway restart` |
| "Provider 'ollama-launch' ... no API key" | Wrong provider | Set `provider: ollama`, restart gateway |
| "AIAgent not available" | WebUI venv missing agent | `~/.hermes/webui/venv/bin/pip install -e ~/.hermes/hermes-agent` |
| `requires a different Python: 3.14` | Wrong Python version | Rebuild venv with `python3.13` |
| MCP `requires the 'mcp' Python SDK` | SDK missing | `pip install mcp` in both venvs |
| npx MCP server won't spawn | launchd PATH missing node | Check plist PATH includes `~/.hermes/node/bin`; bootout/bootstrap |
| Notion MCP "I don't have that tool" | tool_search deferring schemas | Set `tools.tool_search.enabled: "off"`, restart gateway |
| Notion MCP 401 | Stale or rotated API key in BWS | Update `NOTION_API_KEY` in Bitwarden; restart gateway |
| Notion MCP "Doesn't contain a decryption key" | BWS_ACCESS_TOKEN missing from launchd env | Add token to plist, bootout/bootstrap (not just restart) |
| Plist change not taking effect | launchd cached old env | bootout/bootstrap both plists; `hermes gateway restart` is not enough |
| "Response remained truncated after 3 continuation attempts" | max_tokens too high | Set `max_tokens: 8192`; restart gateway |
| "Model has context window below minimum 64,000" | Hermes boot gate | Set `model.context_length: 65536`; Ollama still caps at real limit |

## Backup Your Changes

```bash
cp ~/.hermes/config.yaml hermes-config/hermes/config.yaml
cp ~/.hermes/SOUL.md hermes-config/hermes/SOUL.md
git add -A && git commit -m "Update config" && git push
```

The launchd plists are intentionally excluded from the repo -- they contain the BWS access token. Keep a local copy somewhere safe (1Password, another encrypted store) or just re-fetch the token from vault.bitwarden.com after a restore.

## Links

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Hermes WebUI](https://github.com/nesquena/hermes-webui)
- [Ollama](https://ollama.com/)
- [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/)
