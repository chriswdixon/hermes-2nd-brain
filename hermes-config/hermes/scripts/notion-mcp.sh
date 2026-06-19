#!/bin/bash
# Wrapper for notion-mcp-server — pulls API key from Bitwarden Secrets Manager at runtime.
set -e

NOTION_TOKEN="$(bw-secret value NOTION_API_KEY)"

export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", \"Notion-Version\": \"2022-06-28\"}"

exec /Users/mrchriswdixon/.local/bin/notion-mcp-server "$@"
