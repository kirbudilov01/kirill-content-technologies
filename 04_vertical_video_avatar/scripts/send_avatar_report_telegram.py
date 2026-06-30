import asyncio
import os
from pathlib import Path

from telethon import TelegramClient


PRIVATE_DIR = Path("/Users/kirill/Documents/Codex/.codex-private")
SESSION = PRIVATE_DIR / "telegram-sessions" / "codex-user.session"
DOC = Path("/Users/kirill/Desktop/reposearchengine-main/research/avatar-lab/digital-avatar-ready-systems-report.docx")
TARGET = "whiterose_sc"
CAPTION = (
    "Коммент: собрали большой ресерч по готовым self-hosted digital avatar системам для нашего контент-завода. "
    "Там не только lip-sync, а AvatarAI, Duix, HeyGem/ComfyUI, MuseTalk, LatentSync, Hallo2, EchoMimic, Sonic, "
    "плюс порядок RunPod-тестов и как искали. Главная логика: сначала добиваемся \"Avatar good\", потом строим batch pipeline."
)


async def main():
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    client = TelegramClient(str(SESSION), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("Telegram session is not authorized. Run an account login first, then retry this script.")
        await client.disconnect()
        return 2
    entity = await client.get_entity(TARGET)
    message = await client.send_file(entity, str(DOC), caption=CAPTION)
    print(f"Sent Telegram message_id={message.id}")
    await client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
