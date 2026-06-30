#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

if [ ! -f config/telegram_leads_agent.json ]; then
  cp config/telegram_leads_agent.example.json config/telegram_leads_agent.json
  echo "Created config/telegram_leads_agent.json"
  echo "Edit it first, then run this script again."
  exit 0
fi

python tools/telegram_leads_agent.py
