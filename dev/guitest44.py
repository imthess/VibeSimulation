"""AI import: the API key can be remembered in the OS keychain (a fake `keyring` module is used here)."""
import sys, os, time, types, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
store = {}
fake = types.ModuleType("keyring")
fake.get_password = lambda s, u: store.get((s, u)); fake.set_password = lambda s, u, p: store.__setitem__((s, u), p)
def _del(s, u): store.pop((s, u))
fake.delete_password = _del
sys.modules["keyring"] = fake
import tkinter as tk
from pathlib import Path
import vibesimulation.product.recovery as RC
RC.PATH = Path(tempfile.mkdtemp()) / "rec.json"
from vibesimulation.product.recovery import Recovery
Recovery.__init__.__defaults__ = (RC.PATH,)
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.workspaces.ai_import.core import PROVIDERS
import vibesimulation.workspaces.ai_import.core.secrets as secrets
from vibesimulation.ui.window.main_window import MainWindow
import vibesimulation.workspaces.ai_import.ui.import_view as IV
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=6):
    for _ in range(n): root.update(); time.sleep(0.02)
w.ctx.toaster.show = lambda *a, **k: None; w.ctx.say = lambda *a, **k: None
name = next(n for n, p in PROVIDERS.items() if p.env)
for v in [p.env for p in PROVIDERS.values() if p.env]: os.environ.pop(v, None)
w.show("import"); pump(); v = w.pages["import"].view
IV.ask_model = lambda *a, **k: '{"kind":"digital","inputs":["A"],"outputs":["Y"],"gates":[{"id":"g1","type":"NOT","in":["A"],"out":"Y"}]}'
chk("keyring module detected", secrets.available())
v.prov.set(name); v.provider_changed(); pump()
chk("the 'remember' box is shown and on by default", v.rem_chk.winfo_ismapped() and v.remember.get() and v.key.get() == "")
v.image_bytes = b"x"; v.image_mime = "image/png"; v.key.set("secret-123"); v.remember.set(True); v.convert(); pump(20)
chk("convert with 'remember' stores the key in the keychain", store.get((secrets.SERVICE, name)) == "secret-123")
v.key.set(""); v.provider_changed(); pump()
chk("the key comes back from the keychain, box ticked", v.key.get() == "secret-123" and v.remember.get())
v.remember.set(False); v.convert(); pump(20)
chk("convert with the box off deletes the stored key", (secrets.SERVICE, name) not in store)
chk("the key is never written to the settings", "secret-123" not in repr(w.ctx.cfg))
sys.modules["keyring"] = None
import tempfile, pathlib; secrets.FILE = pathlib.Path(tempfile.mkdtemp()) / "keys"
chk("without keyring: the key goes to a private file, no crash", secrets.set_key(name, "x") == "file" and secrets.get_key(name) == "x" and not secrets.available())
# ---- auto-detection of the provider from a pasted key
sys.modules["keyring"] = fake
from vibesimulation.workspaces.ai_import.core.key_detect import detect_provider
local = next(n for n, p in PROVIDERS.items() if p.local)
v.prov.set(local); v.provider_changed(); pump()
v.key.set("AIzaSyA1234567890abcdefghijklmnopqrstuv"); pump()
chk("pasting a Gemini key switches the provider to Gemini", v.prov.get() == "Gemini (free tier)" and "Detected" in v.detected.cget("text"))
chk("...and the model list follows the provider", v.model.get() in PROVIDERS["Gemini (free tier)"].models)
v.key.set("sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123"); pump()
chk("pasting a Claude key switches to Claude", v.prov.get() == "Claude (paid API)")
v.key.set("  gsk_abcdefghijklmnopqrstuvwxyz0123456789  "); pump()
chk("spaces around the key are removed and Groq is found", v.prov.get() == "Groq (free tier)" and v.key.get() == "gsk_abcdefghijklmnopqrstuvwxyz0123456789")
v.key.set("hello-not-a-key-at-all"); pump()
chk("an unknown key leaves the provider alone and says so", v.prov.get() == "Groq (free tier)" and "not recognised" in v.detected.cget("text"))
root.clipboard_clear(); root.clipboard_append("sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789"); v.paste_key(); pump()
chk("the paste button reads the clipboard and detects OpenRouter", v.prov.get() == "OpenRouter (free models)")
# ---- the preview and the full-size viewer
from PIL import Image
import io as _io
buf = _io.BytesIO(); Image.new("RGB", (300, 120), "white").save(buf, "PNG")
v.image_bytes = buf.getvalue(); v.show_preview(v.image_bytes); pump(20)
pw, ph = v.prev_box.winfo_width(), v.prev_box.winfo_height()
chk("a small picture is enlarged to fill the preview", v.preview is not None and v.preview.width() > 300 and v.preview.width() >= pw * 0.6)
from vibesimulation.workspaces.ai_import.ui.viewer import PictureViewer
vw = PictureViewer(w.ctx, v.image_bytes); pump(10); z0 = vw.zoom; vw.set_zoom(z0 * 2); pump(3)
chk("double-click viewer opens and zooms", vw.winfo_exists() and abs(vw.zoom - z0 * 2) < 1e-6); vw.destroy()
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
