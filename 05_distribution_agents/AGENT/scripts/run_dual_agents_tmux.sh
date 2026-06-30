#!/bin/bash
set -e

AGENT_DIR="/Users/kirill/Desktop/CONTENT DISTRIBUTION/AGENT"
X_DIR="/Users/kirill/Desktop/CONTENT DISTRIBUTION/X-ACTIONS-AGENT"
THREADS_DIR="/Users/kirill/Desktop/CONTENT DISTRIBUTION/TELEGRAM : THREADS AGENT/threads_autopilot"
SESSION="${DUAL_SESSION_NAME:-dual_agents}"
LAYOUT="${DUAL_LAYOUT:-even-horizontal}"
THREADS_SESSION_FILE="$THREADS_DIR/threads_storage_state.json"
X_SESSION_FILE="$X_DIR/data/session.json"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required"
  exit 1
fi

if [ ! -d "$X_DIR" ]; then
  echo "X directory not found: $X_DIR"
  exit 1
fi

if [ ! -d "$THREADS_DIR" ]; then
  echo "Threads directory not found: $THREADS_DIR"
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists. Attaching..."
  tmux attach -t "$SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" -x 240 -y 60 -c "$THREADS_DIR"
tmux setw -t "$SESSION":0 remain-on-exit on

# Left pane: Threads autopilot (visible browser for human-like monitoring)
if [ -f "$THREADS_SESSION_FILE" ]; then
  tmux send-keys -t "$SESSION":0.0 "source ../venv/bin/activate && python autopilot.py --profile safe --verbose" C-m
else
  tmux send-keys -t "$SESSION":0.0 "echo 'Threads login required. Complete browser auth and press Enter in terminal.' && source ../venv/bin/activate && python autopilot.py --setup-login && python autopilot.py --profile safe --verbose" C-m
fi

# Right pane: X thought leader agent
tmux split-window -h -t "$SESSION":0 -c "$X_DIR"
if [ -f "$X_SESSION_FILE" ]; then
  tmux send-keys -t "$SESSION":0.1 "mkdir -p logs && export BROWSER_HEADLESS=false && export npm_config_python=/usr/bin/python3 && npm run agent 2>&1 | tee -a logs/agent.log" C-m
else
  tmux send-keys -t "$SESSION":0.1 "echo 'X login required. Complete browser auth and press Enter in terminal.' && export BROWSER_HEADLESS=false && export npm_config_python=/usr/bin/python3 && npm run agent:login && npm run agent 2>&1 | tee -a logs/agent.log" C-m
fi

case "$LAYOUT" in
  even-horizontal|even-vertical|main-horizontal|main-vertical|tiled)
    tmux select-layout -t "$SESSION":0 "$LAYOUT"
    ;;
  *)
    echo "Unknown DUAL_LAYOUT='$LAYOUT', fallback to even-horizontal"
    tmux select-layout -t "$SESSION":0 even-horizontal
    ;;
esac

echo "Started session: $SESSION"
echo "Layout: $LAYOUT"
echo "Tips:"
echo "  - Resize panes: Ctrl+b then hold Alt+Arrow"
echo "  - Swap panes: Ctrl+b then o"
echo "  - Toggle zoom pane: Ctrl+b then z"
echo "  - Detach session: Ctrl+b then d"
tmux attach -t "$SESSION"
