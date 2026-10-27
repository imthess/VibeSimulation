import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.widgets import Segmented
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.show("settings"); root.update()
def find(wd, out):
    if isinstance(wd, Segmented): out.append(wd)
    for c in wd.winfo_children(): find(c, out)
    return out
segs = find(root, []); print("segments", len(segs))
seg = [s for s in segs if "Dark" in str(getattr(s, "options", getattr(s, "items", "")))] or segs
s = seg[0]; print(vars(s).keys() if False else "")
def click(s, frac):
    root.update(); x = int(s.winfo_width() * frac); y = s.winfo_height() // 2
    s.event_generate("<Motion>", x=x, y=y); s.event_generate("<ButtonPress-1>", x=x, y=y); s.event_generate("<ButtonRelease-1>", x=x, y=y); root.update()
bgs = {}
for name, frac in (("dark", .5), ("light", .17), ("system", .85)):
    click(s, frac); print(name, "->", ctx.cfg.get("mode"), "dark?", ctx.dark, json.loads(open(os.path.expanduser("~/.vibesimulation.json")).read()).get("mode"))
ctx.cfg.clear(); ctx.save_cfg()
