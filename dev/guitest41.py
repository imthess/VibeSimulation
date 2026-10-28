"""About box, update check, examples gallery, autosave and crash recovery in the real window."""
import sys, os, time, json, http.server, threading, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from pathlib import Path
import vibesimulation.product.recovery as RC
RC.PATH = Path(tempfile.mkdtemp()) / "rec.json"
from vibesimulation.product.recovery import Recovery
Recovery.__init__.__defaults__ = (RC.PATH,)
from vibesimulation.components import load_all; load_all()
from vibesimulation import __version__
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.product.examples import EXAMPLES, find
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=4):
    for _ in range(n): root.update(); time.sleep(0.02)
w.ctx.toaster.show = lambda *a, **k: None
chk("version is 1.3.0", __version__ == "1.3.0")
# ---- About
w.show_about(); pump()
from vibesimulation.ui.product.about import AboutBox
box = [c for c in root.winfo_children() if isinstance(c, AboutBox)][0]
chk("about shows the version", __version__ in " ".join(str(x.cget("text")) for x in box.body.winfo_children() if x.winfo_class() == "Label"))
box.check(); pump(); chk("no address: says nothing was checked", "No update address" in box.res.cget("text"))
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"version": "9.9.9", "url": "https://example.org"}).encode())
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
w.ctx.cfg["update_url"] = f"http://127.0.0.1:{srv.server_address[1]}/"
box.check()
for _ in range(60):
    pump(2)
    if "9.9.9" in box.res.cget("text"): break
chk("update found and shown", "9.9.9" in box.res.cget("text"))
os.system("import -display :97 -window root /tmp/pv/about.png 2>/dev/null")
box.destroy(); pump()
# ---- gallery
w.show_gallery("vlsi"); pump()
from vibesimulation.ui.product.gallery import GalleryBox
g = [c for c in root.winfo_children() if isinstance(c, GalleryBox)][0]
chk("gallery lists VLSI examples", g.list.size() == len([e for e in EXAMPLES if e.section == "vlsi"]))
g.list.selection_clear(0, "end"); g.list.selection_set(1); g.pick(); pump()
chk("tutorial shown", "Run" in g.st.cget("text") and g.h.cget("text") == "Counter with a testbench")
os.system("import -display :97 -window root /tmp/pv/gallery.png 2>/dev/null")
g.open(); pump(6)
chk("example opened in VLSI", w.current == "vlsi" and w.vdoc.cur == "counter" and "counter_tb" in w.vdoc.tb_text)
for sec, key in (("logisim", "full_adder"), ("multisim", "rectifier")):
    from vibesimulation.ui.product.gallery import open_example
    open_example(w, find(sec, key)); pump()
    chk(f"{sec} example opens", w.current == sec and (w.doc.valid if sec == "logisim" else w.adoc.valid))
# ---- autosave and recovery
w.hooks.rec.start(w)   # pretend the program just started with these documents
w.adoc.load_text(json.dumps({"components": [{"id": "V1", "type": "V", "value": 7, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 70, "nodes": ["a", "0"]}]}))
w.hooks.tick(); pump()
chk("autosave file written", RC.PATH.exists() and "V1" in RC.PATH.read_text())
# simulate a crash: a new window sees the file
root.destroy()
root = tk.Tk(); root.geometry("1400x900"); w2 = MainWindow(root); w2.ctx.cfg.clear()
chk("new window finds the pending recovery", w2.hooks.pending is not None)
asked = []
w2.ctx.ask = lambda t, m, parent=None: (asked.append(m), True)[1]
w2.hooks.offer(); pump(6)
chk("question mentions the multisim work", asked and "Multisim" in asked[0])
chk("work restored", '"7"' in w2.adoc.text or "7" in w2.adoc.text and "V1" in w2.adoc.text)
w2.close() if False else w2.hooks.finish()
chk("clean exit removes the file", not RC.PATH.exists())
print("ALL OK" if ok else "SOME FAILED"); root.destroy()
