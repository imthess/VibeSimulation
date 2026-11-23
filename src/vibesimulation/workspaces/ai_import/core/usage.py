"""Real token usage: what every AI call cost (as reported by the service), and a history to look at in Settings > AI & Import.

Providers call ``note`` with the raw answer; ``last`` gives the newest entry (shown after a conversion); ``sink`` (set by the app) stores it."""
import threading
import time

from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import tuning

MAX_ENTRIES = 300
_local = threading.local()
sink = None                       # optional callable(entry), called for every call (tests, extra logging)
pending = []                      # entries made on worker threads; the window moves them into its settings with ``drain`` on its own thread


def normalize(d):
    """{'prompt','output','reasoning','total'} from a raw service answer (Gemini, OpenAI-like, Anthropic or Ollama); zeros when it reports nothing."""
    if not isinstance(d, dict): return dict(prompt=0, output=0, reasoning=0, total=0)
    g = d.get("usageMetadata")
    if isinstance(g, dict):
        p, c, t = g.get("promptTokenCount", 0), g.get("candidatesTokenCount", 0), g.get("thoughtsTokenCount", 0)
        return _mk(p, c + t, t, g.get("totalTokenCount"))
    u = d.get("usage")
    if isinstance(u, dict):
        if "prompt_tokens" in u:
            r = (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
            return _mk(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), r, u.get("total_tokens"))
        if "input_tokens" in u: return _mk(u.get("input_tokens", 0), u.get("output_tokens", 0), 0, None)
    if "prompt_eval_count" in d or "eval_count" in d: return _mk(d.get("prompt_eval_count", 0), d.get("eval_count", 0), 0, None)
    return dict(prompt=0, output=0, reasoning=0, total=0)


def _mk(p, o, r, t):
    p, o, r = int(p or 0), int(o or 0), int(r or 0)
    return dict(prompt=p, output=o, reasoning=r, total=int(t or (p + o)))


def context(what):
    """Label for the next calls on this thread: 'picture' (image to circuit) or 'assistant' (AI button)."""
    _local.what = what


def note(provider, model, raw):
    """Record one call. Returns the entry."""
    e = dict(normalize(raw), t=int(time.time()), provider=provider, model=model, what=getattr(_local, "what", "picture"))
    _local.last = e
    if e["total"]: activity.log("tokens", f"{provider} {model}: " + summary(e), "ok", **{k: e[k] for k in ("prompt", "output", "reasoning", "total")})
    else: activity.log("tokens", f"{provider} {model}: the service did not report token usage", "info")
    if tuning.get("record_usage"): pending.append(e)
    if sink:
        try: sink(e)
        except Exception: pass
    return e


def last():
    """Newest entry made on this thread (or None)."""
    return getattr(_local, "last", None)


def clear_last(): _local.last = None


def add(cfg, entry):
    """Append to ``cfg['ai_usage']`` (newest last, capped)."""
    log = cfg.setdefault("ai_usage", [])
    log.append(entry)
    del log[:-MAX_ENTRIES]


def drain(cfg):
    """Move the entries made since the last call into ``cfg['ai_usage']``; returns how many (call from the window's thread)."""
    n = 0
    while pending: add(cfg, pending.pop(0)); n += 1
    return n


def totals(entries):
    """Sums over entries: calls, prompt, output, reasoning, total."""
    s = dict(calls=len(entries), prompt=0, output=0, reasoning=0, total=0)
    for e in entries:
        for k in ("prompt", "output", "reasoning", "total"): s[k] += int(e.get(k, 0))
    return s


def summary(e):
    """One line for the status bar after a call."""
    if not e or not e.get("total"): return ""
    r = f" (of which thinking {e['reasoning']:,})" if e.get("reasoning") else ""
    return f"{e['total']:,} tokens used: {e['prompt']:,} in, {e['output']:,} out{r}"


def when(e): return time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("t", 0)))
