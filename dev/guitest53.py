"""Import & AI: paste a key -> the provider is detected, the key is checked and the best live model is chosen (fake service, no network)."""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
import vibesimulation.workspaces.ai_import.ui.import_view as IV
from vibesimulation.workspaces.ai_import.core import autodetect as A
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
def wait(f, t=8):
    t0 = time.time()
    while time.time() - t0 < t and not f(): pump(2)
    return f()

LIVE = {"Gemini (free tier)": ["gemini-2.5-flash", "gemini-2.5-pro"], "Groq (free tier)": ["meta-llama/llama-4-scout-17b-16e-instruct"]}
seen = []
def fake_discover(key, selected=None, bases=None, providers=None, get=None):
    seen.append((key, selected))
    if key.startswith("BAD"): return A.Found("Gemini (free tier)", message="Gemini (free tier) did not accept this key (HTTP 403). Check that it is copied completely.", accepted=False)
    name = A.detect_provider(key) or selected
    return A.Found(name, LIVE.get(name, []), f"Detected: {name}  ·  model chosen: {(LIVE.get(name) or ['-'])[0]}", True)
IV.discover = fake_discover

w.show("import"); pump(10); v = w.pages["import"].view
v.prov.set("OpenRouter (free models)"); v.provider_changed(); pump(5); v.key.set(""); pump(3)
gem = "AQ.Ab8" + "x" * 40                                           # a newer Google key
v.key.set(gem); pump(2)
chk("provider switches at once from the key", v.prov.get() == "Gemini (free tier)")
chk("the best live model is chosen without touching the model box", wait(lambda: v.model.get() == "gemini-2.5-flash"))
chk("the model list shows the live models", list(v.cb_model.cget("values"))[:2] == ["gemini-2.5-flash", "gemini-2.5-pro"])
chk("a message says what was detected", wait(lambda: "model chosen" in v.detected.cget("text")))
chk("the key was checked once", len(seen) == 1 and seen[0][0] == gem)

# a model the user picked stays
v.cb_model.set("gemini-2.5-pro"); v.cb_model.event_generate("<<ComboboxSelected>>"); pump(3)
v.key.set("AQ.Ab8" + "y" * 40); wait(lambda: len(seen) == 2)
chk("a model chosen by hand is kept when the key changes", wait(lambda: True) and v.model.get() == "gemini-2.5-pro" and v.model_user)
chk("the choice is remembered in the settings", w.ctx.cfg.get("model_manual", {}).get("Gemini (free tier)") is True)
v.prov.set("Groq (free tier)"); v.provider_changed(); pump(3)
chk("another provider starts automatic again", v.model_user is False)

# an unknown prefix: the provider chosen in the window is used
v.key.set("some-unknown-key-" + "z" * 20); wait(lambda: len(seen) == 3)
chk("unknown key shape: the chosen provider is asked", seen[-1][1] == "Groq (free tier)" and wait(lambda: v.model.get() == "meta-llama/llama-4-scout-17b-16e-instruct"))

# a rejected key is shown in red text
v.prov.set("Gemini (free tier)"); v.provider_changed(); pump(3); v.key.set("AIza" + "q" * 35); pump(2)
IV.discover = lambda *a, **k: fake_discover("BAD" + a[0], *a[1:], **k); v.key.set("AIza" + "r" * 35)
chk("a rejected key says so", wait(lambda: "did not accept" in v.detected.cget("text")))
IV.discover = fake_discover

# a stale key result is ignored
v.apply_auto(-5, "AIza" + "r" * 35, A.Found("Groq (free tier)", ["x"], "late", True)); pump(2)
chk("an answer for an old key changes nothing", v.prov.get() == "Gemini (free tier)" and "late" not in v.detected.cget("text"))

# convert: the chosen model no longer exists -> retried with a live one, the box is updated
tries = []
def fake_ask(name, model, key, img, mime, base=None, prompt=None, want_json=True):
    tries.append(model)
    if model == "retired-model": raise RuntimeError("The AI service returned HTTP 404:\nmodel not found")
    return json.dumps({"kind": "digital", "inputs": ["A"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NOT", "in": ["A"], "out": "Y"}]})
IV.ask_model = fake_ask
A.best_model = lambda *a, **k: "gemini-2.5-flash"
v.image_bytes, v.image_mime = b"\x89PNG", "image/png"
v.prov.set("Gemini (free tier)"); v.provider_changed(); v.key.set("AIza" + "s" * 35); pump(3); v.model.set("retired-model"); pump(2)
v.convert()
chk("convert retries once with the best live model", wait(lambda: tries[-1:] == ["gemini-2.5-flash"], 10) and tries[:2] == ["retired-model", "gemini-2.5-flash"])
chk("the model box now shows the model that worked", wait(lambda: v.model.get() == "gemini-2.5-flash"))
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
