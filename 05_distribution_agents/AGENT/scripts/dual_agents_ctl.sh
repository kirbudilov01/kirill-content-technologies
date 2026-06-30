#!/bin/bash
set -e

SESSION="${DUAL_SESSION_NAME:-dual_agents}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  echo "Usage: $0 {start|attach|stop|restart|status}"
}

cmd="${1:-start}"

case "$cmd" in
  start)
    "$SCRIPT_DIR/run_dual_agents_tmux.sh"
    ;;
  attach)
    tmux attach -t "$SESSION"
    ;;
  stop)
    tmux kill-session -t "$SESSION"
    echo "Stopped session: $SESSION"
    ;;
  restart)
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    "$SCRIPT_DIR/run_dual_agents_tmux.sh"
    ;;
  status)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "Session is running: $SESSION"
      tmux list-panes -t "$SESSION":0 -F "pane #{pane_index}: #{pane_current_command} | dead=#{pane_dead}"
    else
      echo "Session is not running: $SESSION"
    fi
    ;;
  *)
    usage
    exit 1
    ;;
esac
