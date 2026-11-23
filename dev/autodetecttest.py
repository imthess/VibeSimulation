"""API key -> provider -> best live model, without a network (fake HTTP): ranking per service, rejected keys, unknown prefixes, missing-model retry."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.workspaces.ai_import.core import PROVIDERS
from vibesimulation.workspaces.ai_import.core import autodetect as A
from vibesimulation.workspaces.ai_import.core.key_detect import detect_provider
ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)

def gm(n, gen=True): return {"name": "models/" + n, "supportedGenerationMethods": ["generateContent"] if gen else ["embedContent"]}
GEMINI = {"models": [gm("gemini-2.0-flash"), gm("gemini-2.5-pro"), gm("gemini-2.5-flash"), gm("gemini-2.5-flash-lite"), gm("gemini-3-flash-preview"),
                     gm("gemini-2.5-flash-preview-tts"), gm("gemini-embedding-001", False), gm("gemini-2.5-flash-image"), gm("imagen-4.0"), gm("gemma-3-27b-it"),
                     gm("gemini-flash-latest"), gm("gemini-2.5-flash-native-audio-latest")]}
OPENAI = {"data": [{"id": i} for i in ("gpt-4o", "gpt-4o-2024-08-06", "gpt-4.1", "gpt-4.1-mini", "gpt-5", "gpt-5-mini", "gpt-5-pro", "gpt-4o-audio-preview", "gpt-4o-realtime-preview",
                                      "whisper-1", "text-embedding-3-small", "o3", "dall-e-3", "gpt-image-1")]}
ANTH = {"data": [{"id": i} for i in ("claude-opus-4-1-20250805", "claude-sonnet-4-5-20250929", "claude-sonnet-4-5", "claude-haiku-4-5", "claude-sonnet-4-20250514", "claude-opus-5-5", "claude-sonnet-5-5")]}
GROQ = {"data": [{"id": i, "active": True} for i in ("llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct", "whisper-large-v3", "meta-llama/llama-guard-4-12b")]}
OR = {"data": [{"id": "a/text:free", "architecture": {"input_modalities": ["text"]}, "pricing": {"prompt": "0"}},
               {"id": "old/vision:free", "created": 100, "context_length": 8000, "architecture": {"input_modalities": ["text", "image"]}, "pricing": {"prompt": "0"}},
               {"id": "new/vision:free", "created": 900, "context_length": 32000, "architecture": {"input_modalities": ["text", "image"]}, "pricing": {"prompt": "0"}},
               {"id": "paid/vision", "created": 999, "architecture": {"input_modalities": ["image"]}, "pricing": {"prompt": "0.001"}}]}
calls = []
def fake(status=200):
    def get(url, headers, timeout=8):
        calls.append(url)
        for host, data in (("generativelanguage", GEMINI), ("api.openai", OPENAI), ("api.anthropic", ANTH), ("api.groq", GROQ), ("openrouter", OR)):
            if host in url: return status, (data if status == 200 else None)
        return 404, None
    return get

# provider from the key's prefix (the classic and the newer Gemini formats)
chk("classic Gemini key", detect_provider("AIza" + "x" * 35) == "Gemini (free tier)")
chk("newer Gemini key (AQ.)", detect_provider("AQ.Ab8" + "x" * 40) == "Gemini (free tier)")
chk("Claude / OpenRouter / Groq / OpenAI keys", [detect_provider(k) for k in ("sk-ant-" + "a" * 30, "sk-or-v1-" + "a" * 30, "gsk_" + "a" * 30, "sk-proj-" + "a" * 30)]
    == ["Claude (paid API)", "OpenRouter (free models)", "Groq (free tier)", "OpenAI (paid API)"])

# best model per service
r = A.discover("AIza" + "x" * 35, None, None, PROVIDERS, fake())
chk("Gemini: provider detected and key accepted", r.provider == "Gemini (free tier)" and r.accepted is True)
chk("Gemini: best is the newest stable flash", r.best == "gemini-2.5-flash")
chk("Gemini: no tts / embedding / image / gemma models listed", not any(w in m for m in r.models for w in ("tts", "embed", "image", "gemma", "audio", "imagen")))
chk("Gemini: the live list is returned best-first (all usable)", r.models[0] == "gemini-2.5-flash" and "gemini-2.5-pro" in r.models and "gemini-flash-latest" in r.models)
chk("Gemini key goes to Google only", all("generativelanguage" in u for u in calls) and len(calls) == 1)
r = A.discover("sk-proj-" + "a" * 30, None, None, PROVIDERS, fake())
chk("OpenAI: best is gpt-5 (no dated, audio, image or pro first)", r.provider == "OpenAI (paid API)" and r.best == "gpt-5" and "gpt-4o-2024-08-06" not in r.models and r.models.index("gpt-5-pro") > r.models.index("gpt-4.1"))
r = A.discover("sk-ant-" + "a" * 30, None, None, PROVIDERS, fake())
chk("Claude: newest sonnet, aliases instead of dated twins", r.best == "claude-sonnet-5-5" and "claude-sonnet-4-5-20250929" not in r.models and "claude-sonnet-4-5" in r.models)
r = A.discover("gsk_" + "a" * 30, None, None, PROVIDERS, fake())
chk("Groq: a vision model, not whisper / guard / text-only", r.best == "meta-llama/llama-4-scout-17b-16e-instruct" and all("whisper" not in m and "guard" not in m and "3.3" not in m for m in r.models))
r = A.discover("sk-or-v1-" + "a" * 30, None, None, PROVIDERS, fake())
chk("OpenRouter: free vision models newest first, free router last unless chosen", r.models == ["new/vision:free", "old/vision:free", "openrouter/free"])

# problems
r = A.discover("AIza" + "x" * 35, None, None, PROVIDERS, fake(403))
chk("a rejected key is reported", r.provider == "Gemini (free tier)" and r.accepted is False and "did not accept" in r.message and r.best is None)
r = A.discover("AIza" + "x" * 35, None, None, PROVIDERS, lambda u, h, timeout=8: (0, None))
chk("offline: provider still known, no models, no false alarm", r.provider == "Gemini (free tier)" and r.accepted is None and not r.models)
calls.clear(); r = A.discover("totally-unknown-key-" + "z" * 20, "Groq (free tier)", None, PROVIDERS, fake())
chk("unknown prefix: only the provider the user chose is asked", r.provider == "Groq (free tier)" and len(calls) == 1 and "groq" in calls[0])
chk("unknown prefix: message does not claim a detection", "accepted the key" in r.message and "Detected" not in r.message)
calls.clear(); r = A.discover("totally-unknown-key-" + "z" * 20, "Ollama (local, free)", None, PROVIDERS, fake())
chk("unknown prefix and a local provider selected: nothing is sent anywhere", r.provider is None and not calls)
chk("empty key: nothing happens", A.discover("  ", "Gemini (free tier)", None, PROVIDERS, fake()).provider is None)
chk("custom server URL is respected", (lambda: (calls.clear(), A.discover("gsk_" + "a" * 30, None, {"Groq (free tier)": "https://proxy.example/"}, PROVIDERS, fake()), calls[0])[2])() .startswith("https://proxy.example/"))

# retry with a live model when the chosen one no longer exists
tries = []
def call(m):
    tries.append(m)
    if m == "gemini-3.8-flash": raise RuntimeError("The AI service returned HTTP 404:\nmodels/gemini-3.8-flash is not found")
    return "answer"
res = A.call_with_fallback("Gemini (free tier)", "gemini-3.8-flash", "AIza" + "x" * 35, None, call, PROVIDERS, fake())
chk("missing model: retried once with the best live model", res == ("answer", "gemini-2.5-flash") and tries == ["gemini-3.8-flash", "gemini-2.5-flash"])
def boom(m): raise RuntimeError("The AI service returned HTTP 429: quota")
try: A.call_with_fallback("Gemini (free tier)", "gemini-2.5-flash", "k", None, boom, PROVIDERS, fake()); chk("other errors are not retried", False)
except RuntimeError: chk("other errors are not retried", True)
chk("version() ignores date stamps", A.version("claude-sonnet-4-5-20250929") == (4, 5) and A.version("gpt-4.1") == (4, 1) and A.version("gemini-2.5-flash") == (2, 5))
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
