"""Send the slides and caption to your Telegram chat via a free bot."""
import json
import os
import time
from pathlib import Path

import requests


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}"


def _post(method: str, attempts: int = 6, **kwargs) -> None:
    # Telegram's gateway sometimes returns 502s for an hour or more, so back off
    # 20s, 40s, 80s, 160s, 320s (~10 min) before giving up.
    delay = 20
    for attempt in range(1, attempts + 1):
        try:
            r = requests.post(_api(method), **kwargs)
            if r.status_code == 429 or r.status_code >= 500:
                r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            if attempt == attempts:
                raise
            print(f"[telegram] {method} failed ({e.__class__.__name__}), retrying in {delay}s")
            time.sleep(delay)
            delay *= 2
            continue
        r.raise_for_status()
        return


def send_message(text: str, attempts: int = 6) -> None:
    chat = os.environ["TELEGRAM_CHAT_ID"]
    for i in range(0, len(text), 4000):  # Telegram's message limit is 4096 chars
        _post("sendMessage", attempts, timeout=30,
              data={"chat_id": chat, "text": text[i:i + 4000],
                    "disable_web_page_preview": True})


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
        _post("sendMediaGroup", timeout=120,
              data={"chat_id": chat, "media": json.dumps(media)}, files=files)
    send_message(caption_path.read_text(encoding="utf-8"))
    print(f"[telegram] sent {len(paths)} slides + caption")


def notify_failure(error: str, what: str = "Today's AI carousel") -> None:
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        try:
            send_message(f"{what} failed:\n{error[:1500]}\n\n"
                         "Check the GitHub Actions log, or make the post manually.", attempts=2)
        except Exception as e:  # noqa: BLE001
            print(f"[telegram] could not send failure notice: {e}")
