---
name: hermes_2nd_brain_setup
description: "Complete Hermes Agent local setup with Ollama, auto-start, and GitHub backup"
metadata: 
  node_type: memory
  type: project
  originSessionId: 23821f6d-11d4-4898-9ba1-8c26173e3681
---

## Hermes 2nd Brain — Complete Local Setup

**Status:** Fully operational, auto-starting on reboot.

### Running Configuration

- **Agent:** Hermes Agent v0.16.0
- **LLM:** Qwen3-fast (32K context, local Ollama)
- **Location:** ~/.hermes (all config, sessions, state)
- **Personalities:** 13 modes (tars, noir, pirate, etc.) + custom SOUL.md
- **Model:** qwen3-fast via http://127.0.0.1:11434/v1
- **MCP:** context-a8c configured (Linear, Slack, P2, WordPress.com)

### Auto-Start

Launchd service: `com.hermes.agent`
- Starts `ollama launch hermes --model qwen3-fast` on boot
- Logs to `/tmp/hermes.out` and `/tmp/hermes.err`
- Restarts if it exits

Verify: `launchctl list | grep hermes`

### GitHub Backup

[hermes-2nd-brain](https://github.com/chriswdixon/hermes-2nd-brain) (private)

Contains:
- Full config.yaml (all personalities, agent settings, toolsets)
- Custom personas (tars-personality.md, etc.)
- Docker Compose setup (with published image)
- Qwen3-fast Modelfile
- Context-a8c MCP configuration
- Comprehensive README with deployment guide

**To restore:** `git clone git@github.com:chriswdixon/hermes-2nd-brain.git && cp -r hermes-config/* ~/.hermes/`

### Installation Details

**Hermes binary:** `~/.hermes/hermes-agent/venv/bin/hermes`
- Python 3.13 venv
- Wrapper at `~/.local/bin/hermes`
- Installed from NousResearch/hermes-agent GitHub repo

**Ollama:** Local serve running on http://127.0.0.1:11434
- qwen3-fast model (custom Ollama Modelfile)
- qwen3.6 model also available
- Auto-starts via Homebrew brew service

### Access

```bash
# Interactive CLI
ollama launch hermes --model qwen3-fast

# Or direct
hermes

# SSH to localhost (for Hermes Desktop)
ssh localhost whoami
# Uses key-based auth: ~/.ssh/id_ed25519
```

### Skills & Plugins

- CLI and web toolsets enabled by default
- No skills installed by default (can be enabled in config)
- Plugins list empty (can add integrations via config.yaml)
- Computer use, code execution, browser tools available

### Sessions & Data

All stored in ~/.hermes/:
- `sessions/` — saved chat sessions
- `cron/` — scheduled tasks
- `memories/` — persistent context
- `config.yaml` — main config

### Useful Workflows

1. **Start Hermes:** `ollama launch hermes --model qwen3-fast`
2. **Check status:** `launchctl list | grep hermes`
3. **View logs:** `cat /tmp/hermes.out /tmp/hermes.err`
4. **Restart service:** `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hermes.agent.plist && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hermes.agent.plist`
5. **Update config:** Edit ~/.hermes/config.yaml, restart with launchctl

### Environment Variables

Located in ~/.hermes/webui-docker/.env (for Docker setup if needed)
- LLM providers: OpenRouter, Anthropic, Google Gemini, etc. (all optional)
- TTS/STT providers (currently not configured)
- Discord, Slack, Teams integrations (not enabled)

### Notes

- Hermes Desktop (macOS app) is built and installed but requires SSH daemon running + passwordless key auth (done)
- Docker setup available in backup but using native Ollama instead for simplicity
- Auto-start works reliably — survives reboots and crashes (KeepAlive: true)
- Config mirrors what was running before the reboot that broke the installation
