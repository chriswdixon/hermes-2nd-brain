# TARS — Local AI Agent Setup

## What It Is

TARS is a locally-running AI agent named after the robot from *Interstellar* — mostly because it does whatever you tell it to, refuses to be dramatic about it, and occasionally surprises you with competence. It runs on my Mac, talks to nothing outside my network unless I tell it to, and is available 24/7 regardless of what Anthropic or OpenAI are doing with their uptime.

The name comes from a custom identity file (`~/.hermes/SOUL.md`) that gets loaded before anything else. Swap that file out, you get a different personality. Lose that file during a reinstall and spend twenty minutes wondering why your assistant keeps introducing itself as "Hermes." (This happened.)

## The Stack

| Layer | Tech | Notes |
|---|---|---|
| **Agent framework** | [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.16.0 | NousResearch's open-source agent runtime |
| **Model** | `qwen3.6:latest` | 128K context window, runs local via Ollama |
| **Inference** | [Ollama](https://ollama.com/) | Local model server, auto-starts via Homebrew |
| **Web UI** | [hermes-webui](https://github.com/nesquena/hermes-webui) | Chat interface at `http://localhost:8787` |
| **Runtime** | Python 3.13 | 3.14 breaks the agent; 3.13 is non-negotiable |
| **Auto-start** | launchd (macOS) | Two services: gateway + webui, both KeepAlive |

Everything runs native — no Docker, no cloud dependency, no monthly bill for the privilege of talking to myself.

## Why This Exists

Cloud AI is useful. It's also:
- Subject to rate limits at inconvenient times
- Logging conversations to servers I don't control
- Unavailable when I'm traveling somewhere with bad internet
- Charging per token for things I'm going to ask fifty times

TARS handles ambient, repetitive, or privacy-sensitive tasks. Things I don't want going through an API. Things I want an answer to at 6 AM before my coffee has kicked in. Daily briefings, quick lookups, context that lives on my machine and stays there.

It's not a replacement for Claude. It's the local agent doing the work that doesn't need to leave the house.

## MCP Integrations

TARS has two MCP servers wired in via `config.yaml`:

**context-a8c** — The Automattic internal MCP server. Gives TARS access to Linear, Slack, P2 blogs, and WordPress.com context. OAuth tokens are per-machine and not in the backup — after a restore you re-auth manually, which takes thirty seconds and is fine.

**Notion** — Enabled via a wrapper script (see Secrets Management below). The Notion MCP dumps ~50 tools into context at once and sends qwen3.6 into an unreliable spiral, so `tools.tool_search.enabled` must stay `auto` or `off` — if set to `auto`, Hermes hides MCP tool schemas behind a meta-tool past 10% context usage and qwen3.6 won't bother discovering them. The model will just tell you it doesn't have the tool. Turning `tool_search` off exposes all tools directly and the problem goes away.

## Secrets Management

API keys live in [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/), never in `config.yaml` or the backup repo. The setup has three layers:

**1. Bitwarden Secrets Manager (BWS)**

Secrets are stored in a BWS project called "AI Toolage". The `bws` CLI (`~/.local/bin/bws`) pulls them at runtime. A read-only machine account access token is stored in the macOS login Keychain under the service name `bws_access_token`.

```bash
# List secrets (no values shown)
bw-secret list

# Fetch a specific value
bw-secret value NOTION_API_KEY
```

`bw-secret` is a helper script at `~/.local/bin/bw-secret` that reads the access token from Keychain and wraps the `bws` CLI. It works fine interactively but can't be used from launchd (Keychain isn't accessible in that environment without a login session).

**2. launchd plists carry the BWS access token**

Because launchd services run outside the login session and can't touch the Keychain, the BWS access token is injected directly into the plist `EnvironmentVariables`. This gives MCP wrapper scripts a way to call `bws` without going through Keychain:

```xml
<key>BWS_ACCESS_TOKEN</key>
<string>0.xxx...</string>
```

The BWS access token is a machine-scoped service account credential — this is exactly what it's designed for. It's not a user password. It's scoped read-only to one project and is revocable.

**3. MCP wrapper scripts fetch at spawn time**

MCP servers that need credentials don't get them via config — they get a wrapper script instead. The wrapper fetches the secret from BWS at startup using the `BWS_ACCESS_TOKEN` from the environment, constructs the auth header, and execs the real binary:

```bash
# hermes-config/hermes/scripts/notion-mcp.sh
NOTION_TOKEN="$(BWS_ACCESS_TOKEN="${BWS_ACCESS_TOKEN}" \
  /Users/mrchriswdixon/.local/bin/bws secret list --output json \
  | python3 -c '...')"
export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", ...}"
exec /Users/mrchriswdixon/.local/bin/notion-mcp-server "$@"
```

The Notion API key never touches disk. Rotating it in Bitwarden is the only thing that needs to happen — no config files, no plists, no restarts required.

**After a restore**, the BWS access token needs to be put back into the launchd plists manually (it's not in the backup — that would defeat the point). Get it from vault.bitwarden.com or another machine's Keychain, then:

```bash
# Add to Keychain for interactive use
bw-secret set-token

# Update the plists
# Edit BWS_ACCESS_TOKEN in both:
# ~/Library/LaunchAgents/com.hermes.gateway.plist
# ~/Library/LaunchAgents/com.hermes.webui.plist

# Reload launchd (restart alone isn't enough — plist env won't update)
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.gateway.plist
```

Note: `hermes gateway restart` only restarts the process. It does NOT reload the plist environment. If you change anything in the plist, you must `bootout` and `bootstrap` — otherwise launchd keeps running the old environment and you'll spend an afternoon wondering why nothing works.

## Config That Matters

```yaml
context_length: 65536   # qwen3.6 has 128K real; Hermes needs >=64K to boot
max_tokens: 8192        # higher values cause truncation-continuation loops — don't touch
provider: ollama        # NOT ollama-launch; that demands a fake API key
```

`SOUL.md` at `~/.hermes/SOUL.md` is what makes this TARS and not a generic chatbot. It's the first thing loaded. It's the most important file in the whole setup. It's the one that's easiest to accidentally overwrite during a reinstall. The backup copy lives at `hermes-config/hermes/SOUL.md`.

## Backup and Restore

This repo is the backup. What's here:
- Full `config.yaml` (no credentials — those are in Bitwarden)
- `SOUL.md` (the TARS identity)
- Custom personas
- Qwen3 Modelfile
- MCP wrapper scripts (`hermes-config/hermes/scripts/`)
- A `restore.sh` script that does the full rebuild in one command

**To restore from scratch:**
```bash
git clone git@github.com:chriswdixon/hermes-2nd-brain.git
cd hermes-2nd-brain
./hermes-config/restore.sh
```

That script rebuilds both Python venvs, pulls the qwen3.6 model, restores config and SOUL.md, and installs the launchd services. After that, re-auth the MCP servers manually. OAuth tokens are explicitly not in the backup because they're scoped and machine-specific.

## Things That Have Gone Wrong (For Future Reference)

**The wrong SOUL.md problem.** Fresh `hermes-agent` clone ships with a generic Hermes identity. If you don't overwrite `~/.hermes/SOUL.md` from the backup, you get "Hi, I'm Hermes!" instead of TARS. The fix is obvious in retrospect. It wasn't obvious at the time.

**Python version.** The agent requires Python `<3.14`. macOS default `python3` may be 3.14. Use 3.13 explicitly, everywhere, in both venvs.

**The webui venv.** The web UI's virtualenv needs the agent installed as an editable package or you get "AIAgent not available" at runtime. This is in the restore script now. It wasn't the first time.

**Port confusion.** The web UI is on port `8787`. Port `9119` is the agent's own dashboard — a completely different thing.

**launchd PATH.** Both launchd plists need `~/.hermes/node/bin` on PATH explicitly, or npx-based MCP servers can't spawn. This is easy to forget when writing a plist by hand and costs about forty-five minutes to diagnose.

**launchd doesn't reload plists on restart.** `hermes gateway restart` restarts the process but the service keeps its original environment. If you change anything in a plist — env vars, paths, anything — you must `bootout` and `bootstrap` to force launchd to re-read it. This is not obvious and will make you think your changes aren't working when they just haven't been loaded yet.

**Use absolute paths in wrapper scripts.** `~` expands correctly in your terminal but may not resolve as expected inside launchd subprocesses. Use `/Users/mrchriswdixon/...` explicitly in any script that launchd spawns.

## Daily Briefings

TARS handles two scheduled morning briefings via Claude's scheduled-tasks system (not Hermes cron — different thing). These send iMessages via AppleScript to Messages.app and pull calendar data, Georgetown TX weather via `wttr.in`, and open Notion tasks. They only fire when the Mac is awake, which is a known limitation and not worth solving.

One important operational note: to remove a scheduled task, always use `delete_scheduled_task` via the MCP tool. Never `rm -rf` the task directory. The scheduler keeps a registry separate from the files, and deleting the files without touching the registry creates zombie tasks — they show up in `list`, they update `lastRunAt`, and they cannot be recreated because the registry already has an entry with that name. The fix is tedious. The prevention is free.

---

That's the setup. It works, it survives reboots, and the restore path has been tested under pressure. Anything that isn't documented here was either obvious or is now someone else's problem.
