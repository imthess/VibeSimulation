"""A second AI, only for the AI button (Settings > AI & Import > "Use a different AI for the AI button").
The picture import keeps using the service chosen on the Import & AI page; the AI button uses this one, e.g. a local Ollama model, while the
pictures go to a stronger cloud model. Keys live in the keyring (or the session) under a name of their own, never in the settings file."""
import os

from vibesimulation.workspaces.ai_import.core import secrets
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key

_memory = {}


def _slot(provider): return "AI button: " + provider


def enabled(cfg): return bool(cfg.get("ai_sep_on")) and bool(cfg.get("ai_sep", {}).get("provider"))


def get(cfg):
    """(provider, model, base) saved for the AI button."""
    p = cfg.get("ai_sep", {}) or {}
    return p.get("provider", ""), p.get("model", ""), p.get("base", "")


def key(provider, env=None):
    return clean_key(_memory.get(provider) or secrets.get_key(_slot(provider)) or (os.environ.get(env, "") if env else ""))


def save(cfg, provider, model, base, key_text, providers):
    """Store the choice; returns a short note about where the key went ('' when no key is needed)."""
    cfg["ai_sep"] = {"provider": provider, "model": model, "base": base}
    k = clean_key(key_text or "")
    if not providers[provider].env: return ""
    if k:
        _memory[provider] = k
        return "key kept in the system keychain" if secrets.set_key(_slot(provider), k) else "key kept for this session only (install 'keyring' to keep it)"
    return ""


def describe(cfg):
    p, m, _ = get(cfg)
    return f"{p} · {m}" if p else "not set"
