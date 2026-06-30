import argparse
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from telethon import TelegramClient
from telethon.tl.types import User

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "telegram_leads_agent.json"
STATE_PATH = BASE_DIR / "output" / "telegram_leads_state.json"


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ollama_chat(host: str, model: str, prompt: str, timeout_sec: int = 30) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    req = Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout_sec) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("message", {}).get("content", "").strip()


def classify_message(text: str, cfg: dict) -> dict:
    host = cfg.get("ollama_host", "http://127.0.0.1:11434")
    model = cfg.get("ollama_model", "llama3.1")
    prompt = f"""
Return ONLY JSON with fields:
- relevant: boolean
- score: number 0..1
- reason: short string

Relevant if this incoming Telegram message is a request to hire or find someone for:
IT, developer work, AI, apps, web, Telegram bots, automation, technical partner.

Message:
{text[:900]}
"""
    try:
        out = ollama_chat(host, model, prompt)
        m = re.search(r"\{.*\}", out, flags=re.DOTALL)
        if not m:
            raise ValueError("no_json")
        data = json.loads(m.group(0))
        return {
            "relevant": bool(data.get("relevant", False)),
            "score": float(data.get("score", 0.0)),
            "reason": str(data.get("reason", ""))[:180],
        }
    except Exception:
        low = text.lower()
        intent = any(x in low for x in ["ищу", "нужен", "need", "hire", "hiring", "подрядчик", "в штат"])
        domain = any(x in low for x in ["разработ", "developer", "ai", "ии", "app", "web", "telegram", "телеграм", "бот"])
        ok = intent and domain
        return {"relevant": ok, "score": 0.68 if ok else 0.1, "reason": "rule_fallback"}


def draft_reply(text: str, persona: str, cfg: dict) -> str:
    host = cfg.get("ollama_host", "http://127.0.0.1:11434")
    model = cfg.get("ollama_model", "llama3.1")
    prompt = f"""
Write one concise human reply for Telegram DM.
Rules:
- max 300 chars
- no links
- no hashtags
- friendly and specific
- soft CTA to continue conversation

Persona:
{persona[:1200]}

Incoming message:
{text[:900]}

Return only reply text.
"""
    try:
        out = ollama_chat(host, model, prompt)
        return re.sub(r"\s+", " ", out).strip()[:300]
    except Exception:
        return "Понял запрос. Мы как раз делаем такие IT/AI/web/telegram решения под ключ, от задачи до запуска. Если актуально, могу коротко расписать план и сроки прямо тут."


async def run_cycle(client: TelegramClient, cfg: dict, state: dict, persona: str):
    watched = set(cfg.get("watch_usernames", []))
    min_score = float(cfg.get("min_score", 0.72))
    auto_reply = bool(cfg.get("auto_reply", False))
    max_per_cycle = int(cfg.get("max_actions_per_cycle", 3))

    actions = 0
    my_id = (await client.get_me()).id

    async for dialog in client.iter_dialogs(limit=200):
        if actions >= max_per_cycle:
            break
        ent = dialog.entity
        if not isinstance(ent, User):
            continue
        username = (ent.username or "").lower()
        if watched and username not in {u.lower().lstrip("@") for u in watched}:
            continue

        msg = await client.get_messages(dialog.id, limit=1)
        if not msg:
            continue
        m = msg[0]
        if not m.message:
            continue
        if m.sender_id == my_id:
            continue

        key = f"{dialog.id}:{m.id}"
        if key in state.get("seen", []):
            continue

        decision = classify_message(m.message, cfg)
        state.setdefault("seen", []).append(key)

        if not decision["relevant"] or decision["score"] < min_score:
            continue

        reply = draft_reply(m.message, persona, cfg)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "dialog_id": dialog.id,
            "username": f"@{username}" if username else "",
            "msg_id": m.id,
            "text": m.message[:800],
            "decision": decision,
            "draft_reply": reply,
            "status": "draft",
        }

        if auto_reply:
            await client.send_message(dialog.id, reply)
            row["status"] = "sent"

        state.setdefault("history", []).append(row)
        actions += 1


def trim_state(state: dict):
    state["seen"] = list(dict.fromkeys(state.get("seen", [])))[-10000:]
    state["history"] = state.get("history", [])[-2000:]


async def main():
    parser = argparse.ArgumentParser(description="Telegram leads agent")
    parser.add_argument("--once", action="store_true", help="run one cycle")
    args = parser.parse_args()

    cfg = read_json(CONFIG_PATH, None)
    if cfg is None:
        raise SystemExit(f"Missing config: {CONFIG_PATH}")

    persona_file = Path(cfg.get("persona_file", ""))
    persona = persona_file.read_text(encoding="utf-8") if persona_file.exists() else ""

    state = read_json(STATE_PATH, {"seen": [], "history": []})

    api_id = int(cfg.get("api_id", 0))
    api_hash = cfg.get("api_hash", "")
    session_file = cfg.get("session_file", str(BASE_DIR / "config" / "telegram_leads"))

    if not api_id or not api_hash:
        raise SystemExit("api_id/api_hash are required in config")

    client = TelegramClient(session_file, api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Session is not authorized. Set session_file to authorized .session base name")

    try:
        if args.once:
            await run_cycle(client, cfg, state, persona)
            trim_state(state)
            write_json(STATE_PATH, state)
            return

        while True:
            await run_cycle(client, cfg, state, persona)
            trim_state(state)
            write_json(STATE_PATH, state)
            await asyncio.sleep(int(cfg.get("cycle_seconds", 900)))
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
