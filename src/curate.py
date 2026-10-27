"""Ask Gemini (free tier) to pick the top stories and write slide copy.

The model only returns item ids plus text. Links and source names are attached
by code from the fetched data, so the model can't invent a URL.
"""
import json
import os
import time

import requests

from . import config

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = f"""You are the editor of a daily Instagram carousel about AI news.
Audience: {config.AUDIENCE}

Rules:
- Use ONLY facts present in the candidate items. Never add numbers, dates, prices or names that aren't there.
- If an item is vague, skip it rather than guess.
- Write in your own words. Never copy sentences from the items.
- Plain English, no hype words (revolutionary, game-changer, insane, mind-blowing).
- Prefer launches, releases, policy changes and things people can try, over opinion pieces.
- Merge items that cover the same story; use the most informative one's id.
- Order by how much the audience would care, most important first.
"""

FORMAT = """Return JSON only, in exactly this shape:
{
  "cover_hook": "max 8 words, the biggest story as a hook",
  "stories": [
    {
      "id": <candidate id as integer>,
      "tag": "one of: Launch, Model, Research, Tool, Funding, Policy, Business, Open source",
      "headline": "max 9 words",
      "summary": "what happened, max 28 words, 1-2 sentences",
      "why": "why it matters to the audience, max 16 words"
    }
  ],
  "caption_hook": "one line to open the caption, max 15 words",
  "hashtags": ["8 to 12 relevant hashtags without spaces"]
}
"""


BREAKING_FORMAT = """Return JSON only, in exactly this shape:
{
  "cover_hook": "max 8 words, the news itself as a hook",
  "stories": [
    {
      "id": <id of the candidate item this slide is based on, as integer>,
      "tag": "a short angle label, max 2 words, like: What happened, Why now, What changes",
      "headline": "max 9 words",
      "summary": "max 28 words, 1-2 sentences",
      "why": "why it matters to the audience, max 16 words"
    }
  ],
  "caption_hook": "one line to open the caption, max 15 words",
  "hashtags": ["6 to 10 relevant hashtags without spaces"]
}
"""


def _call(model: str, prompt: str, key: str, system: str = SYSTEM, timeout: int = 120) -> dict:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
    }
    delay = 15
    for attempt in range(1, 5):
        r = requests.post(API.format(model=model), json=body, timeout=timeout,
                          headers={"x-goog-api-key": key})
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        if r.status_code in (429, 500, 503) and attempt < 4:
            print(f"[gemini] {model} returned {r.status_code}, retrying in {delay}s")
            time.sleep(delay)
            delay *= 2
            continue
        raise RuntimeError(f"Gemini {model} failed ({r.status_code}): {r.text[:300]}")
    raise RuntimeError("unreachable")


def _validate(data: dict, items: list[dict], top_n: int, minimum: int = 3, allow_repeat: bool = False) -> dict:
    by_id = {it["id"]: it for it in items}
    stories, used = [], set()
    for s in data.get("stories", []):
        try:
            sid = int(s["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if sid not in by_id or (sid in used and not allow_repeat):
            continue
        used.add(sid)
        src = by_id[sid]
        stories.append({
            "tag": str(s.get("tag", "News"))[:20],
            "headline": str(s.get("headline", "")).strip(),
            "summary": str(s.get("summary", "")).strip(),
            "why": str(s.get("why", "")).strip(),
            "source": src["source"],
            "url": src["url"],
        })
        if len(stories) == top_n:
            break
    if len(stories) < minimum:
        raise RuntimeError(f"Only {len(stories)} usable stories came back")
    data["stories"] = stories
    data["hashtags"] = [h.lstrip("#").replace(" ", "") for h in data.get("hashtags", [])][:12]
    return data


def curate(items: list[dict], top_n: int = config.TOP_N) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    if len(items) < 3:
        raise RuntimeError(f"Only {len(items)} candidate items found; nothing to curate")

    lines = [f"[{it['id']}] ({it['source']}) {it['title']} :: {it['summary']}" for it in items]
    prompt = (f"Pick the top {top_n} stories from these candidates.\n\n"
              + "\n".join(lines) + "\n\n" + FORMAT)

    for model in (config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL):
        try:
            return _validate(_call(model, prompt, key), items, top_n)
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] {model}: {e}")
            last = e
    raise RuntimeError(f"All Gemini models failed: {last}")


def curate_breaking(items: list[dict], topic: str, notes: str = "", slides: int = 2) -> dict:
    """Write a short breaking-news post about one topic, steered by the editor's notes."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    if not items:
        raise RuntimeError(f"No recent news found for '{topic}'. Try different words.")

    system = SYSTEM + """
This is a breaking-news post about a single topic, not the daily roundup.
- Every slide covers the same story from a different angle, so slides must not repeat each other.
- The editor's notes set the angle and emphasis. Facts stated in the notes come from the editor and may be used.
- If candidate items disagree, say what is confirmed and what is reported.
"""
    lines = [f"[{it['id']}] ({it['source']}) {it['title']} :: {it['summary']}" for it in items]
    prompt = (f"Topic: {topic}\nEditor's notes: {notes or '(none)'}\n\n"
              f"Write exactly {slides} slides about this topic from these candidates.\n\n"
              + "\n".join(lines) + "\n\n" + BREAKING_FORMAT)

    for model in (config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL):
        try:
            return _validate(_call(model, prompt, key, system, timeout=45), items, slides, minimum=1, allow_repeat=True)
        except Exception as e:  # noqa: BLE001
            print(f"[gemini] {model}: {e}")
            last = e
    raise RuntimeError(f"All Gemini models failed: {last}")
