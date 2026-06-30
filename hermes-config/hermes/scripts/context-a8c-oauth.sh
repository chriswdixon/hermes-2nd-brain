#!/bin/bash
set -e
export OAUTH_ENABLED=true
export WP_OAUTH_CLIENT_ID="128117"
echo "Starting context-a8c MCP server with OAuth enabled..."
npx @automattic/mcp-context-a8c 2>&1
