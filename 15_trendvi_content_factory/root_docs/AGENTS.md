# Codex Project Notes

## Project

- Repository: `kirbudilov01/trendvi`
- Local path: `/Users/kirill/Desktop/trendvi-main`
- Git remote: `git@github-kirbudilov01:kirbudilov01/trendvi.git`
- Default branch: `main`

## Working Style

- Treat this repository as the source of truth for Trendvi / want2view work.
- Before changing code, inspect the relevant files and current Git status.
- Keep edits scoped to the user's task.
- Do not commit secrets, `.env` files, dumps, private keys, tokens, or server credentials.
- After meaningful changes, run the narrowest useful checks before committing.
- When the user asks to ship, commit with a clear message, push to `origin/main` unless another branch is requested, then deploy using the server notes in the local private Codex file.

## Standard Task Flow

When the user gives a product/code task and asks to publish or deploy, use this flow:

1. Inspect `git status --short --branch` and relevant files.
2. Implement the requested change locally.
3. Run the narrowest useful checks:
   - frontend-only change: `cd frontend && npm run build`
   - backend-only change: targeted tests if available, otherwise import/syntax or container build checks
   - Docker/runtime change: relevant `docker compose config` or service build
4. Commit only the intended files with a concise message.
5. Push to `origin/main` unless the user asked for another branch.
6. Deploy on production through SSH:

```bash
ssh trendvi-prod 'cd /home/ubuntu/trendvi && git pull --ff-only origin main'
```

7. Rebuild/restart only the services affected by the change. Common examples:

```bash
ssh trendvi-prod 'cd /home/ubuntu/trendvi && docker compose build frontend && docker compose up -d frontend'
ssh trendvi-prod 'cd /home/ubuntu/trendvi && docker compose build backend && docker compose up -d backend'
ssh trendvi-prod 'cd /home/ubuntu/trendvi && docker compose build backend trendvi-search-worker && docker compose up -d backend trendvi-search-worker'
```

8. Verify production state:

```bash
ssh trendvi-prod 'cd /home/ubuntu/trendvi && docker compose ps'
ssh trendvi-prod 'cd /home/ubuntu/trendvi && docker compose logs --tail=120 backend frontend'
```

If a deploy needs secrets or environment changes, update them only on the server or in local ignored files, never in tracked Git files.

## Local Development

Common local commands:

```bash
docker compose up -d
docker compose build backend frontend
docker compose logs -f backend
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

Backend:

```bash
cd backend
python -m pytest
```

## Deployment

- Keep non-secret deployment process notes in repository docs when they help future work.
- Keep real server access details only in `.codex/server-access.md` on this machine.
- Check existing deployment references before inventing a new flow:
  - `docs/prod-deploy.md`
  - `ARSENIY_SERVER_DEPLOY.md`
  - `README_ZEABUR_DEPLOY.md`
  - `scripts/prod_deploy.sh`
