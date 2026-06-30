# SMM-HEAD-AGENT

Workspace-level reference for the SMM Head role.

This repository now contains SMM Head logic in two places:

1. App runtime generation:
- New stream workspaces auto-create SMM-HEAD-AGENT.md from stream automation service.

2. Workspace Copilot setup:
- .github/agents/smm-head.agent.md
- .github/instructions/smm-head-workflow.instructions.md

Additional workspace agents:
- .github/agents/producer.agent.md
- .github/agents/smm-manager.agent.md
- .github/agents/article-creator.agent.md

Additional role profiles:
- config/roles/PRODUCER/role.yaml
- config/roles/SMM-MANAGER/role.yaml
- config/roles/ARTICLE-CREATOR/role.yaml

Use the SMM Head role to manage posting decisions, asset reuse, missing-asset requests, and final queue planning without duplicate generation.
