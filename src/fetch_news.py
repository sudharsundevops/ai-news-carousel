"""Collect candidate AI stories from RSS feeds and Hacker News."""
import re
import time
from calendar import timegm
from html import unescape

import feedparser
import requests

from . import config

UA = {"User-Agent": "ai-news-carousel/1.0 (+https://github.com)"}


def _clean(text: str, limit: int = 400) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _is_ai(text: str) -> bool:
    t = f" {text.lower()} "
    return any(re.search(rf"\b{re.escape(k)}\b", t) for k in config.AI_KEYWORDS)


def fetch_rss(since_ts: float) -> list[dict]:
    items = []
    for source, url in config.FEEDS.items():
        try:
            resp = requests.get(url, headers=UA, timeout=20)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:  # noqa: BLE001
            print(f"[rss] skipped {source}: {e}")
            continue
        count = 0
        for e in feed.entries:
            parsed = e.get("published_parsed") or e.get("updated_parsed")
            if not parsed:
                continue
            ts = timegm(parsed)
            if ts < since_ts:
                continue
            title = _clean(e.get("title", ""), 200)
            summary = _clean(e.get("summary", ""), 900)
            if source not in config.AI_ONLY_SOURCES and not _is_ai(f"{title} {summary}"):
                continue
            items.append({"source": source, "title": title, "summary": summary,
                          "url": e.get("link", ""), "ts": ts, "points": 0})
            count += 1
        print(f"[rss] {source}: {count} recent")
    return items


def fetch_hn(since_ts: float) -> list[dict]:
    items = []
    for q in config.HN_QUERIES:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": q, "tags": "story", "hitsPerPage": 30,
                        "numericFilters": f"created_at_i>{int(since_ts)},points>{config.HN_MIN_POINTS}"},
                headers=UA, timeout=20)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            print(f"[hn] skipped '{q}': {e}")
            continue
        for h in resp.json().get("hits", []):
            title = h.get("title") or ""
            if not _is_ai(title):
                continue
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
            items.append({"source": "Hacker News", "title": _clean(title, 200), "summary": "",
                          "url": url, "ts": h.get("created_at_i", 0),
                          "points": h.get("points", 0)})
    print(f"[hn] {len(items)} hits (before dedupe)")
    return items


def fetch_topic(topic: str, days: int = 2, limit: int = 25) -> list[dict]:
    """Latest coverage of one topic, for breaking posts: Google News search plus Hacker News."""
    since = time.time() - days * 86400
    items = []
    try:
        resp = requests.get("https://news.google.com/rss/search", headers=UA, timeout=20,
                            params={"q": f"{topic} when:{days}d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        resp.raise_for_status()
        for e in feedparser.parse(resp.content).entries:
            parsed = e.get("published_parsed")
            ts = timegm(parsed) if parsed else time.time()
            if ts < since:
                continue
            # Google News titles end with " - Publisher"; keep the publisher as the source.
            title, _, publisher = _clean(e.get("title", ""), 240).rpartition(" - ")
            items.append({"source": publisher or "Google News", "title": title or e.get("title", ""),
                          "summary": _clean(e.get("summary", ""), 900), "url": e.get("link", ""),
                          "ts": ts, "points": 0})
    except Exception as e:  # noqa: BLE001
        print(f"[topic] Google News skipped: {e}")
    try:
        resp = requests.get("https://hn.algolia.com/api/v1/search_by_date", headers=UA, timeout=20,
                            params={"query": topic, "tags": "story", "hitsPerPage": 15,
                                    "numericFilters": f"created_at_i>{int(since)}"})
        resp.raise_for_status()
        for h in resp.json().get("hits", []):
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
            items.append({"source": "Hacker News", "title": _clean(h.get("title") or "", 200),
                          "summary": "", "url": url, "ts": h.get("created_at_i", 0),
                          "points": h.get("points", 0)})
    except Exception as e:  # noqa: BLE001
        print(f"[topic] Hacker News skipped: {e}")

    seen, out = set(), []
    for it in sorted(items, key=lambda x: -x["ts"]):
        key = _norm_title(it["title"])
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    out = out[:limit]
    for i, it in enumerate(out):
        it["id"] = i
    print(f"[topic] {len(out)} items for '{topic}'")
    return out


def fetch_all(used_urls: set[str]) -> list[dict]:
    since = time.time() - config.LOOKBACK_HOURS * 3600
    raw = fetch_rss(since) + fetch_hn(since)

    seen_titles, seen_urls, out = set(), set(used_urls), []
    # Official/editorial sources first, then HN by points.
    raw.sort(key=lambda x: (x["source"] == "Hacker News", -x["points"], -x["ts"]))
    for it in raw:
        key = _norm_title(it["title"])
        if not key or key in seen_titles or it["url"] in seen_urls:
            continue
        seen_titles.add(key)
        seen_urls.add(it["url"])
        out.append(it)

    out = out[: config.MAX_CANDIDATES]
    for i, it in enumerate(out):
        it["id"] = i
    print(f"[fetch] {len(out)} candidates after dedupe")
    return out
