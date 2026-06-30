#!/bin/bash
set -e
X_DIR="/Users/kirill/Desktop/CONTENT DISTRIBUTION/X-ACTIONS-AGENT"
cd "$X_DIR"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required (>=18)."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for native npm modules."
  exit 1
fi

echo "Node: $(node -v)"
echo "Installing XActions dependencies..."

# Avoid node-gyp selecting a virtualenv python path with spaces.
export npm_config_python="/usr/bin/python3"
npm install

if [ ! -f "data/agent-config.json" ]; then
  echo "No data/agent-config.json found. Running setup wizard..."
  npm run agent:setup
fi

echo "Setup complete."
echo "Next: ./run_x_agent.sh"
