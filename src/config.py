"""Everything you'd want to tweak lives here."""
import os

# Your Instagram handle, shown on every slide.
HANDLE = os.getenv("IG_HANDLE") or "@aichronicle.in"

# News date covered by edition No. 1. Each day after adds one to the edition number on the cover.
LAUNCH_DATE = "2026-10-26"

# How many stories per carousel. Instagram's app allows up to 20 slides,
# so cover + 10 stories + closing slide (12 total) is fine when you post manually.
TOP_N = int(os.getenv("TOP_N") or 10)

# Look back this many hours for news. 30h gives some overlap across time zones.
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS") or 30)

# Who you're writing for. The LLM uses this to pick and explain stories.
AUDIENCE = (
    "Tech-savvy people in India (students, developers, product folks) who follow AI "
    "but don't read research papers. They want to know what launched, what changed, "
    "and whether it affects the tools they use."
)

# Gemini model. Free-tier models change over time: check AI Studio if a call fails.
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-latest"
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL") or "gemini-flash-lite-latest"

# RSS feeds. A feed that fails or moves is skipped and logged, never fatal.
FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "NVIDIA": "https://blogs.nvidia.com/feed/",
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica": "https://arstechnica.com/ai/feed/",
    "VentureBeat": "https://venturebeat.com/category/ai/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
}

# Hacker News searches (free Algolia API, no key). Minimum points filters out noise.
HN_QUERIES = ["AI", "LLM", "OpenAI", "Anthropic", "Gemini", "GPT", "open source model"]
HN_MIN_POINTS = 80

# Feeds that are not AI-only get filtered by these words.
AI_KEYWORDS = [
    "ai", "a.i.", "llm", "gpt", "model", "openai", "anthropic", "claude", "gemini",
    "deepmind", "llama", "mistral", "copilot", "chatbot", "agent", "neural",
    "machine learning", "genai", "generative", "nvidia", "gpu", "diffusion",
]
AI_ONLY_SOURCES = {"OpenAI", "Google AI", "Google DeepMind", "Hugging Face",
                   "TechCrunch", "The Verge", "Ars Technica", "VentureBeat",
                   "MIT Technology Review"}

# Max candidate items sent to the LLM (keeps the request small and free-tier friendly).
MAX_CANDIDATES = 60

# Days to remember used story links, so the same story isn't repeated tomorrow.
HISTORY_DAYS = 7
