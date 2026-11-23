"""Find out, from a pasted API key alone, which service it is for and which model to use.

1. ``detect_provider`` (``key_detect.py``) reads the key's prefix. If the prefix is unknown, the provider the user already selected is used;
   the key is never sent to services it does not belong to.
2. ``discover`` asks that one service for its *live* model list with the key. That checks the key and shows only models that exist today
   (no out-of-date names), and ``rank`` puts the best picture-capable model first.
3. ``call_with_fallback`` runs a request and, if the service says the model does not exist, retries once with the best live model.

Every function takes ``get`` (default ``http_get``) so tests can run without a network."""
import json
import re
import time
import http.client
import urllib.error
import urllib.request

from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import tuning
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key, detect_provider


# ------------------------------------------------------------------------------------------------- network
def http_get(url, headers, timeout=25):
    """(status, parsed JSON or None). Status 0 means the service could not be reached."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "VibeSimulation", **headers})
    for h in headers.values(): activity.secret(h.replace("Bearer ", ""))
    t0 = time.time(); host = url.split("/")[2]
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace")); activity.log("net", f"GET {host}{url[url.index('/', 8):].split('?')[0]}  HTTP {r.status}  {time.time() - t0:.1f} s", "ok")
            return r.status, data
    except urllib.error.HTTPError as e:
        activity.log("net", f"GET {host}  HTTP {e.code}  {time.time() - t0:.1f} s", "error"); return e.code, None
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
        activity.log("net", f"GET {host} failed after {time.time() - t0:.1f} s: {e}", "error"); return 0, None


# ------------------------------------------------------------------------------------------------- ranking helpers
def version(name):
    """Numbers in a model name, without date stamps: 'gemini-2.5-flash' -> (2, 5); 'claude-sonnet-4-5-20250929' -> (4, 5); 'gpt-4.1' -> (4, 1)."""
    name = re.sub(r"(?<!\d)(?:20)?\d{2}[-_]?\d{2}[-_]?\d{2}(?!\d)|\b\d{8}\b", "", name)
    out = []
    for a, b in re.findall(r"(\d+)(?:[.\-_](\d{1,2})(?!\d))?", name):
        out.append(int(a))
        if b: out.append(int(b))
    return tuple(out)


def _bad(name, words):
    low = name.lower()
    return any(w in low for w in words)


def _newest_first(items, family):
    """Sort model names: family rank first (smaller is better), then newest version."""
    return sorted(items, key=lambda n: (family(n), 0 if version(n) else 1, tuple(-v for v in version(n)), len(n)))      # un-numbered aliases (…-latest) after numbered models


# ------------------------------------------------------------------------------------------------- one lister per service
def _gemini(key, base, get):
    st, d = get(f"{base}/v1beta/models?pageSize=200", {"x-goog-api-key": key})
    if st != 200 or not d: return st, []
    names = [m["name"].split("/", 1)[-1] for m in d.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    skip = ("tts", "embed", "imagen", "veo", "aqa", "image", "live", "audio", "robotics", "computer", "learnlm", "native", "customtools", "gemma", "exp")
    ok = [n for n in names if n.startswith("gemini") and not _bad(n, skip)]
    def family(n):
        stable = 0 if not re.search(r"preview|exp|\d{2}-\d{2}$", n) else 1
        kind = 2 if "lite" in n else 0 if "flash" in n else 1                      # flash (free tier friendly) < pro < lite
        return (kind if kind != 2 else 1.5, stable)
    return st, _newest_first(ok, family)


def _openai_like(url, keep, skip, family):
    def lister(key_, base, get):
        st, d = get(url.format(base=base), {"Authorization": "Bearer " + key_})
        if st != 200 or not d: return st, []
        ids = [m["id"] for m in d.get("data", []) if isinstance(m, dict) and "id" in m]
        return st, _newest_first([i for i in ids if keep(i) and not _bad(i, skip)], family)
    return lister


_openai = _openai_like("{base}/v1/models",
                       lambda i: re.match(r"^(gpt-(4o|4\.1|5)|o\d)", i) is not None and not re.search(r"-\d{4}-\d{2}-\d{2}$", i),
                       ("audio", "realtime", "transcribe", "tts", "image", "search", "instruct", "codex", "embedding", "moderation", "chat-latest"),
                       lambda n: 3 if re.match(r"o\d", n) else 2 if "pro" in n else 1 if ("mini" in n or "nano" in n) else 0)


def _anthropic(key, base, get):
    st, d = get(f"{base}/v1/models?limit=100", {"x-api-key": key, "anthropic-version": "2023-06-01"})
    if st != 200 or not d: return st, []
    ids = [m["id"] for m in d.get("data", []) if "id" in m]
    ids = [i for i in ids if not (re.search(r"-\d{8}$", i) and re.sub(r"-\d{8}$", "", i) in ids)] or ids
    return st, _newest_first(ids, lambda n: 0 if "sonnet" in n else 1 if "opus" in n else 2)


def _groq(key, base, get):
    st, d = get(f"{base}/openai/v1/models", {"Authorization": "Bearer " + key})
    if st != 200 or not d: return st, []
    ids = [m["id"] for m in d.get("data", []) if m.get("active", True)]
    vis = [i for i in ids if any(w in i.lower() for w in ("llama-4", "vision", "scout", "maverick")) and not _bad(i, ("guard", "whisper", "tts"))]
    return st, _newest_first(vis, lambda n: 0 if "scout" in n else 1)


def _openrouter(key, base, get):
    root = base.rstrip("/"); root = root[:-4] if root.endswith("/api") else root                  # the saved address ends in /api, like the chat address
    st, d = get(f"{root}/api/v1/models", {"Authorization": "Bearer " + key})
    if st != 200 or not d: return st, []
    rows = []
    for m in d.get("data", []):
        mods = (m.get("architecture") or {}).get("input_modalities") or []
        free = str(m.get("id", "")).endswith(":free") or str((m.get("pricing") or {}).get("prompt", "1")) in ("0", "0.0")
        if "image" in mods and free: rows.append((-(m.get("created") or 0), -(m.get("context_length") or 0), m["id"]))
    ids = [r[2] for r in sorted(rows)]
    return st, (["openrouter/free"] + ids) if tuning.get("openrouter_router") or not ids else ids + ["openrouter/free"]      # the router is only first when the user chose it


LISTERS = {"Gemini (free tier)": _gemini, "OpenAI (paid API)": _openai, "Claude (paid API)": _anthropic,
           "Groq (free tier)": _groq, "OpenRouter (free models)": _openrouter}


# ------------------------------------------------------------------------------------------------- public
class Found:
    """Result of ``discover``: provider (or None), live models best-first, a short message and whether the key was accepted."""
    def __init__(self, provider=None, models=(), message="", accepted=None):
        self.provider, self.models, self.message, self.accepted = provider, list(models), message, accepted

    @property
    def best(self): return self.models[0] if self.models else None


def discover(key, selected=None, bases=None, providers=None, get=http_get):
    """Which service is this key for, and what can it run? ``selected`` is the provider currently chosen in the window (used when the
    key's prefix says nothing); ``bases`` maps provider name -> server URL; ``providers`` is ``PROVIDERS`` (for default URLs)."""
    k = clean_key(key); bases = bases or {}
    if not k: return Found(message="")
    known = detect_provider(k); name = known or (selected if selected in LISTERS else None)
    if name is None:
        return Found(message="This key's service could not be recognised: choose the provider yourself.", accepted=None)
    base = (bases.get(name) or (providers[name].base if providers and name in providers else "")).rstrip("/")
    if not base: return Found(name, message=f"Detected: {name}")
    st, models = LISTERS[name](k, base, get)
    lead = f"Detected: {name}" if known else f"{name} accepted the key"
    if st == 200:
        return Found(name, models, lead + (f"  ·  model chosen: {models[0]}" if models else "  ·  no usable model listed, choose one"), True)
    if st in (401, 403): return Found(name, message=f"{name} did not accept this key (HTTP {st}). Check that it is copied completely.", accepted=False)
    if st == 429: return Found(name, message=f"{lead} (busy right now; model list not loaded)" if known else f"{name} is busy right now; the key could not be checked", accepted=True if known else None)
    return Found(name, message=f"Detected: {name} (could not load its model list: offline?)" if known else "This key could not be checked (offline?).", accepted=None)


def best_model(name, key, base=None, providers=None, get=http_get):
    """The best live model of a service, or None."""
    return discover(key, name, {name: base} if base else None, providers, get).best if name in LISTERS else None


def is_missing_model(msg):
    low = str(msg).lower()
    return "http 404" in low or ("model" in low and ("not found" in low or "does not exist" in low or "not supported" in low or "decommissioned" in low))


def call_with_fallback(name, model, key, base, call, providers=None, get=http_get):
    """call(model) -> text. If the service reports the model as missing, try once with the best live model.
    Returns (text, model_used); raises the original error if there is nothing better to try."""
    try:
        return call(model), model
    except RuntimeError as e:
        if not is_missing_model(e): raise
        alt = best_model(name, key, base, providers, get)
        activity.log("model", f"{model} was not found; best live model: {alt or 'none found'}", "warn")
        if not alt or alt == model: raise
        return call(alt), alt
