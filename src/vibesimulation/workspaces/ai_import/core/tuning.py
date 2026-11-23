"""The token-saving switches (Settings > AI & Import), read by the AI back ends. The window copies the saved settings here with ``apply``
so the providers (which run in background threads) need no access to the window."""
DEFAULTS = {
    "limit_reasoning": True,     # stop / limit the model's hidden "thinking" (it is billed as output tokens)
    "compact_answer": True,      # ask for the short answer format instead of JSON
    "record_usage": True,        # keep the token history
    "openrouter_router": False,  # OpenRouter: let its free router pick the model (unpredictable, often a slow thinking model) instead of the best free picture model
}
_state = dict(DEFAULTS)


def apply(cfg):
    for k, v in DEFAULTS.items(): _state[k] = bool(cfg.get("ai_" + k, v))
    _state["openrouter_router"] = cfg.get("ai_openrouter_pick", "best") == "router"


def get(key): return _state.get(key, DEFAULTS.get(key))
