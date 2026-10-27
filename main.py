"""Daily AI news carousel: fetch -> curate -> render -> deliver.

Usage:
  python main.py                 full run (needs GEMINI_API_KEY; Telegram optional)
  python main.py --sample        render from samples/sample_stories.json, no APIs
  python main.py --no-send       full run but don't message Telegram
  python main.py --breaking "topic" [--notes "angle"]   2-3 slides on one topic, right now
"""
import argparse
from datetime import datetime
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
from src.render import IST, news_date, render_slides, write_caption  # noqa: E402

HISTORY = ROOT / "data" / "history.json"
# The news date of the last edition sent, so a second run for the same day skips itself.
LAST_EDITION = ROOT / "data" / "last_edition.txt"
# Headlines from recent editions. Links alone miss the same story from another outlet.
COVERED = ROOT / "data" / "covered.json"
COVERED_DAYS = 3


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


def load_covered() -> list[dict]:
    if not COVERED.exists():
        return []
    cutoff = time.time() - COVERED_DAYS * 86400
    return [c for c in json.loads(COVERED.read_text()) if c["ts"] >= cutoff]


def save_covered(covered: list[dict], stories: list[dict]) -> None:
    now = time.time()
    covered = covered + [{"headline": s["headline"], "ts": now} for s in stories]
    COVERED.write_text(json.dumps(covered, indent=1, ensure_ascii=False))


def run_breaking(args) -> None:
    from datetime import datetime

    from src.curate import curate_breaking
    from src.fetch_news import fetch_topic

    out_dir = ROOT / "output" / f"breaking-{datetime.now(IST).strftime('%Y-%m-%d-%H%M')}"
    data = curate_breaking(fetch_topic(args.breaking), args.breaking, args.notes, args.slides)
    paths = render_slides(data, out_dir, breaking=True)
    caption = write_caption(data, out_dir)
    (out_dir / "stories.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID") and not args.no_send:
        send_slides(paths, caption)
    else:
        print(f"[done] files are in {out_dir} (Telegram not sent)")


def run(args) -> None:
    if args.breaking:
        return run_breaking(args)
    news_day = news_date()
    if args.date:   # cover exactly one IST calendar day
        news_day = datetime.fromisoformat(args.date).replace(tzinfo=IST)
    day = news_day.strftime("%Y-%m-%d")
    out_dir = ROOT / "output" / day
    if not args.sample and not args.force and LAST_EDITION.exists() and LAST_EDITION.read_text().strip() == day:
        print(f"[skip] the {day} edition was already sent; use --force to send it again")
        return

    if args.sample:
        data = json.loads((ROOT / "samples" / "sample_stories.json").read_text())
        hist = None
    else:
        from src.curate import curate
        from src.fetch_news import fetch_all
        hist = load_history()
        covered = load_covered()
        if args.date:
            start = news_day.timestamp()
            items = fetch_all(set(hist), since=start, until=start + 86400)
        else:
            items = fetch_all(set(hist))
        data = curate(items, recent=[c["headline"] for c in covered])

    paths = render_slides(data, out_dir, day=news_day)
    caption = write_caption(data, out_dir)
    (out_dir / "stories.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if hist is not None:
        save_history(hist, data["stories"])
        save_covered(covered, data["stories"])

    can_send = os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    if can_send and not args.no_send:
        send_slides(paths, caption)
        if not args.sample:
            LAST_EDITION.write_text(day + "\n")
    else:
        print(f"[done] files are in {out_dir} (Telegram not sent)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="render sample data, no APIs")
    ap.add_argument("--no-send", action="store_true", help="skip Telegram")
    ap.add_argument("--force", action="store_true", help="send today's edition even if it was already sent")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="make the edition for one past day (IST), using only news from that day")
    ap.add_argument("--breaking", metavar="TOPIC", help="make a short breaking-news post on one topic")
    ap.add_argument("--notes", default="", help="your angle or facts for the breaking post")
    ap.add_argument("--slides", type=int, default=2, choices=[1, 2, 3], help="story slides after the cover")
    args = ap.parse_args()
    try:
        run(args)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        if not args.sample:
            notify_failure(str(e), f"Breaking post on '{args.breaking}'" if args.breaking else "Today's AI carousel")
        sys.exit(1)
