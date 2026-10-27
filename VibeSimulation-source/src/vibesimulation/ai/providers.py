"""AI back ends (Strategy pattern): each provider class knows how to send the picture to one kind of service.

To add a service, subclass ``Provider``, implement ``ask`` and add it to ``PROVIDERS``.
"""
import base64
import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from .prompt import build_prompt


def _post(url, headers, body, key=None, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        if key:
            detail = detail.replace(key, "***")
        raise RuntimeError(f"The AI service returned HTTP {e.code}:\n{detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach the AI service: {e.reason}")


class Provider(ABC):
    kind = ""
    env = None             # environment variable that may hold the API key
    show_base = False      # let the user edit the server URL
    local = False

    def __init__(self, name, models, base, help_text):
        self.name, self.models, self.base, self.help = name, models, base, help_text

    @abstractmethod
    def ask(self, model, key, img, mime, base=None):
        """Send the image + prompt; return the model's text answer."""

    def url(self, base):
        return (base or self.base).strip().rstrip("/")


class GeminiProvider(Provider):
    kind, env = "gemini", "GEMINI_API_KEY"

    def ask(self, model, key, img, mime, base=None):
        b64 = base64.b64encode(img).decode()
        d = _post(f"{self.url(base)}/v1beta/models/{model}:generateContent", {"x-goog-api-key": key},
                  {"contents": [{"parts": [{"text": build_prompt()}, {"inline_data": {"mime_type": mime, "data": b64}}]}],
                   "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}, key)
        try:
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError("Gemini returned no answer: " + json.dumps(d)[:300])


class AnthropicProvider(Provider):
    kind, env = "anthropic", "ANTHROPIC_API_KEY"

    def ask(self, model, key, img, mime, base=None):
        b64 = base64.b64encode(img).decode()
        d = _post(f"{self.url(base)}/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"},
                  {"model": model, "max_tokens": 4000, "temperature": 0,
                   "messages": [{"role": "user", "content": [
                       {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                       {"type": "text", "text": build_prompt()}]}]}, key)
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

    def ask(self, model, key, img, mime, base=None):
        b64 = base64.b64encode(img).decode()
        body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
            {"type": "text", "text": build_prompt()}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}]}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        d = _post(f"{self.url(base)}/v1/chat/completions", {"Authorization": "Bearer " + key}, body, key)
        try:
            return d["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("The service returned no answer: " + json.dumps(d)[:400])


class OllamaProvider(Provider):
    kind, local, show_base = "ollama", True, True

    def ask(self, model, key, img, mime, base=None):
        b64 = base64.b64encode(img).decode()
        url = f"{self.url(base)}/api/chat"
        last = ""
        for fmt in ("json", None):                  # constrained JSON first; if the model answers nothing, try free text
            body = {"model": model, "stream": False, "think": False,   # thinking models otherwise spend the whole budget "thinking"
                    "messages": [{"role": "user", "content": build_prompt(), "images": [b64]}],
                    "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3072}}
            if fmt: body["format"] = fmt
            d = _post(url, {}, body, timeout=1800)
            msg = d.get("message") or {}
            text = (msg.get("content") or "").strip()
            if "{" not in text:
                text = (text + "\n" + (msg.get("thinking") or "")).strip()   # last resort: JSON may sit in the reasoning text
            if "{" in text:
                return text
            last = json.dumps(d)[:200]
            if d.get("done_reason") == "length" or msg.get("thinking"):
                raise RuntimeError("This model is a 'thinking' model: it spent its whole answer limit reasoning and never wrote the circuit "
                                   "(slow on a CPU). Use a non-thinking model instead: press 'Download' with model  qwen3-vl:4b-instruct  "
                                   "(or qwen3-vl:2b-instruct), then Convert again.")
        raise RuntimeError("The model answered with no circuit (empty reply). Try a non-thinking model such as qwen3-vl:4b-instruct, "
                           "a tightly cropped image, or update Ollama (ollama.com). Raw reply: " + last)


PROVIDERS = {p.name: p for p in (
    GeminiProvider("Gemini (free tier)", ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"],
                   "https://generativelanguage.googleapis.com", "Free key at aistudio.google.com/apikey"),
    OpenAICompatibleProvider("OpenRouter (free models)", ["openrouter/free", "meta-llama/llama-4-maverick:free", "google/gemma-3-27b-it:free"],
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


def ask_model(provider, model, key, img, mime, base=None):
    return PROVIDERS[provider].ask(model, (key or "").strip(), img, mime, base)


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
