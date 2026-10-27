"""Turn curated stories into 1080x1350 PNG slides plus a caption file."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from . import config

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))


def news_date() -> datetime:
    """The day being covered: yesterday, in IST."""
    return datetime.now(IST) - timedelta(days=1)


def render_slides(data: dict, out_dir: Path, breaking: bool = False) -> list[Path]:
    """Daily edition: cover, stories, back page. Breaking: cover and stories only, dated today."""
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]))
    tpl = env.get_template("slide.html")
    stories = data["stories"]
    n = len(stories)
    d = datetime.now(IST) if breaking else news_date()
    today = datetime.now(IST).date()
    edition = max(1, (today - datetime.fromisoformat(config.LAUNCH_DATE).date()).days + 1)
    common = {"handle": config.HANDLE, "count": n, "edition": edition, "breaking": breaking,
              "date_label": f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"}

    pages = [tpl.render(kind="cover", hook=data.get("cover_hook", stories[0]["headline"]), **common)]
    pages += [tpl.render(kind="story", s=s, rank=i, **common) for i, s in enumerate(stories, 1)]
    if not breaking:
        pages.append(tpl.render(kind="outro", **common))

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for i, html in enumerate(pages, 1):
            page.set_content(html, wait_until="networkidle", timeout=30000)
            page.evaluate("document.fonts.ready")
            page.evaluate("window.fitText()")
            path = out_dir / f"slide_{i:02d}.png"
            page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            paths.append(path)
        browser.close()
    print(f"[render] {len(paths)} slides in {out_dir}")
    return paths


def write_caption(data: dict, out_dir: Path) -> Path:
    lines = [data.get("caption_hook", "Yesterday in AI, in one swipe."), ""]
    for i, s in enumerate(data["stories"], 1):
        lines.append(f"{i}. {s['headline']}")
    lines += ["", "Sources:"]
    for i, s in enumerate(data["stories"], 1):
        lines.append(f"{i}. {s['source']}: {s['url']}")
    lines += ["", f"Follow {config.HANDLE} for a daily AI briefing and breaking AI news.", ""]
    lines.append(" ".join(f"#{h}" for h in data.get("hashtags", [])))
    text = "\n".join(lines)
    if len(text) > 2200:  # Instagram's caption limit: drop URLs, keep source names
        text = "\n".join(l.split(": http")[0] for l in lines)
    path = out_dir / "caption.txt"
    path.write_text(text[:2200], encoding="utf-8")
    return path
