"""Send the slides and caption to your Telegram chat via a free bot."""
import json
import os
from pathlib import Path

import requests


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"


def send_message(text: str) -> None:
    chat = os.environ["TELEGRAM_CHAT_ID"]
    for i in range(0, len(text), 4000):  # Telegram's message limit is 4096 chars
        r = requests.post(_api("sendMessage"), timeout=30,
                          data={"chat_id": chat, "text": text[i:i + 4000],
                                "disable_web_page_preview": True})
        r.raise_for_status()


def send_slides(paths: list[Path], caption_path: Path) -> None:
    chat = os.environ["TELEGRAM_CHAT_ID"]
    # Sent as documents (not photos) so Telegram doesn't compress them.
    # Telegram allows max 10 files per album, so send in chunks.
    for start in range(0, len(paths), 10):
        chunk = paths[start:start + 10]
        media, files = [], {}
        for j, p in enumerate(chunk):
            files[f"f{j}"] = (p.name, p.read_bytes(), "image/png")
            media.append({"type": "document", "media": f"attach://f{j}"})
        r = requests.post(_api("sendMediaGroup"), timeout=120,
                          data={"chat_id": chat, "media": json.dumps(media)}, files=files)
        r.raise_for_status()
    send_message(caption_path.read_text(encoding="utf-8"))
    print(f"[telegram] sent {len(paths)} slides + caption")


def notify_failure(error: str, what: str = "Today's AI carousel") -> None:
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        try:
            send_message(f"{what} failed:\n{error[:1500]}\n\n"
                         "Check the GitHub Actions log, or make the post manually.")
        except Exception as e:  # noqa: BLE001
            print(f"[telegram] could not send failure notice: {e}")
