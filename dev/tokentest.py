"""Token-saving core without a network: scan pipeline (crop, flatten, size), short answer format, usage normalising, reasoning limit in requests."""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from PIL import Image, ImageDraw
from vibesimulation.workspaces.ai_import.core import scan, compact, usage, tuning, providers
ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)

# a photo-like page: shadow gradient, table around, a small drawing in the middle
im = Image.new("RGB", (2400, 1800), (90, 70, 50))
page = Image.new("RGB", (1800, 1400))
d = ImageDraw.Draw(page)
for x in range(1800): d.line([(x, 0), (x, 1400)], fill=(235 - x // 30, 232 - x // 30, 225 - x // 30))     # light falls off to the right
d.rectangle([700, 500, 1100, 800], outline=(30, 30, 40), width=5); d.line([300, 650, 700, 650], fill=(30, 30, 40), width=5); d.line([1100, 650, 1500, 650], fill=(30, 30, 40), width=5)
im.paste(page, (300, 200))
box = scan.auto_box(im)
chk("auto crop finds the drawing (inside the page, around the strokes)", 250 < box[0] <= 1000 and box[2] >= 1700 and box[1] > 500 and box[3] < 1250 and box[2] - box[0] < 1700)
o = scan.ScanOptions()
out = scan.scan(im, o)
chk("result is at most 1280 px", max(out.size) <= 1280 and out.size[0] > 300)
g = out.convert("L"); hist = g.histogram()
chk("white paper, dark lines (black & white)", sum(hist[:40]) > 0 and sum(hist[215:]) / g.width / g.height > 0.8 and sum(hist[40:215]) / g.width / g.height < 0.15)
corner = [g.getpixel((5, 5)), g.getpixel((g.width - 6, 5))]
chk("shadow is flat: both corners white", min(corner) > 235)
b, m = scan.encode(out, "bw")
chk("PNG for black & white, smaller than the photo as JPEG", m == "image/png" and len(b) < 60000)
raw = io.BytesIO(); im.save(raw, "JPEG", quality=90)
b2, m2, info = scan.prepare(raw.getvalue(), "image/jpeg", o)
chk("prepare reports the scan", info["scanned"] and info["from"] == (2400, 1800) and m2 == "image/png")
b3, m3, info3 = scan.prepare(b"not an image", "image/png", o)
chk("broken picture falls back to the original", not info3["scanned"] and b3 == b"not an image")
o2 = scan.ScanOptions(crop=False, look="colour", size=0, flatten=False)
chk("no crop / colour / no resize keeps the size", scan.scan(im, o2).size == im.size and scan.encode(scan.scan(im, o2), "colour")[1] == "image/jpeg")
chk("grey look works", scan.scan(im, scan.ScanOptions(look="gray")).size[0] > 0)
chk("manual box is used", scan.scan(im, scan.ScanOptions(size=0), (100, 100, 600, 500)).size == (500, 400))
chk("bad manual box is repaired", scan.clean_box((-50, 900, 99999, 10), (2400, 1800))[2] <= 2400)
c = scan.from_cfg({"scan_size": "abc", "scan_contrast": 900, "scan_look": "x", "scan_crop": False})
chk("settings are clamped", c.size == 1280 and c.contrast == 100 and c.look == "bw" and c.crop is False)
blank = Image.new("RGB", (800, 600), (240, 240, 240))
chk("empty page: whole picture kept", scan.auto_box(blank) == (0, 0, 800, 600))
hard = scan.scan(im, scan.ScanOptions(contrast=100, size=0)).convert("L").histogram()
chk("full contrast is nearly two-tone", sum(hard[30:225]) < 0.02 * sum(hard))

# short answer format
j = compact.to_json_text("D\nin A B\nout Y\ng1 NAND A B > n1\ng2 NOT n1 > Y")
import json
dj = json.loads(j)
chk("short logic answer -> JSON", dj["kind"] == "digital" and dj["inputs"] == ["A", "B"] and dj["gates"][1] == {"id": "g2", "type": "NOT", "in": ["n1"], "out": "Y"})
da = json.loads(compact.to_json_text("A Divider\nV1 VoltageSource 5 n1 0 ac=2 freq=1k\nR1 Resistor 1k n1 n2\nD1 Diode n2 0\nQ1 NPN n1 n2 0"))
chk("short analog answer -> JSON", da["title"] == "Divider" and da["components"][0]["ac"] == 2 and da["components"][2]["nodes"] == ["n2", "0"] and da["components"][3]["nodes"] == ["n1", "n2", "0"])
chk("JSON and code pass through", compact.to_json_text('{"kind":"digital"}') == '{"kind":"digital"}' and compact.to_json_text("module m;") == "module m;")
chk("broken short answer returned unchanged", compact.to_json_text("D\ng1 AND") == "D\ng1 AND")
chk("fenced short answer", json.loads(compact.to_json_text("```\nD\nin A\nout Y\ng1 NOT A > Y\n```"))["gates"][0]["type"] == "NOT")

# usage
chk("gemini usage", usage.normalize({"usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200, "thoughtsTokenCount": 800, "totalTokenCount": 2000}}) == dict(prompt=1000, output=1000, reasoning=800, total=2000))
chk("openai usage", usage.normalize({"usage": {"prompt_tokens": 500, "completion_tokens": 3000, "total_tokens": 3500, "completion_tokens_details": {"reasoning_tokens": 2500}}})["reasoning"] == 2500)
chk("anthropic usage", usage.normalize({"usage": {"input_tokens": 9, "output_tokens": 4}})["total"] == 13)
chk("ollama usage", usage.normalize({"prompt_eval_count": 7, "eval_count": 3})["total"] == 10)
chk("nothing reported -> zeros", usage.normalize({})["total"] == 0 and usage.normalize(None)["total"] == 0)
cfg = {}
for i in range(usage.MAX_ENTRIES + 5): usage.add(cfg, {"total": 1, "prompt": 1, "output": 0, "reasoning": 0})
chk("history is capped", len(cfg["ai_usage"]) == usage.MAX_ENTRIES and usage.totals(cfg["ai_usage"])["total"] == usage.MAX_ENTRIES)
got = []; usage.sink = got.append; usage.context("assistant")
e = usage.note("X", "m", {"usage": {"input_tokens": 1, "output_tokens": 2}})
chk("note stores, labels and remembers", got and got[0]["what"] == "assistant" and usage.last() is e and "3 tokens" in usage.summary(e))
usage.sink = None

# request bodies: reasoning limit on/off and 400 retry
sent = []
def fake_post(url, headers, body, key=None, timeout=180):
    import copy; sent.append(copy.deepcopy(body))
    if fake_post.refuse and ("reasoning" in body or "reasoning_effort" in body or "thinkingConfig" in body.get("generationConfig", {})): raise RuntimeError("The AI service returned HTTP 400:\nbad")
    return {"choices": [{"message": {"content": "{}"}}], "candidates": [{"content": {"parts": [{"text": "{}"}]}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
fake_post.refuse = False
providers._post = fake_post
tuning._state["limit_reasoning"] = True
P = providers.PROVIDERS
P["OpenRouter (free models)"].ask("x/y:free", "k", b"i", "image/png")
chk("OpenRouter: reasoning low + cap", sent[-1].get("reasoning") == {"effort": "low"} and sent[-1].get("max_tokens"))
P["Gemini (free tier)"].ask("gemini-2.5-flash", "k", b"i", "image/png")
chk("Gemini 2.5: thinking budget", "thinkingConfig" in sent[-1]["generationConfig"])
P["Gemini (free tier)"].ask("gemini-2.0-flash", "k", b"i", "image/png")
chk("Gemini 2.0: untouched", "thinkingConfig" not in sent[-1]["generationConfig"])
P["OpenAI (paid API)"].ask("gpt-4o", "k", b"i", "image/png")
chk("OpenAI gpt-4o: untouched", "reasoning_effort" not in sent[-1])
P["OpenAI (paid API)"].ask("o3", "k", b"i", "image/png")
chk("OpenAI o3: effort low", sent[-1].get("reasoning_effort") == "low")
fake_post.refuse = True; n = len(sent)
txt = P["OpenRouter (free models)"].ask("x/y:free", "k", b"i", "image/png")
chk("service refuses the option: retried without it", len(sent) == n + 2 and "reasoning" not in sent[-1] and txt == "{}")
tuning._state["limit_reasoning"] = False; fake_post.refuse = False
P["OpenRouter (free models)"].ask("x/y:free", "k", b"i", "image/png")
chk("switch off: nothing added", "reasoning" not in sent[-1])
# keys: fallback file when there is no keyring, and a hard time limit
import tempfile, pathlib, builtins, time as _t
from vibesimulation.workspaces.ai_import.core import secrets
_real = builtins.__import__
def no_keyring(name, *a, **k):
    if name == "keyring": raise ImportError("no keyring")
    return _real(name, *a, **k)
secrets.FILE = pathlib.Path(tempfile.mkdtemp()) / "keys"; builtins.__import__ = no_keyring
chk("no keyring: key goes to a private file", secrets.set_key("P", "sk-abc") == "file" and secrets.get_key("P") == "sk-abc" and oct(os.stat(secrets.FILE).st_mode & 0o777) == "0o600")
chk("the file does not hold the key in plain text", "sk-abc" not in secrets.FILE.read_text())
secrets.delete_key("P"); chk("forgotten", secrets.get_key("P") == "")
builtins.__import__ = _real
class Slow:
    def read1(self, n): _t.sleep(0.2); return b"x"      # a keep-alive byte every 0.2 s, like OpenRouter while a model is busy
try: providers._read_within(Slow(), 0.5); chk("slow trickle is cut off", False)
except RuntimeError as e: chk("slow trickle is cut off", "did not answer" in str(e))
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
