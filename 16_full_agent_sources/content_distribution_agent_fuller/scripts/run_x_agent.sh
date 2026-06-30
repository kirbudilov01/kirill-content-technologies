#!/bin/bash
set -e
X_DIR="/Users/kirill/Desktop/CONTENT DISTRIBUTION/X-ACTIONS-AGENT"
cd "$X_DIR"

# Default mode: thought leader agent (manual login required first)
# Login once:
#   npm run agent:login

mkdir -p logs
export BROWSER_HEADLESS=false
export npm_config_python="/usr/bin/python3"

if [ ! -f "data/session.json" ]; then
	echo "No X session found. Starting login flow..."
	echo "After login in opened browser, return here and press Enter."
	npm run agent:login
fi

npm run agent 2>&1 | tee -a logs/agent.log
