"""Activity page (</> icon above Settings): live log, findings, tokens, details, downloads (.md / .pdf), tools, and the logging from a conversion."""
import sys, os, time, json, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
from vibesimulation.common import activity
import vibesimulation.workspaces.ai_import.ui.import_view as IV
from vibesimulation.workspaces.ai_import.core import providers, secrets as _sec, usage
from vibesimulation.workspaces.activity.core import findings
from vibesimulation.workspaces.activity.tools import diagnose
_sec.FILE = pathlib.Path(tempfile.mkdtemp()) / "keys"
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
def wait(f, t=8):
    t0 = time.time()
    while time.time() - t0 < t and not f(): pump(2)
    return f()

# the icon: above Settings
from vibesimulation.ui.navigation import rail
keys = [k[0] for k in rail.BOTTOM]; bx = w.rail.boxes()
chk("rail has </> above the settings icon", keys == ["activity", "settings"] and bx["activity"][1] < bx["settings"][1] and rail.BOTTOM[0][1] == "</>")
w.show("activity"); pump(8); pg = w.pages["activity"]
chk("page opens", w.current == "activity" and pg.winfo_ismapped())
# live log
activity.log("test", "hello from a test", "info"); activity.log("test", "something odd", "warn"); activity.log("test", "it failed with sk-abcdefghijklmnop1234", "error")
chk("new lines appear by themselves", wait(lambda: "hello from a test" in pg.txt.get("1.0", "end")))
chk("keys are masked", "sk-abcdefghijklmnop1234" not in pg.txt.get("1.0", "end") and "***" in pg.txt.get("1.0", "end"))
pg.problems.set(True); pg.redraw(); txt = pg.txt.get("1.0", "end")
chk("problems only hides plain info", "something odd" in txt and "hello from a test" not in txt); pg.problems.set(False); pg.redraw()
# live status while a job runs
jid = activity.LOG.begin("waiting for a model", source="test"); pump(25)
chk("status chip shows work in progress", "Working" in pg.chip.cget("text") and "waiting for a model" in pg.chip.cget("text"))
activity.LOG.end(jid, True, "done"); pump(25); chk("status chip goes back to idle", "Idle" in pg.chip.cget("text"))
# views
for v, needle in (("tokens", "Token usage"), ("findings", "What the log says"), ("details", "System")):
    pg.set_view(v); pump(3); chk(f"{v} view", needle in pg.txt.get("1.0", "end"))
w.ctx.cfg["ai_usage"] = [dict(t=time.time(), prompt=1000, output=500, reasoning=400, total=1500, provider="X", model="m", what="picture")]
pg.set_view("tokens"); pump(3); chk("token table lists calls and totals", "1,500" in pg.txt.get("1.0", "end") and "1 calls" in pg.txt.get("1.0", "end"))
# findings rules
E = lambda text, level="info", source="net", **d: type("E", (), dict(text=text, level=level, source=source, data=d))()
f = lambda es, cfg=None, req=None: findings.analyze(es, cfg or {}, req)
chk("timeout is explained", f([E("The AI service did not answer within 3 minutes")])[0][0] == "error")
chk("HTTP 429 is explained", any("429" in t for _, t, _ in f([E("HTTP 429: quota")])))
chk("big token use is flagged", any("tokens" in t for _, t, _ in f([E("x", source="tokens", total=30000, prompt=1, output=29999, reasoning=29000)])))
chk("large picture is flagged", any("large" in t for _, t, _ in f([], {}, {"bytes": 900000})))
chk("nothing wrong -> ok", f([])[0][0] == "ok")
# download
rep = pg.report_text()
chk("report has the sections", all(h in rep for h in ("## Findings", "## System", "## AI settings", "## Token usage", "## Log", "hello from a test")))
d = tempfile.mkdtemp(); from vibesimulation.workspaces.activity.export import save_markdown, save_pdf
save_markdown(rep, d + "/r.md"); save_pdf(rep, d + "/r.pdf"); pdf = open(d + "/r.pdf", "rb").read()
chk("markdown file written", open(d + "/r.md", encoding="utf-8").read() == rep)
chk("pdf file written and valid", pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF") and b"/Count" in pdf)
# a conversion writes its steps
tries = []
def fake_ask(name, model, key, img, mime, base=None, prompt=None, want_json=True):
    activity.log("net", "POST fake  model m1  1 KB sent"); time.sleep(0.2)
    usage.note(name, model, {"usage": {"prompt_tokens": 900, "completion_tokens": 100}})
    return "D\nin A\nout Y\ng1 NOT A > Y"
IV.ask_model = fake_ask
w.show("import"); pump(5); v = w.pages["import"].view
v.prov.set("Groq (free tier)"); v.provider_changed(); v.model.set("m1"); v.key.set("gsk_" + "t" * 40); pump(3); v.image_bytes, v.image_mime = b"\x89PNG....", "image/png"
n0 = len(activity.LOG.all()); v.convert()
chk("Convert is logged and shown as running", any("Convert pressed" in e.text for e in activity.LOG.all()[n0:]) and activity.LOG.running())
wait(lambda: v.result_kind == "digital"); pump(5)
txt = " ".join(e.text for e in activity.LOG.all()[n0:])
chk("the steps are in the log", "Convert pressed" in txt and "answer received" in txt and "tokens" in txt.lower() and "digital circuit" in txt)
chk("the key is never logged", "gsk_" + "t" * 40 not in txt and "gsk_" + "t" * 40 not in rep)
# a hanging conversion: the watchdog gives up
import threading; gate = threading.Event(); IV.ask_model = lambda *a, **k: (gate.wait(6), "x")[1]
providers.TIMEOUT = 1; v.convert(); pump(3); v.t_start = time.time() - 100; wait(lambda: not v.busy, 4)
chk("watchdog stops a conversion that never ends", not v.busy and "watchdog" in " ".join(e.text for e in activity.LOG.all()[-6:]) and "No answer" in v.status.msg)
gate.set(); providers.TIMEOUT = 180
# tools
IV_discover = None
from vibesimulation.workspaces.ai_import.core import autodetect as A
diagnose.autodetect.discover = lambda *a, **k: A.Found("Groq (free tier)", ["m"], "ok", True)
w.show("activity"); pg.t_connection(); chk("Test connection writes its result", wait(lambda: "Connection OK" in pg.txt.get("1.0", "end")))
diagnose.chat_model = lambda *a, **k: "OK"
pg.t_model(); chk("Test model writes its result", wait(lambda: "The model answered in" in pg.txt.get("1.0", "end")))
pg.clear(); pump(3); chk("Clear empties the log", "hello from a test" not in pg.txt.get("1.0", "end"))
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
