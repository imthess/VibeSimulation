import sys, os, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.file_browser import FileDialog
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx if hasattr(w,"ctx") else w.context
T = pathlib.Path(tempfile.mkdtemp()); (T/"sub").mkdir()
for n,s in [("a.json","{}"),("b.json","x"*3000),("c.txt","t"),("d.circ","<x/>")]: (T/n).write_text(s)
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
d = FileDialog(ctx, "open", "Open", [".json",".circ"], start=str(T))
root.update()
def step(name, fn):
    try: fn(); root.update()
    except Exception as e:
        import traceback; traceback.print_exc(); print("FAIL", name)
step("snap", lambda: snap("f1"))
step("sort", lambda: d.sort_by("size"))
step("grid", lambda: [setattr(d,"grid",True), d.render()] if hasattr(d,"grid") else None)
step("snap2", lambda: snap("f2"))
for loc in [("recent",),("starred",),("network",),("trash",)]:
    step(str(loc), lambda loc=loc: d.goto(loc))
step("snap3", lambda: snap("f3"))
step("home", lambda: d.goto(("dir", pathlib.Path.home())))
step("back", d.back); step("fwd", d.forward); step("up", d.up)
print("DONE")
d.destroy() if hasattr(d,"destroy") else None
