"""Daily AI news carousel: fetch -> curate -> render -> deliver.

Usage:
  python main.py                 full run (needs GEMINI_API_KEY; Telegram optional)
  python main.py --sample        render from samples/sample_stories.json, no APIs
  python main.py --no-send       full run but don't message Telegram
"""
import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Load .env for local runs (GitHub Actions uses repository secrets instead).
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            if _v.strip():
                os.environ.setdefault(_k.strip(), _v.strip())

from src import config  # noqa: E402  (imported after .env so it sees those values)
from src.deliver import notify_failure, send_slides  # noqa: E402
from src.render import news_date, render_slides, write_caption  # noqa: E402

HISTORY = ROOT / "data" / "history.json"


def load_history() -> dict:
    if not HISTORY.exists():
        return {}
    hist = json.loads(HISTORY.read_text())
    cutoff = time.time() - config.HISTORY_DAYS * 86400
    return {url: ts for url, ts in hist.items() if ts >= cutoff}


def save_history(hist: dict, stories: list[dict]) -> None:
    now = time.time()
    for s in stories:
        hist[s["url"]] = now
    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_text(json.dumps(hist, indent=1, sort_keys=True))


def run(args) -> None:
    out_dir = ROOT / "output" / news_date().strftime("%Y-%m-%d")

    if args.sample:
        data = json.loads((ROOT / "samples" / "sample_stories.json").read_text())
        hist = None
    else:
        from src.curate import curate
        from src.fetch_news import fetch_all
        hist = load_history()
        items = fetch_all(set(hist))
        data = curate(items)

    paths = render_slides(data, out_dir)
    caption = write_caption(data, out_dir)
    (out_dir / "stories.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if hist is not None:
        save_history(hist, data["stories"])

    can_send = os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    if can_send and not args.no_send:
        send_slides(paths, caption)
    else:
        print(f"[done] files are in {out_dir} (Telegram not sent)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="render sample data, no APIs")
    ap.add_argument("--no-send", action="store_true", help="skip Telegram")
    args = ap.parse_args()
    try:
        run(args)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        if not args.sample:
            notify_failure(str(e))
        sys.exit(1)
