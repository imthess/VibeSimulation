import sys, os, tempfile, pathlib, time
T = pathlib.Path(tempfile.mkdtemp()); os.environ["XDG_DATA_HOME"] = str(T/"xdg")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.file_browser import FileDialog
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx if hasattr(w,"ctx") else w.context
D = T/"data"; (D/"sub").mkdir(parents=True)
for n in ["a.json","b.json","c.circ","needle.json"]: (D/n).write_text("{}")
(D/"sub"/"deep_needle.json").write_text("{}")
ctx.ask_string = lambda *a, **k: "Renamed.json" if "Rename" in a[0] else "Fresh"
ctx.ask = lambda *a, **k: True; ctx.say = lambda *a, **k: print("SAY", a[:2])
def snap(n): root.update(); os.system(f"import -display :97 -window root {S}{n}.png")
def ok(c, m): print(("PASS " if c else "FAIL ")+m)
d = FileDialog(ctx, "open", "Open", [".json",".circ"], start=str(D)); root.update()
names = lambda: [e.name for e in d.entries]
ok(names()==["sub","a.json","b.json","c.circ","needle.json"], f"list {names()}")
d.toggle_view(); root.update(); snap("g1"); ok(d.view.get()=="grid","grid")
d.toggle_view()
d.select(names().index("a.json")); d.toggle_star(d.current()); root.update()
ok(str(D/"a.json") in ctx.cfg.get("starred",[]), "star"); 
d.goto(("starred")if False else ("starred",)); root.update(); ok(names()==["a.json"], f"starred {names()}")
d.goto(("dir",D))
d.new_folder(); root.update(); ok("Fresh" in names() and (D/"Fresh").is_dir(), "new folder")
d.select(names().index("b.json")); d.rename(); root.update(); ok((D/"Renamed.json").exists(), "rename")
d.select(names().index("Renamed.json")); d.trash(); root.update(); ok(not (D/"Renamed.json").exists(), "trash")
d.goto(("trash",)); root.update(); ok("Renamed.json" in names(), f"in trash {names()}")
snap("g2")
d.select(names().index("Renamed.json")); d.restore(); root.update(); ok((D/"Renamed.json").exists(), "restore")
d.goto(("dir",D))
d.toggle_search(); d.search.set("needle"); d.run_search()
for _ in range(30): root.update(); time.sleep(0.05)
ok(sorted(names())==["deep_needle.json","needle.json"], f"search {names()}"); snap("g3")
d.toggle_search(); root.update()
ok(d.loc[0]=="dir", "search closed")
d.select(names().index("needle.json")); d.accept(); root.update()
ok(d.result==str(D/"needle.json"), f"result {d.result}")
print("recent", ctx.cfg.get("recent"))
# save mode
d2 = FileDialog(ctx, "save", "Save", [".json"], start=str(D), name="out.json"); root.update(); snap("g4")
d2.accept(); root.update(); ok(d2.result==str(D/"out.json"), f"save {d2.result}")
print("DONE")
