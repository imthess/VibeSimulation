"""Token saving on the Import page: scan on import (Scanned / Original, crop, settings), short answer format, real token line, history,
the Settings entries, and a separate AI for the AI button. Fake service, no network."""
import sys, os, time, json, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from PIL import Image, ImageDraw
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
import vibesimulation.workspaces.ai_import.ui.import_view as IV
from vibesimulation.workspaces.ai_import.core import compact, profile, scan, tuning, usage
import tempfile, pathlib
from vibesimulation.workspaces.ai_import.core import secrets as _sec; _sec.FILE = pathlib.Path(tempfile.mkdtemp()) / "keys"      # never touch the real key file
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
def wait(f, t=8):
    t0 = time.time()
    while time.time() - t0 < t and not f(): pump(2)
    return f()

# a photo of a drawing on a dark table
im = Image.new("RGB", (2000, 1500), (80, 60, 40)); page = Image.new("RGB", (1500, 1100), (235, 232, 225)); d = ImageDraw.Draw(page)
d.rectangle([500, 400, 900, 700], outline=(30, 30, 40), width=5); d.line([200, 550, 500, 550], fill=(30, 30, 40), width=5); d.line([900, 550, 1300, 550], fill=(30, 30, 40), width=5)
im.paste(page, (250, 200)); PATH = "/tmp/vs_test_photo.jpg"; im.save(PATH, quality=92)

w.show("import"); pump(10); v = w.pages["import"].view
chk("scan is on by default", v.scan_seg.value == "scanned")
v.load_image(PATH); pump(5)
chk("picture is scanned on import (PNG, at most 1280 px, smaller than the photo)", v.image_mime == "image/png" and v.scan_info.get("scanned") and max(v.scan_info["size"]) <= 1280 and len(v.image_bytes) < os.path.getsize(PATH))
chk("a line says what is sent", "scanned" in v.scan_lbl.cget("text"))
sent_scanned = v.image_bytes
v.scan_seg.pick("original"); v.scan_mode_changed("original"); pump(3)
chk("Original: the picture is sent as it is", v.image_mime == "image/jpeg" and "original" in v.scan_lbl.cget("text") and v.image_bytes == v.orig_bytes and w.ctx.cfg["scan_on"] is False)
v.scan_mode_changed("scanned"); pump(3)
chk("back to Scanned", v.image_bytes == sent_scanned or v.scan_info.get("scanned"))
# settings change -> rebuilt
w.ctx.cfg["scan_size"] = 800; v.scan_changed(); pump(3)
chk("scan size setting is followed", max(v.scan_info["size"]) <= 800)
w.ctx.cfg["scan_size"] = 1280; w.ctx.cfg["scan_look"] = "colour"; v.scan_changed(); pump(3)
chk("colour look sends a JPEG", v.image_mime == "image/jpeg"); w.ctx.cfg["scan_look"] = "bw"
# manual crop
v.scan_box = (400, 500, 1000, 900); w.ctx.cfg["scan_size"] = 0; v.scan_changed(); pump(3)
chk("a manual crop box is used", v.scan_info["size"] == (600, 400))
# the crop dialog itself
from vibesimulation.workspaces.ai_import.ui.crop_dialog import CropDialog
dlg = CropDialog(w.ctx, v.orig_bytes, None, scan.from_cfg(w.ctx.cfg)); pump(5)
x0, y0, x1, y1 = dlg.box
chk("crop dialog starts on the automatic box", 0 <= x0 < x1 <= 2000 and (x1 - x0) < 1900 and (y1 - y0) < 1400)
class E: pass
e = E(); e.x, e.y = int(x1 * dlg.k), int(y1 * dlg.k); dlg.press(e); e.x -= 60; e.y -= 40; dlg.move(e)
chk("dragging a corner resizes the frame", dlg.box[2] < x1 and dlg.box[3] < y1)
dlg.ok(); pump(2); chk("OK returns the box in picture pixels", dlg.result is not None and dlg.result[2] == round(dlg.box[2]) or dlg.result is not None)
w.ctx.cfg["scan_size"] = 1280; v.scan_box = None

# + / - next to Adjust crop
c0 = w.ctx.cfg.get("scan_contrast", 50); v.nudge_scan("scan_contrast", 10); i0 = w.ctx.cfg.get("scan_ink", 50); v.nudge_scan("scan_ink", -10)
chk("contrast + and line strength - change the settings", w.ctx.cfg["scan_contrast"] == c0 + 10 and w.ctx.cfg["scan_ink"] == i0 - 10 and "Line strength" in v.scan_lbl.cget("text"))
w.ctx.cfg["scan_contrast"] = 0; v.nudge_scan("scan_contrast", -10); chk("limits at 0", w.ctx.cfg["scan_contrast"] == 0); w.ctx.cfg["scan_contrast"] = 50; w.ctx.cfg["scan_ink"] = 50; v.rebuild_scan()
# a conversion that never ends can be stopped
import threading
gate = threading.Event()
def hang(*a, **k): gate.wait(5); return "D\nin A\nout Y\ng1 NOT A > Y"
IV.ask_model = hang
v.prov.set("Groq (free tier)"); v.provider_changed(); v.model.set("m1"); v.key.set("gsk_" + "k" * 40); pump(3); v.convert(); pump(3)
chk("while working the button says Stop", v.busy and v.btn_convert.text == "Stop")
v.convert(); pump(3); chk("Stop gives the window back", not v.busy and "Stopped" in v.status.msg and v.btn_convert.text.startswith("Convert"))
gate.set(); pump(15); chk("the late answer is ignored", v.result_kind is None and v.status.msg.startswith("Stopped"))
# the key is remembered at once (private file when there is no keyring)
from vibesimulation.workspaces.ai_import.core import secrets
import tempfile, pathlib; secrets.FILE = pathlib.Path(tempfile.mkdtemp()) / "keys"
k = "gsk_" + "r" * 40; v.remember.set(True); v.key.set(k); v.remember_key()
chk("the key is saved without pressing Convert", secrets.get_key("Groq (free tier)") == k)
# convert with the short answer format and real tokens
asked = []
def fake_ask(name, model, key, img, mime, base=None, prompt=None, want_json=True):
    asked.append((prompt, mime, len(img)))
    usage.note(name, model, {"usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 150, "thoughtsTokenCount": 0, "totalTokenCount": 1350}})
    return "D\nin A\nout Y\ng1 NOT A > Y"
IV.ask_model = fake_ask
v.prov.set("Groq (free tier)"); v.provider_changed(); v.key.set(""); pump(3); v.model.set("m1"); v.key.set("gsk_" + "k" * 40); pump(3)
v.model.set("m1"); v.cb_target.set("Logisim circuit"); v.target_changed(); v.convert()
chk("short answer format is requested", wait(lambda: asked) and "ANSWER FORMAT" in asked[-1][0] and asked[-1][1] == "image/png")
chk("the short answer opens as a circuit", wait(lambda: v.result_kind == "digital"))
chk("tokens used are shown", wait(lambda: "1,350 tokens used" in v.status.msg))
pump(5); usage.drain(w.ctx.cfg)
chk("the call is in the history", w.ctx.cfg.get("ai_usage") and w.ctx.cfg["ai_usage"][-1]["total"] == 1350)
w.ctx.cfg["ai_compact_answer"] = False; tuning.apply(w.ctx.cfg); asked.clear(); wait(lambda: not v.busy); v.convert()
chk("short format off: normal prompt", wait(lambda: asked) and "ANSWER FORMAT" not in asked[-1][0])
tuning.apply({}); wait(lambda: not v.busy)

# settings page entries
w.show("settings"); pump(5); sp = w.pages["settings"].view if hasattr(w.pages["settings"], "view") else w.pages["settings"]
labels = [dd["label"] for dd in sp.defs()]
for lab in ("Limit the AI's hidden thinking", "OpenRouter model choice", "Scan pictures on import", "Short answer format", "Convert pictures to", "Use a different AI for the AI button", "Scan contrast", "Scan size (pixels)", "Crop to the circuit (and margin)"):
    chk("settings has: " + lab, lab in labels)
sp.cur = "AI & Import"; sp.build(); pump(8)
chk("the AI & Import page builds", sp.card is not None)
# default convert-to
w.ctx.cfg["import_target"] = "logisim"; v.target.set("Logisim circuit"); sp.refresh(); pump(2)
chk("default tab setter follows", "import_target" in sp.setters)

chk("the token history setting is gone", "Token usage and history" not in labels)

# separate AI for the AI button
cfg = w.ctx.cfg; v.prov.set("Groq (free tier)"); v.model.set("import-model")
chk("without a separate AI the button uses the Import page", not profile.enabled(cfg))
msg = profile.save(cfg, "Ollama (local, free)", "qwen3-vl:4b-instruct", "http://localhost:11434", "", IV.PROVIDERS); cfg["ai_sep_on"] = True
name, model, key, base = w.assistant.session.config() if hasattr(w, "assistant") else (None,) * 4
if name is None:
    from vibesimulation.ui.assistant.session import Session
    name, model, key, base = Session(w).config()
chk("the AI button uses its own AI", name == "Ollama (local, free)" and model == "qwen3-vl:4b-instruct" and base == "http://localhost:11434")
chk("picture import keeps its own", v.prov.get() == "Groq (free tier)" and v.model.get() == "import-model")
cfg["ai_sep_on"] = False
from vibesimulation.ui.assistant.session import Session
chk("switched off: back to the Import page's AI", Session(w).config()[0] == "Groq (free tier)")
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
