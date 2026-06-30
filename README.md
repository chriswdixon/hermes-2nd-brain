# Hermes 2nd Brain Backup

Complete Hermes Agent setup: Anthropic Claude API (haiku-4-5), native WebUI, Gateway, and TARS personality. Auto-starts on reboot via launchd. Secrets managed via Bitwarden Secrets Manager and gateway token auth. Tasks backed by Obsidian vault, not Notion.

**Status:** Production-ready, auto-starting on reboot. Last updated: June 30, 2026.

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

Native macOS setup. No Docker. Two moving parts:

- **Hermes Agent** -- `~/.hermes/hermes-agent`, Python 3.13 venv
- **Hermes WebUI** ([nesquena/hermes-webui](https://github.com/nesquena/hermes-webui)) -- `~/.hermes/webui`, Python 3.13 venv, serves http://localhost:8787
- **Model:** Claude (haiku-4-5) via Anthropic API, with Ollama (qwen36) as fallback
- **Task storage:** Obsidian vault (`/Users/mrchriswdixon/Obsidian/SecondBrain`), not Notion

Identity is **TARS**, defined in `SOUL.md`. See the warning below.

### Key facts

| Thing | Correct value | Common wrong value |
|-------|---------------|--------------------|
| Model | `claude-haiku-4-5` | ~~qwen36~~ (fallback only) |
| Provider | `anthropic` | ~~ollama~~ (now fallback) |
| Context length | `131072` (Claude limit) | ~~65536~~ (that was Ollama) |
| WebUI port | `8787` | ~~9119~~ (that's the agent's own `hermes dashboard`) |
| Python | `3.13` | ~~3.14~~ (agent requires `<3.14`) |
| Identity source | `~/.hermes/SOUL.md` | ~~config.yaml personalities~~ (those feed the selector) |
| Services | `com.hermes.gateway`, `com.hermes.webui` | ~~com.hermes.agent~~ (removed) |
| Task CLI | `vault-tasks.py` (Obsidian) | ~~notion-mcp~~ (Notion retired) |

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

What's backed up (committed to git):
```
hermes-config/
├── restore.sh                    # Full rebuild script (start here)
├── hermes/
│   ├── config.yaml               # Agent config: Anthropic Claude, TARS personality
│   ├── cron-jobs.json            # Scheduled cron jobs (daily-brief, p2-monitor, etc)
│   ├── SOUL.md                   # TARS identity -- the primary persona source
│   ├── TARS.md                   # Full setup writeup
│   ├── MEMORY.md                 # Persistent memory snapshot
│   ├── scripts/                  # Automation: dual-brief.py, vault-tasks.py, etc
│   └── personas/                 # Persona reference docs
├── webui/                        # WebUI config snapshot
└── webui-docker/                 # Legacy Docker setup (kept for reference)
```

What's **NOT** in the repo (secrets, excluded by .gitignore):
- `~/.hermes/.env` (contains BWS_ACCESS_TOKEN)
- `~/.hermes/auth.json` (OAuth tokens)
- launchd plists (they contain BWS_ACCESS_TOKEN in EnvironmentVariables)
- model blobs (GGUF/BIN files)
- node_modules, venvs, session logs, cron output

## config.yaml -- the parts that matter

```yaml
model:
  provider: anthropic           # Primary provider
  default: claude-haiku-4-5
  context_length: 131072        # Claude limit
  max_tokens: 8192

fallback_providers:
- provider: ollama              # Fallback when Claude unavailable
  model: qwen36
  base_url: http://127.0.0.1:11434/v1
  api_key: ollama

toolsets:
- hermes-cli

mcp_servers:
  context-a8c:
    command: /Users/mrchriswdixon/.hermes/scripts/context-a8c.sh
    enabled: true
```

**Anthropic API:**
- Auth: token injected by gateway (no local config needed)
- Model: claude-haiku-4-5 (fast, cheap, good enough for most tasks)

**Obsidian tasks (no longer Notion):**
- Vault: `/Users/mrchriswdixon/Obsidian/SecondBrain`
- CLI: `python3 /Users/mrchriswdixon/.hermes/scripts/vault-tasks.py`
- Use: `add`, `list --open`, `set-status`, `done` (see config.yaml for full command reference)

## MCP Servers

| Server | Transport | Auth | Provides |
|--------|-----------|------|----------|
| `context-a8c` | wrapper script -> npx | OAuth (self-managed) | Linear, Slack, P2, WordPress.com |

**Note:** Notion MCP has been retired. Tasks are managed via local Obsidian vault instead (see Obsidian tasks section above).

### context-a8c setup

OAuth credentials are stored in `~/.hermes/auth.json`. First-time setup:
```bash
hermes mcp login context-a8c
```

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
| "Provider 'anthropic' ... error" | Bad or missing API key | Token should be injected by gateway; check `hermes mcp test` |
| "Model context window below 64K" | Gateway init validation | Claude is 131K; if using Ollama fallback, ensure `context_length: 65536` |
| "AIAgent not available" | WebUI venv missing agent | `~/.hermes/webui/venv/bin/pip install -e ~/.hermes/hermes-agent` |
| `requires a different Python: 3.14` | Wrong Python version | Rebuild venv with `python3.13` |
| MCP `requires the 'mcp' Python SDK` | SDK missing | `pip install mcp` in both venvs |
| npx MCP server won't spawn | launchd PATH missing node | Check plist PATH includes `~/.hermes/node/bin`; bootout/bootstrap |
| "Response remained truncated after 3 continuation attempts" | max_tokens too high | Set `max_tokens: 8192`; restart gateway |
| Plist change not taking effect | launchd cached old env | bootout/bootstrap both plists; `hermes gateway restart` is not enough |
| `vault-tasks.py: vault not found` | Wrong Obsidian path | Check `/Users/mrchriswdixon/Obsidian/SecondBrain` exists; see vault-tasks.py source |

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
