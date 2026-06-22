#!/bin/bash
# Wrapper for notion-mcp-server — fetches NOTION_API_KEY from Bitwarden Secrets Manager
# at runtime using BWS_ACCESS_TOKEN. Sources .env as fallback so MCP test works.
set -e

# Fetch BWS_ACCESS_TOKEN from Keychain — available regardless of what Hermes passes through.
_BWS_TOKEN="${BWS_ACCESS_TOKEN:-$(/usr/bin/security find-generic-password -s bws_access_token -w 2>/dev/null || true)}"

NOTION_TOKEN="${NOTION_API_KEY:-}"

if [ -z "$NOTION_TOKEN" ] && [ -n "$_BWS_TOKEN" ]; then
  NOTION_TOKEN="$(BWS_ACCESS_TOKEN="$_BWS_TOKEN" /Users/mrchriswdixon/.local/bin/bws secret list --output json 2>/dev/null \
    | /usr/bin/python3 -c 'import sys,json; v=[s["value"] for s in json.load(sys.stdin) if s["key"]=="NOTION_API_KEY"]; print(v[0] if v else "", end="")' 2>/dev/null || true)"
fi

if [ -z "$NOTION_TOKEN" ]; then
  echo "notion-mcp.sh: NOTION_API_KEY not available" >&2
  exit 1
fi

export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", \"Notion-Version\": \"2022-06-28\"}"

exec /Users/mrchriswdixon/.hermes/node/bin/node /Users/mrchriswdixon/.local/lib/node_modules/@notionhq/notion-mcp-server/bin/cli.mjs "$@"