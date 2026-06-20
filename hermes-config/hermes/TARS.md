# TARS: My Local AI Agent Setup

## What It Is

TARS is a locally-running AI agent I named after the robot from *Interstellar*. It does whatever I tell it to, refuses to be dramatic about it, and occasionally surprises me with competence. It runs on my Mac, talks to nothing outside my network unless I tell it to, and is available 24/7 regardless of what Anthropic or OpenAI are doing with their uptime.

The name comes from a custom identity file (`~/.hermes/SOUL.md`) that gets loaded before anything else. Swap that file out and you get a different personality. Lose it during a reinstall and you'll spend twenty minutes wondering why your assistant keeps introducing itself as "Hermes." (This happened.)

## The Stack

| Layer | Tech | Notes |
|---|---|---|
| **Agent framework** | [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.16.0 | NousResearch's open-source agent runtime |
| **Model** | `qwen3.6:latest` | 128K context window, runs local via Ollama |
| **Inference** | [Ollama](https://ollama.com/) | Local model server, auto-starts via Homebrew |
| **Web UI** | [hermes-webui](https://github.com/nesquena/hermes-webui) | Chat interface at `http://localhost:8787` |
| **Runtime** | Python 3.13 | 3.14 breaks the agent; 3.13 is non-negotiable |
| **Auto-start** | launchd (macOS) | Two services: gateway + webui, both KeepAlive |

Everything runs native. No Docker, no cloud dependency, no monthly bill for the privilege of talking to myself.

## Why This Exists

Cloud AI is useful. It's also subject to rate limits at inconvenient times, logging conversations to servers I don't control, unavailable when I'm traveling somewhere with bad internet, and charging per token for things I'm going to ask fifty times.

TARS handles ambient, repetitive, or privacy-sensitive tasks. Things I don't want going through an API. Things I want an answer to at 6 AM before my coffee has kicked in. Daily briefings, quick lookups, context that lives on my machine and stays there.

It's not a replacement for Claude. It's the local agent doing the work that doesn't need to leave the house.

## MCP Integrations

I have two MCP servers wired in via `config.yaml`:

**context-a8c** is the Automattic internal MCP server. It gives TARS access to Linear, Slack, P2 blogs, and WordPress.com context. OAuth tokens are per-machine and not in the backup, so after a restore I re-auth manually. Takes thirty seconds.

**Notion** is enabled via a wrapper script (see Secrets Management below). The Notion MCP dumps about 50 tools into context at once and sends qwen3.6 into an unreliable spiral. To deal with this, `tools.tool_search.enabled` needs to stay at `off`. In `auto` mode, Hermes hides MCP tool schemas behind a meta-tool once context hits 10% usage, and qwen3.6 won't bother discovering them. The model just reports that it doesn't have the tool. Setting `tool_search` to `off` exposes all tools directly and the problem goes away.

## Secrets Management

API keys live in [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/), never in `config.yaml` or the backup repo. The setup has three layers.

**1. Bitwarden Secrets Manager (BWS)**

I store secrets in a BWS project called "AI Toolage". The `bws` CLI pulls them at runtime. A machine account access token is stored in the macOS login Keychain under the service name `bws_access_token`.

```bash
# List secrets (no values shown)
bw-secret list

# Fetch a specific value
bw-secret value NOTION_API_KEY
```

`bw-secret` is a thin helper script at `~/.local/bin/bw-secret` that reads the token from Keychain and wraps the `bws` CLI. It works fine interactively but can't be used from launchd because the Keychain isn't accessible in that environment without a login session.

**2. launchd plists carry the BWS access token**

Because launchd services run outside the login session, I inject the BWS access token directly into the plist `EnvironmentVariables`. This gives MCP wrapper scripts a way to call `bws` without going through Keychain:

```xml
<key>BWS_ACCESS_TOKEN</key>
<string>0.xxx...</string>
```

The BWS access token is a machine-scoped service account credential. That's exactly what it's designed for. It's not a user password. It's scoped read-only to one project and is revocable independently of everything else.

**3. MCP wrapper scripts fetch at spawn time**

MCP servers that need credentials don't get them via config. They get a wrapper script instead. The wrapper fetches the secret from BWS at startup, constructs the auth header, and execs the real binary:

```bash
NOTION_TOKEN="$(BWS_ACCESS_TOKEN="${BWS_ACCESS_TOKEN}" \
  /Users/mrchriswdixon/.local/bin/bws secret list --output json \
  | python3 -c '...')"
export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", ...}"
exec /Users/mrchriswdixon/.local/bin/notion-mcp-server "$@"
```

The Notion API key never touches disk. Rotating it in Bitwarden is the only thing that needs to happen. No config files, no plists, no restarts.

**After a restore**, the BWS access token needs to go back into the launchd plists manually (it's not in the backup, because that would defeat the point). I get it from vault.bitwarden.com, update both plists, then `bootout`/`bootstrap` to reload the environment.

## Config That Matters

```yaml
context_length: 65536   # qwen3.6 has 128K real; Hermes needs >=64K to boot
max_tokens: 8192        # higher values cause truncation-continuation loops, don't touch
provider: ollama        # NOT ollama-launch; that demands a fake API key
```

`SOUL.md` at `~/.hermes/SOUL.md` is what makes this TARS and not a generic chatbot. It's the first thing loaded, the most important file in the whole setup, and the one that's easiest to accidentally overwrite during a reinstall. The backup copy lives at `hermes-config/hermes/SOUL.md`.

## Backup and Restore

The GitHub repo ([chriswdixon/hermes-2nd-brain](https://github.com/chriswdixon/hermes-2nd-brain), private) is the backup. What's in it:

- Full `config.yaml` (no credentials; those are in Bitwarden)
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

That script rebuilds both Python venvs, pulls the qwen3.6 model, restores config and SOUL.md, and installs the launchd services. After that, I re-auth the MCP servers manually and put the BWS access token back in the plists.

## Things That Have Gone Wrong

**The wrong SOUL.md problem.** A fresh `hermes-agent` clone ships with a generic Hermes identity. If I don't overwrite `~/.hermes/SOUL.md` from the backup, I get "Hi, I'm Hermes!" instead of TARS. Obvious in retrospect.

**Python version.** The agent requires Python `<3.14`. The macOS default `python3` may be 3.14. I use 3.13 explicitly, everywhere, in both venvs.

**The webui venv.** The web UI's virtualenv needs the agent installed as an editable package or it throws "AIAgent not available" at runtime.

**Port confusion.** The web UI is on port `8787`. Port `9119` is the agent's own dashboard, which is a completely different thing.

**launchd PATH.** Both launchd plists need `~/.hermes/node/bin` on PATH explicitly, or npx-based MCP servers can't spawn. Easy to forget when writing a plist by hand.

**launchd doesn't reload plists on restart.** `hermes gateway restart` restarts the process but the service keeps its original environment. If I change anything in a plist, I have to `bootout` and `bootstrap` to force launchd to re-read it. This is not obvious and will make me think my changes aren't working when they just haven't been loaded yet.

**Use absolute paths in wrapper scripts.** `~` expands correctly in my terminal but may not resolve inside launchd subprocesses. Full paths only.

## Daily Briefings

TARS runs two scheduled morning briefings via Claude's scheduled-tasks system (not Hermes cron, which is a different thing). They send iMessages via AppleScript, pull my calendar data, Georgetown TX weather, and open Notion tasks. They only fire when the Mac is awake, which is a known limitation I've decided isn't worth solving.

To remove a scheduled task, I always use `delete_scheduled_task` via the MCP tool. Never `rm -rf` the task directory. The scheduler keeps a registry separate from the files, and deleting the files without updating the registry creates zombie tasks that show up in `list` but can't be recreated or removed cleanly.

---

That's the setup. It works, it survives reboots, and the restore path has been tested under pressure. Anything not documented here was either obvious or is now someone else's problem.
