#!/bin/bash
# Wrapper for Hermes MCP config — sets OAuth env vars before launching context-a8c.
# Launch with --disable-features=AutoReloadPAC to avoid PAC localhost parse crash
set -e
export OAUTH_ENABLED=true
export WP_OAUTH_CLIENT_ID="128117"
exec npx @automattic/mcp-context-a8c "$@"
