# Hermes 2nd Brain Backup

Complete local Hermes Agent v0.16.0 setup with Ollama, WebUI, Gateway, and team context access.

**Status:** Production-ready, auto-starting on reboot.

## Quick Summary

This is a complete Hermes setup running on macOS with:

- **Hermes Agent v0.16.0** — Local AI agent with Ollama (qwen3-fast, 65K context)
- **Hermes WebUI** — Web interface at http://localhost:8787
- **Hermes Gateway** — Enables WebUI + scheduled jobs (cron)
- **MCP (context-a8c)** — Access to Linear, Slack, P2, WordPress.com
- **Auto-start** — All services start on reboot via launchd
- **App Icon** — Hermes WebUI clickable app in Applications/Dock

### Running Services

```bash
# Check service status
launchctl list | grep hermes

# View logs
tail -f ~/.hermes/logs/gateway.log      # Gateway
tail -f ~/.hermes/webui/bootstrap-8787.log  # WebUI
cat /tmp/hermes-stdout.log              # Agent
```

### Access

- **CLI:** `hermes` or `ollama launch hermes --model qwen3-fast`
- **WebUI:** http://localhost:8787 (click app in Dock or Applications)
- **Gateway:** Running on http://127.0.0.1:8000 (internal)

## Contents

```
hermes-config/
├── hermes/                    # Agent configuration
│   ├── config.yaml            # Main Hermes config (personalities, settings, toolsets, etc.)
│   ├── SOUL.md                # Agent personality/soul definition
│   └── personas/              # Custom personality definitions
│       ├── agent-persona.md
│       ├── persona.md
│       └── tars-personality.md
├── models/                    # Custom Ollama model definitions
│   └── qwen3-fast.Modelfile   # Custom Qwen3 Fast model config
└── webui-docker/              # Docker setup for Hermes WebUI
    ├── docker-compose.yml     # Docker Compose configuration
    ├── webui-settings.json    # WebUI UI/UX settings
    ├── hermes.env.example     # Environment variables template (NO SECRETS)
    └── webui.ctl.env.example  # WebUI control environment template
```

## Full Deployment Guide

Complete step-by-step instructions to deploy Hermes with Ollama, Docker, WebUI, skills, and plugins.

### Prerequisites

- **macOS** (or Linux/Windows with Docker)
- **Docker** and **Docker Compose** installed
- **Ollama** (local or cloud)
- **Git** for cloning this repo
- **4+ GB RAM** available (8+ GB recommended for smooth operation)
- **API keys** for at least one LLM provider (local Ollama, OpenRouter, Anthropic, etc.)

### Step 1: Install & Start Ollama

#### Option A: Local Ollama (Recommended for FDE work)

```bash
# Install Ollama (macOS)
# Download from https://ollama.ai or use:
brew install ollama

# Start Ollama service (runs on http://127.0.0.1:11434)
ollama serve

# In another terminal, pull and create the model:
cd hermes-2nd-brain/hermes-config/models

# Pull base model (Qwen3)
ollama pull qwen3:32b  # or qwen3:7b for faster, smaller model

# Create custom qwen3-fast model from this Modelfile
ollama create qwen3-fast -f qwen3-fast.Modelfile

# Verify it's available
ollama list
```

#### Option B: Cloud Ollama (Ollama Cloud)

```bash
# If using Ollama Cloud instead of local:
# 1. Sign up at https://ollama.com
# 2. Generate API key in settings
# 3. Set in .env later: OLLAMA_API_KEY=<your-key>
```

#### Option C: Remote Ollama Instance

```bash
# If using an existing remote Ollama:
# Update config.yaml model.base_url to point to your instance:
# model:
#   base_url: http://your-ollama-server:11434/v1
```

### Step 2: Clone & Set Up Hermes Config

```bash
# Clone this backup repo
git clone https://github.com/chriswdixon/hermes-2nd-brain.git
cd hermes-2nd-brain

# Create ~/.hermes directory (Hermes runtime config)
mkdir -p ~/.hermes

# Copy config files to ~/.hermes
cp hermes-config/hermes/config.yaml ~/.hermes/
cp -r hermes-config/hermes/personas ~/.hermes/

# Optional: Copy SOUL.md (personality definition)
cp hermes-config/hermes/SOUL.md ~/.hermes/

# Create models directory for custom Ollama models
mkdir -p ~/.hermes/models
cp hermes-config/models/qwen3-fast.Modelfile ~/.hermes/models/
```

### Step 3: Set Up Environment Variables

```bash
# Copy Docker env template
mkdir -p ~/.hermes/webui-docker
cp hermes-config/webui-docker/docker-compose.yml ~/.hermes/webui-docker/
cp hermes-config/webui-docker/webui-settings.json ~/.hermes/webui-docker/
cp hermes-config/webui-docker/hermes.env.example ~/.hermes/webui-docker/.env
cp hermes-config/webui-docker/webui.ctl.env.example ~/.hermes/webui-docker/webui.ctl.env

# Edit .env and add your API keys
nano ~/.hermes/webui-docker/.env
```

**Required variables** (pick ONE LLM provider):
```bash
# Option 1: Local Ollama (no key needed, already running)
# Leave commented—Hermes defaults to http://127.0.0.1:11434

# Option 2: OpenRouter (supports 100+ models, easy to use)
OPENROUTER_API_KEY=your_openrouter_key_here

# Option 3: Anthropic Claude (if you have an API key)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Option 4: Google Gemini
GOOGLE_API_KEY=your_google_api_key_here
```

### Step 4: Start Hermes with Docker

```bash
cd ~/.hermes/webui-docker

# Export user IDs (required for proper file permissions inside container)
export HERMES_UID=$(id -u)
export HERMES_GID=$(id -g)

# Start both gateway (agent) and dashboard (WebUI)
docker compose up -d

# Verify services are running
docker compose ps

# Follow logs (Ctrl+C to exit)
docker compose logs -f
```

**Expected output:**
```
gateway running ✓
dashboard running ✓
```

### Step 5: Access Hermes WebUI

Open in browser:
- **Dashboard**: http://localhost:9119
- **Gateway API** (if enabled): http://localhost:8000

You should see:
- Active model: `qwen3-fast` (or your configured model)
- Personality: `tars` (default, customizable)
- Toolsets: `hermes-cli`, `web` enabled

### Step 6: Enable Skills

Skills are Hermes' extension system. To enable them:

```bash
# Check available skills
hermes skills list

# Enable a skill
hermes skills enable skill-name

# Or enable via config.yaml:
nano ~/.hermes/config.yaml

# Add under `skills.external_dirs`:
skills:
  external_dirs:
    - ~/my-hermes-skills  # Custom skills directory
```

**Common skills to enable:**
```bash
hermes skills enable web-search
hermes skills enable code-execution
hermes skills enable file-operations
hermes skills enable git-integration
```

### Step 7: Enable Plugins

Plugins extend Hermes functionality at the agent level:

```bash
# Edit config.yaml
nano ~/.hermes/config.yaml

# Update the plugins section:
plugins:
  enabled:
    - plugin-name-1
    - plugin-name-2

# Example plugins:
# - slack-integration
# - discord-bot
# - custom-tool
```

Then restart Hermes:
```bash
docker compose restart gateway
```

### Step 8: Configure Toolsets

Toolsets define which integrations are available. This config includes:

```yaml
toolsets:
  - hermes-cli          # Command-line tools
  - web                 # Web browsing & search
  # - hermes-slack      # Slack integration (if enabled)
  # - hermes-discord    # Discord integration (if enabled)
```

Add platform integrations in the `.env`:
```bash
# Discord
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# Telegram
TELEGRAM_BOT_TOKEN=...
```

### Step 9: Set Up MCP Servers (Optional but Recommended)

The config includes **context-a8c** MCP (Automattic internal tools). On first run:

```bash
# When you first use Hermes, it will prompt you to authenticate
# Click the auth prompt in the WebUI or terminal

# Authenticate with your Automattic SSO credentials
# This grants Hermes access to:
# - Linear (tickets, projects, sprints)
# - Slack (channels, DMs, context)
# - P2 (internal blogs and posts)
# - WordPress.com (site info, plugin data)
```

After auth, Hermes can query your team's Linear tickets, search Slack history, and access internal documentation.

**To manage MCPs later:**
```bash
nano ~/.hermes/config.yaml

# MCPs are under `lsp.servers`:
lsp:
  servers:
    context-a8c:
      command: npx
      args:
        - "@automattic/mcp-context-a8c"
```

### Step 10: First Run & Customization

```bash
# Access Hermes WebUI at http://localhost:9119

# Settings you'll want to configure:
# 1. Personality → choose from 13 available modes
# 2. Model → switch between local/cloud providers
# 3. Reasoning effort → low/medium/high
# 4. Enable/disable toolsets
# 5. Set API keys for desired services
# 6. Authenticate with MCP servers if needed
```

### Step 10: Create Your First Session

1. Open WebUI dashboard
2. Click **New Session**
3. Choose personality (try "noir" for FDE vibes)
4. Type a prompt or paste code to analyze
5. Hermes responds with access to all enabled tools

## Skills & Plugins Reference

### Built-in Skills (Common)

| Skill | Purpose |
|-------|---------|
| `web-search` | Search the web for information |
| `code-execution` | Run Python/bash scripts safely |
| `file-operations` | Read/write files in workspace |
| `git-integration` | Clone/push/commit via git |
| `docker-ops` | Run Docker commands |

**Enable multiple skills:**
```bash
for skill in web-search code-execution file-operations git-integration; do
  hermes skills enable $skill
done
```

### Plugin Examples

**Platform Integrations:**
- `hermes-discord` - Run Hermes as a Discord bot
- `hermes-slack` - Hermes in Slack channels
- `hermes-telegram` - Telegram bot integration
- `hermes-teams` - Microsoft Teams integration

**Custom Plugins:**
Create custom plugins in `~/.hermes/plugins/`:
```bash
mkdir -p ~/.hermes/plugins/my-custom-plugin
# Add your plugin code here
```

Then enable in config:
```yaml
plugins:
  enabled:
    - my-custom-plugin
```

## Performance Tuning

### For M-series Mac (MLX acceleration)

```yaml
# In config.yaml, configure for local inference:
model:
  provider: ollama-launch
  base_url: http://127.0.0.1:11434/v1
  default: qwen3-fast

# Ollama automatically uses Metal (GPU) on M1/M2/M3 Macs
```

### For Multi-GPU Setup

```bash
# If you have NVIDIA GPUs:
# 1. Install NVIDIA container runtime
# 2. Update docker-compose.yml to use nvidia/cuda base image
# 3. Ollama will auto-detect and use GPUs
```

### Memory Optimization

Adjust in `config.yaml`:
```yaml
terminal:
  container_memory: 5120  # MB, adjust based on available RAM
code_execution:
  timeout: 300  # seconds, lower for faster failure
compression:
  enabled: true  # auto-compress old context for efficiency
```

## Monitoring & Maintenance

### Check Service Health

```bash
# View all logs
docker compose logs -f

# Check specific service
docker compose logs -f gateway   # Agent service
docker compose logs -f dashboard # WebUI service

# Check resource usage
docker stats hermes hermes-dashboard
```

### Update Ollama Model

```bash
# Pull latest Qwen3 model
ollama pull qwen3:latest

# Rebuild custom model
ollama create qwen3-fast -f ~/.hermes/models/qwen3-fast.Modelfile

# Restart Hermes
docker compose restart gateway
```

### Backup Your Config

```bash
# Backup to git
cd hermes-2nd-brain
git add -A
git commit -m "Updated config: enabled skills, new personalities"
git push
```

### Reset to Defaults

```bash
# Restore config from this repo
cp hermes-config/hermes/config.yaml ~/.hermes/config.yaml

# Keep your .env secrets, but reset everything else
```

## Configuration Details

### Agent Settings (config.yaml)

- **Personalities**: Catgirl, concise, creative, helpful, hype, kawaii, noir, philosopher, pirate, shakespeare, surfer, teacher, technical, uwu
- **Default Personality**: tars (defined in `personas/tars-personality.md`)
- **Model**: qwen3-fast (via Ollama at `http://127.0.0.1:11434/v1`)
- **Toolsets**: CLI, web, various platform integrations
- **Reasoning**: Medium effort, tool use auto-enforcement
- **Plugins**: Enabled list is empty by default
- **MCP Servers**: context-a8c (Automattic context — Linear, Slack, P2 access)

### MCP Servers

**context-a8c** — Access to Automattic internal tools:
- **Linear** — Issues, projects, sprints, backlogs (read/write)
- **Slack** — Channel messages, DMs, threads, lookups
- **P2 blogs** — Internal P2 post search and content
- **WordPress.com** — Site info, plugin data, infrastructure context

Enabled by default in this config. Hermes will authenticate via OAuth 2.1 + PKCE on first use.

**Setup:**
```bash
# MCP is pre-configured in config.yaml
# On first run, you'll be prompted to authenticate with Automattic SSO

# Hermes will then have access to:
# - Linear tickets and project context
# - Slack channels and messages
# - P2 internal blogs
# - WordPress.com site information
```

### Model Configuration

The `qwen3-fast.Modelfile` defines a custom Ollama model with:
- `min_p: 0`
- `num_ctx: 65536` (65K context window — required for reliable tool use)
- `temperature: 1`
- `top_k: 20`, `top_p: 0.95`
- Custom parser/renderer for Qwen3.5

**Context Window**: 65,536 tokens (upgraded from 32K for tool reliability)

To rebuild:
```bash
ollama create qwen3-fast -f hermes-config/models/qwen3-fast.Modelfile
```

### Services & Daemons

**Running Services (macOS launchd):**
- `com.hermes.agent` - Hermes CLI agent (via `ollama launch hermes`)
- `ai.hermes.gateway` - Hermes Gateway daemon (enables WebUI + scheduled jobs)
- `com.hermes.webui` - Hermes WebUI server (runs `ctl.sh start`)

**Access:**
- **CLI**: `hermes` or `ollama launch hermes --model qwen3-fast`
- **WebUI**: http://localhost:8787 (or click app in Dock)
- **Gateway API**: http://127.0.0.1:8000 (internal, used by WebUI)

**Logs:**
```bash
tail -f ~/.hermes/logs/gateway.log          # Gateway
tail -f ~/.hermes/webui/bootstrap-8787.log  # WebUI
```

**Docker Setup** (alternative to launchd):
The `docker-compose.yml` in this repo is for reference. On macOS, native launchd services are preferred for auto-start and reliability.

## Customization Guide

### Add a New Personality

1. Create personality definition file:
```bash
cat > ~/.hermes/personas/my-personality.md << 'EOF'
You are a [your personality name]. Your traits and behaviors:
- How you speak
- Your tone and style
- Any specific instructions

Use this personality for [what it's good for].
EOF
```

2. Add to `config.yaml`:
```yaml
agent:
  personalities:
    my-personality: |
      You are a [your personality name]. Your traits and behaviors:
      - How you speak
      - Your tone and style
      - Any specific instructions
```

3. Set as default (optional):
```yaml
personality: my-personality
```

4. Switch in WebUI dashboard under Settings → Personality

### Create a Custom Skill

```bash
# Create skill directory
mkdir -p ~/.hermes/skills/my-skill

# Create skill metadata
cat > ~/.hermes/skills/my-skill/skill.yaml << 'EOF'
name: My Custom Skill
version: 1.0.0
description: What this skill does
author: Your Name
enabled: true
tools:
  - name: my_tool
    description: Tool description
    params:
      param1: string
EOF

# Create implementation (Python, JavaScript, or bash)
cat > ~/.hermes/skills/my-skill/index.py << 'EOF'
def my_tool(param1):
    """Tool implementation"""
    return f"Result: {param1}"
EOF
```

5. Enable in config:
```yaml
skills:
  enabled:
    - my-skill
```

### Add Custom Toolsets

1. Create toolset directory:
```bash
mkdir -p ~/.hermes/toolsets/my-toolset
```

2. Update `config.yaml`:
```yaml
toolsets:
  - hermes-cli
  - web
  - my-toolset
```

### Create a Custom Plugin

Plugins extend Hermes at the agent/gateway level:

```bash
mkdir -p ~/.hermes/plugins/my-plugin

cat > ~/.hermes/plugins/my-plugin/plugin.yaml << 'EOF'
name: My Custom Plugin
version: 1.0.0
description: What this plugin does
hooks:
  - on_message_received
  - before_tool_execution
  - after_response_generated
EOF
```

Then enable:
```yaml
plugins:
  enabled:
    - my-plugin
```

### Switch LLM Providers

Change in `config.yaml`:
```yaml
model:
  provider: ollama-launch        # Current
  # provider: openrouter         # Alternative
  # provider: anthropic          # Alternative
  base_url: http://127.0.0.1:11434/v1
  default: qwen3-fast
```

Or via CLI:
```bash
hermes model switch openrouter
hermes model set claude-opus-4.6
```

### Modify Agent Behavior

All agent settings are in `config.yaml` under `agent.*`:

```yaml
agent:
  reasoning_effort: medium    # low, medium, high
  max_turns: 60               # Max conversation depth
  tool_use_enforcement: auto  # auto, required, disabled
  task_completion_guidance: true
  verbose: false              # Show detailed logs
```

## Environment Variables

See `webui-docker/hermes.env.example` for available options:

- **LLM Providers**: OpenRouter, NovitaAI, Google Gemini, Ollama Cloud, GLM, Claude (Anthropic), Xing, Deepseek, Grok
- **TTS Providers**: ElevenLabs, Edge, OpenAI, Piper, Neutts
- **STT Providers**: OpenAI Whisper, ElevenLabs, Mistral
- **Platform Integrations**: Discord, Slack, Teams, Telegram, etc.

Only set the environment variables for providers you actually use.

## Security

⚠️ **Do not commit**:
- `.env` files with actual API keys
- Any files containing credentials, tokens, or secrets
- Service account JSON files

The `.gitignore` in this repo prevents accidental commits of secrets. Review the file before making changes.

## Docker Troubleshooting

### Restart Services

```bash
docker compose restart
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f gateway
docker compose logs -f dashboard
```

### Stop Services

```bash
docker compose down
```

### File Permission Issues

If files are owned by the wrong user inside the container:
```bash
export HERMES_UID=$(id -u)
export HERMES_GID=$(id -g)
docker compose down
docker compose up -d
```

## Links

- [Hermes Agent Documentation](https://hermes-agent.nousresearch.com/)
- [Nous Research GitHub](https://github.com/NousResearch/hermes-agent)
- [Ollama Documentation](https://ollama.ai/)

## Notes

- This is a personal backup of a Hermes installation
- Docker Compose file uses `network_mode: host` for local performance
- Dashboard password auth is disabled in this config (enable if needed in config.yaml)
