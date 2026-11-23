"""Which service does an API key belong to? Looked up from the key's own prefix, so the user only has to paste it."""
import re

# (provider name as listed in providers.PROVIDERS, regular expression). The first match wins, so specific prefixes come before general ones.
RULES = (
    ("Claude (paid API)", re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,}$")),
    ("OpenRouter (free models)", re.compile(r"^sk-or-[A-Za-z0-9_\-]{20,}$")),
    ("Groq (free tier)", re.compile(r"^gsk_[A-Za-z0-9]{20,}$")),
    ("Gemini (free tier)", re.compile(r"^(?:AIza[0-9A-Za-z_\-]{30,}|AQ\.[0-9A-Za-z_\-.]{30,})$")),      # classic AIza... keys and the newer AQ.... keys
    ("OpenAI (paid API)", re.compile(r"^sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}$")),
)


def detect_provider(key):
    """The provider name for a pasted key, or None when the key is not recognised."""
    k = (key or "").strip().strip("\"'")
    if k.lower().startswith("bearer "): k = k[7:].strip()
    for name, rx in RULES:
        if rx.match(k): return name
    return None


def clean_key(key):
    """The key without surrounding spaces, quotes or a leading 'Bearer '."""
    k = (key or "").strip().strip("\"'")
    return k[7:].strip() if k.lower().startswith("bearer ") else k
