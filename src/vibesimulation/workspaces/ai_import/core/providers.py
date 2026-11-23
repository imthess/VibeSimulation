"""AI back ends (Strategy pattern): each provider class knows how to send the picture to one kind of service.

To add a service, subclass ``Provider``, implement ``ask`` and add it to ``PROVIDERS``.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import tuning, usage
from vibesimulation.workspaces.ai_import.core.prompt import build_prompt
TIMEOUT = 180          # seconds a cloud service may take in all; then the request is given up (a busy free model can otherwise keep you waiting for ever)


def _read_within(r, seconds):
    """The whole answer, but never longer than ``seconds`` in total. ``read1`` returns whatever has arrived: services such as OpenRouter keep a
    connection alive with a few bytes while a model is busy, and a plain ``read(n)`` would wait for all n bytes and never check the clock."""
    end = time.monotonic() + seconds; parts = []
    while True:
        if time.monotonic() > end: raise RuntimeError(f"The AI service did not answer within {seconds // 60} minutes (a busy free model?). Press Convert again, or choose another model.")
        chunk = r.read1(16384)
        if not chunk: return b"".join(parts)
        parts.append(chunk)


def _summary(url, body):
    """(model, options text) of a request, for the activity log."""
    model = body.get("model") or (url.split("/models/")[-1].split(":")[0] if "/models/" in url else "")
    gc = body.get("generationConfig", {}) if isinstance(body.get("generationConfig"), dict) else {}
    opts = [f"{k}={body[k]}" for k in ("reasoning", "reasoning_effort", "max_tokens", "response_format", "temperature") if k in body]
    opts += [f"{k}={gc[k]}" for k in ("thinkingConfig", "maxOutputTokens", "responseMimeType") if k in gc]
    return model, ", ".join(opts) or "no extra options"


def _post(url, headers, body, key=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    for h in headers.values(): activity.secret(h.replace("Bearer ", ""))
    activity.secret(key)
    model, opts = _summary(url, body); host = urllib.parse.urlparse(url).netloc; size = len(req.data)
    activity.LOG.last_request = dict(time=time.time(), url=url, model=model, bytes=size, body=activity.shrink(body)); activity.LOG.last_response = None
    activity.log("net", f"POST {host}  model {model}  {size // 1024:,} KB sent  ({opts})")
    jid = activity.LOG.begin(f"waiting for {model or host}", source="net"); stop_beat = activity.heartbeat(jid, model or host); t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = _read_within(r, timeout); status = r.status
        d = json.loads(raw.decode("utf-8", "replace"))
        activity.LOG.last_response = dict(time=time.time(), status=status, seconds=round(time.time() - t0, 1), bytes=len(raw), body=activity.shrink(d, 400))
        activity.LOG.end(jid, True, f"HTTP {status}, {len(raw) // 1024:,} KB received"); return d
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        if key:
            detail = detail.replace(key, "***")
        activity.LOG.last_response = dict(time=time.time(), status=e.code, seconds=round(time.time() - t0, 1), bytes=len(detail), body=activity.redact(detail))
        activity.LOG.end(jid, False, f"HTTP {e.code}: {activity.redact(detail)[:300]}")
        raise RuntimeError(f"The AI service returned HTTP {e.code}:\n{detail}")
    except urllib.error.URLError as e:
        activity.LOG.end(jid, False, f"could not reach {host}: {e.reason}"); raise RuntimeError(f"Could not reach the AI service: {e.reason}")
    except RuntimeError as e:
        activity.LOG.end(jid, False, str(e)); raise
    except OSError as e:                                                         # includes socket timeouts
        activity.LOG.end(jid, False, f"no answer in time: {e}"); raise RuntimeError(f"The AI service did not answer in time ({e}). Press Convert again, or choose another model.")
    finally:
        stop_beat()


def _post_trim(url, headers, body, key, drop, model, label, timeout=TIMEOUT):
    """Like ``_post`` but, if the service refuses (HTTP 400) a token-saving option in ``drop`` (a list of ways to remove it from the body),
    removes the options and tries again. Records the token usage of the answer."""
    try:
        d = _post(url, headers, body, key, timeout)
    except RuntimeError as e:
        if "HTTP 400" not in str(e) or not drop: raise
        activity.log("net", "the service refused a token-saving option (HTTP 400): trying again without it", "warn")
        for f in drop: f(body)
        d = _post(url, headers, body, key, timeout)
    usage.note(label, model, d)
    return d


class Provider(ABC):
    kind = ""
    env = None             # environment variable that may hold the API key
    show_base = False      # let the user edit the server URL
    local = False

    def __init__(self, name, models, base, help_text):
        self.name, self.models, self.base, self.help = name, models, base, help_text

    @abstractmethod
    def ask(self, model, key, img, mime, base=None, prompt=None, want_json=True):
        """Send the image + prompt (the built-in one when prompt is None); return the model's text answer. want_json: the answer is a JSON circuit, not code."""

    def chat(self, model, key, system, user, base=None, want_json=False):
        """Text only (no picture): one question, one answer. Used by the AI assistant bar."""
        raise RuntimeError(f"{self.name} cannot be used for text requests yet.")

    def url(self, base):
        return (base or self.base).strip().rstrip("/")


class GeminiProvider(Provider):
    kind, env = "gemini", "GEMINI_API_KEY"

    def _go(self, model, key, base, body):
        """Send; with the reasoning limit on, models that think (2.5 and newer) get a small thinking budget."""
        drop = []
        if tuning.get("limit_reasoning") and re.match(r"gemini-(2\.5|[3-9])", model):
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0 if "lite" in model else 1024}
            drop = [lambda b: b["generationConfig"].pop("thinkingConfig", None)]
        return _post_trim(f"{self.url(base)}/v1beta/models/{model}:generateContent", {"x-goog-api-key": key}, body, key, drop, model, self.name)

    def ask(self, model, key, img, mime, base=None, prompt=None, want_json=True):
        b64 = base64.b64encode(img).decode()
        gc = {"temperature": 0, **({"responseMimeType": "application/json"} if want_json else {"maxOutputTokens": 16000})}
        d = self._go(model, key, base, {"contents": [{"parts": [{"text": prompt or build_prompt()}, {"inline_data": {"mime_type": mime, "data": b64}}]}], "generationConfig": gc})
        try:
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError("Gemini returned no answer: " + json.dumps(d)[:300])


    def chat(self, model, key, system, user, base=None, want_json=False):
        cfg = {"temperature": 0.2, "maxOutputTokens": 16000}
        if want_json: cfg["responseMimeType"] = "application/json"
        d = self._go(model, key, base, {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": cfg})
        try:
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError("Gemini returned no answer: " + json.dumps(d)[:300])


class AnthropicProvider(Provider):
    kind, env = "anthropic", "ANTHROPIC_API_KEY"

    def ask(self, model, key, img, mime, base=None, prompt=None, want_json=True):
        b64 = base64.b64encode(img).decode()
        d = _post_trim(f"{self.url(base)}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, {"model": model, "max_tokens": 4000 if want_json else 12000, "temperature": 0,
                   "messages": [{"role": "user", "content": [
                       {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                       {"type": "text", "text": prompt or build_prompt()}]}]}, key, [], model, self.name)
        try:
            return "".join(p.get("text", "") for p in d["content"] if p.get("type") == "text")
        except (KeyError, TypeError):
            raise RuntimeError("Claude returned no answer: " + json.dumps(d)[:300])


    def chat(self, model, key, system, user, base=None, want_json=False):
        d = _post_trim(f"{self.url(base)}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
                       {"model": model, "max_tokens": 16000, "temperature": 0.2, "system": system, "messages": [{"role": "user", "content": user}]}, key, [], model, self.name)
        try:
            return "".join(p.get("text", "") for p in d["content"] if p.get("type") == "text")
        except (KeyError, TypeError):
            raise RuntimeError("Claude returned no answer: " + json.dumps(d)[:300])


class OpenAICompatibleProvider(Provider):
    """OpenAI, OpenRouter, Groq and any server that speaks the OpenAI chat API."""
    kind = "openai"

    def __init__(self, name, models, base, help_text, env, json_mode=False, show_base=False):
        super().__init__(name, models, base, help_text)
        self.env, self.json_mode, self.show_base = env, json_mode, show_base

    def _go(self, model, key, base, body, want_json):
        """Send; with the reasoning limit on, services that support it are told to think little and the answer is capped."""
        drop = []
        if tuning.get("limit_reasoning"):
            if self.name.startswith("OpenRouter"):
                body["reasoning"] = {"effort": "low"}; drop.append(lambda b: b.pop("reasoning", None))
                if want_json: body["max_tokens"] = 3000 if tuning.get("compact_answer") else 6000; drop.append(lambda b: b.pop("max_tokens", None))
            elif self.name.startswith("OpenAI") and re.match(r"(o\d|gpt-5)", model):
                body["reasoning_effort"] = "low"; drop.append(lambda b: b.pop("reasoning_effort", None))
        return _post_trim(f"{self.url(base)}/v1/chat/completions", {"Authorization": "Bearer " + key}, body, key, drop, model, self.name)

    @staticmethod
    def _cut_short(d):
        """True when the answer is empty because a thinking model used its whole limit on reasoning (finish_reason 'length', content null)."""
        try: c = d["choices"][0]; return c.get("finish_reason") == "length" and not (c.get("message") or {}).get("content")
        except (KeyError, IndexError, TypeError, AttributeError): return False

    def ask(self, model, key, img, mime, base=None, prompt=None, want_json=True):
        b64 = base64.b64encode(img).decode()
        body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt or build_prompt()}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}]}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        d = self._go(model, key, base, body, want_json)
        if self._cut_short(d):                                           # a thinking model spent its whole limit thinking: once more with room for the answer
            activity.log("net", "the model used all its tokens thinking and wrote no answer; asking once more with a bigger limit", "warn")
            body["max_tokens"] = 16000; body.pop("reasoning", None)
            d = _post_trim(f"{self.url(base)}/v1/chat/completions", {"Authorization": "Bearer " + key}, body, key, [lambda b: b.pop("max_tokens", None)], model, self.name)
            if self._cut_short(d):
                raise RuntimeError(f"{model} is a 'thinking' model: it spent all its tokens reasoning and never wrote the circuit. Pick another model in the Model box "
                                   "(Settings > AI & Import shows the live list) - not the free router, which may choose a thinking model.")
        try:
            return d["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("The service returned no answer: " + json.dumps(d)[:400])


    def chat(self, model, key, system, user, base=None, want_json=False):
        body = {"model": model, "temperature": 0.2, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if want_json and self.json_mode: body["response_format"] = {"type": "json_object"}
        d = self._go(model, key, base, body, False)
        try:
            return d["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("The service returned no answer: " + json.dumps(d)[:400])


class OllamaProvider(Provider):
    kind, local, show_base = "ollama", True, True

    def ask(self, model, key, img, mime, base=None, prompt=None, want_json=True):
        b64 = base64.b64encode(img).decode()
        url = f"{self.url(base)}/api/chat"
        last = ""
        for fmt in (("json", None) if want_json else (None,)):                  # constrained JSON first (circuits); if the model answers nothing, try free text. Code is never constrained
            body = {"model": model, "stream": False, "think": False,   # thinking models otherwise spend the whole budget "thinking"
                    "messages": [{"role": "user", "content": prompt or build_prompt(), "images": [b64]}],
                    "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3072 if want_json else 4096}}
            if fmt: body["format"] = fmt
            d = _post(url, {}, body, timeout=1800); usage.note(self.name, model, d)
            msg = d.get("message") or {}
            text = (msg.get("content") or "").strip()
            if "{" not in text and want_json:
                text = (text + "\n" + (msg.get("thinking") or "")).strip()   # last resort: JSON may sit in the reasoning text
            if "{" in text or (not want_json and text):
                return text
            last = json.dumps(d)[:200]
            if d.get("done_reason") == "length" or msg.get("thinking"):
                raise RuntimeError("This model is a 'thinking' model: it spent its whole answer limit reasoning and never wrote the circuit "
                                   "(slow on a CPU). Use a non-thinking model instead: press 'Download' with model  qwen3-vl:4b-instruct  "
                                   "(or qwen3-vl:2b-instruct), then Convert again.")
        raise RuntimeError("The model answered with no circuit (empty reply). Try a non-thinking model such as qwen3-vl:4b-instruct, "
                           "a tightly cropped image, or update Ollama (ollama.com). Raw reply: " + last)


    def chat(self, model, key, system, user, base=None, want_json=False):
        body = {"model": model, "stream": False, "think": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 4096}}
        if want_json: body["format"] = "json"
        d = _post(f"{self.url(base)}/api/chat", {}, body, timeout=1800); usage.note(self.name, model, d)
        msg = d.get("message") or {}
        text = (msg.get("content") or "").strip()
        if not text: raise RuntimeError("The model answered with an empty reply. Try another model (a non-thinking one works best) or a shorter request.")
        return text


PROVIDERS = {p.name: p for p in (
    GeminiProvider("Gemini (free tier)", ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"],
                   "https://generativelanguage.googleapis.com", "Free key at aistudio.google.com/apikey"),
    OpenAICompatibleProvider("OpenRouter (free models)", ["meta-llama/llama-4-maverick:free", "google/gemma-3-27b-it:free", "openrouter/free"],
                             "https://openrouter.ai/api", "Free key at openrouter.ai/keys. Pick a vision-capable model whose name ends in :free", "OPENROUTER_API_KEY"),
    OpenAICompatibleProvider("Groq (free tier)", ["meta-llama/llama-4-scout-17b-16e-instruct"], "https://api.groq.com/openai",
                             "Free key at console.groq.com/keys. Needs a vision-capable model", "GROQ_API_KEY"),
    OllamaProvider("Ollama (local, free)", ["qwen3-vl:4b-instruct", "qwen3-vl:2b-instruct", "qwen2.5vl:3b", "gemma3:4b", "qwen3-vl:4b", "qwen3-vl:8b"], "http://localhost:11434",
                   "Runs on your PC, no key, no limits. Install Ollama (ollama.com), then press \"Download model\" below."),
    AnthropicProvider("Claude (paid API)", ["claude-sonnet-5-5", "claude-opus-5-5"], "https://api.anthropic.com", "Key at console.anthropic.com (pay per use)"),
    OpenAICompatibleProvider("OpenAI (paid API)", ["gpt-4o", "gpt-4.1"], "https://api.openai.com", "Key at platform.openai.com (pay per use)", "OPENAI_API_KEY", json_mode=True),
    OpenAICompatibleProvider("Custom (OpenAI-compatible)", ["your-vision-model"], "https://example.com",
                             "Any server that speaks the OpenAI chat API: set the server URL, model and key", "CUSTOM_API_KEY", show_base=True),
)}


def ask_model(provider, model, key, img, mime, base=None, prompt=None, want_json=True):
    return PROVIDERS[provider].ask(model, (key or "").strip(), img, mime, base, prompt, want_json)


def chat_model(provider, model, key, system, user, base=None, want_json=False):
    """Ask a text question (no picture) to the chosen service; returns the model's answer."""
    return PROVIDERS[provider].chat(model, (key or "").strip(), system, user, base, want_json)


def explain_error(provider, msg):
    """Plain-language hint appended below a raw AI error."""
    low = msg.lower()
    gem = provider.startswith("Gemini")
    if "http 403" in low and ("denied access" in low or "permission" in low):
        return ("\n\nWhat this means: the provider refused your key's project or account. This is NOT caused by the model name or by this app, "
                "and no setting here can fix it.\nTry: (1) in aistudio.google.com/apikey create a NEW key with 'Create API key in new project', "
                "using a personal Google account; (2) check that Gemini's free tier is offered in your country; "
                "(3) meanwhile pick OpenRouter, Groq or Ollama from the list, which need no Google account." if gem else
                "\n\nWhat this means: the provider refused your key or account. Create a fresh key, or choose another provider.")
    if "http 401" in low or "api key not valid" in low or "invalid api key" in low or "incorrect api key" in low:
        return "\n\nWhat this means: the key is wrong or has extra spaces. Paste it again."
    if "http 404" in low:
        return "\n\nWhat this means: this model name does not exist for this provider. Pick another model or type the exact name."
    if "http 429" in low:
        return "\n\nWhat this means: free quota used up for now. Wait a minute, or choose another model or provider."
    if "could not reach" in low:
        return "\n\nWhat this means: no connection. Check the internet (or that Ollama is running for the local option)."
    return ""


def ollama_models(base):
    """Names of the models installed in a local Ollama server (raises if it is not running)."""
    req = urllib.request.Request(base.rstrip("/") + "/api/tags")
    with urllib.request.urlopen(req, timeout=4) as r:
        return [m["name"] for m in json.loads(r.read().decode()).get("models", [])]


def ollama_pull(base, model, progress):
    """Download a model into Ollama; progress(text) is called with status lines."""
    req = urllib.request.Request(base.rstrip("/") + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            for raw in r:
                try:
                    d = json.loads(raw.decode())
                except ValueError:
                    continue
                if d.get("error"):
                    raise RuntimeError(d["error"])
                if d.get("total") and d.get("completed") is not None:
                    progress(f"Downloading {model}: {d['completed'] * 100 // d['total']}%  ({d['completed'] // 1048576} of {d['total'] // 1048576} MB)")
                else:
                    progress(f"{model}: {d.get('status', '')}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama returned HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Ollama at {base}: {e.reason}. Install it from ollama.com and start it.")


def extract_json(text):
    """Pull the JSON object out of a model answer (it may be wrapped in text or code fences)."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("The model's answer contained no JSON.")
    return json.loads(text[a:b + 1])
