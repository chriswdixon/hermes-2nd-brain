# Hermes 2nd Brain Backup

Personal backup of Hermes Agent configuration, personalities, skills, plugins, and Docker setup.

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

## Quick Start

### 1. Restore from Backup

```bash
# Copy to your Hermes config directory
cp -r hermes-config/* ~/.hermes-config/

# Or if you're setting up fresh Hermes:
mkdir -p ~/hermes-config
cp -r hermes-config/* ~/hermes-config/
```

### 2. Set Up Environment Variables

```bash
# Copy example env files and fill in your API keys
cp webui-docker/hermes.env.example ~/.hermes-config/webui-docker/.env
cp webui-docker/webui.ctl.env.example ~/.hermes-config/webui-docker/webui.ctl.env

# Edit with your API keys
nano ~/.hermes-config/webui-docker/.env
```

### 3. Start Hermes with Docker

```bash
cd ~/.hermes-config/webui-docker

# Set user IDs (required for file permissions)
export HERMES_UID=$(id -u)
export HERMES_GID=$(id -g)

# Start services
docker compose up -d

# View logs
docker compose logs -f
```

## Configuration Details

### Agent Settings (config.yaml)

- **Personalities**: Catgirl, concise, creative, helpful, hype, kawaii, noir, philosopher, pirate, shakespeare, surfer, teacher, technical, uwu
- **Default Personality**: tars (defined in `personas/tars-personality.md`)
- **Model**: qwen3-fast (via Ollama at `http://127.0.0.1:11434/v1`)
- **Toolsets**: CLI, web, various platform integrations
- **Reasoning**: Medium effort, tool use auto-enforcement
- **Plugins**: Enabled list is empty by default

### Model Configuration

The `qwen3-fast.Modelfile` defines a custom Ollama model with:
- `min_p: 0`
- `num_ctx: 32768` (32K context window)
- `temperature: 1`
- `top_k: 20`, `top_p: 0.95`
- Custom parser/renderer for Qwen3.5

To rebuild:
```bash
ollama create qwen3-fast -f hermes-config/models/qwen3-fast.Modelfile
```

### Docker Setup

**Services:**
- `gateway` - Main Hermes agent service (host network, port bindings handled locally)
- `dashboard` - Dashboard UI (localhost:9119)

**Security Notes:**
- Dashboard binds to `127.0.0.1` only (local access only)
- API server is disabled by default (requires `API_SERVER_KEY` and `API_SERVER_HOST` env vars)
- All config files and API keys stored in `~/.hermes` volume mount

## Customization

### Add a New Personality

1. Create a new file in `hermes-config/hermes/personas/your-personality.md`
2. Define the personality prompt/instructions
3. Update `hermes-config/hermes/config.yaml` in the `agent.personalities` section:
   ```yaml
   personalities:
     your-personality: |
       Your personality prompt here...
   ```

### Enable Plugins

Update `hermes-config/hermes/config.yaml`:
```yaml
plugins:
  enabled:
    - plugin-name-here
    - another-plugin
```

### Add Custom Toolsets

Update `hermes-config/hermes/config.yaml`:
```yaml
toolsets:
  - hermes-cli
  - web
  - your-custom-toolset
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
