import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx if hasattr(w,"ctx") else w.context
f = tempfile.NamedTemporaryFile(suffix=".json", delete=False); f.write(b'{}'); f.close()
ctx.add_recent(f.name); w.show("logisim")
m = ctx.menu(); w.menubar.file_menu(m) if hasattr(w,"menubar") else w.menu.file_menu(m)
print([m.entrycget(i,"label") for i in range(m.index("end")+1) if m.type(i) not in ("separator",)])
print("recent state", m.entrycget(2,"state"))
# PDF check
a = w.actions; tv = a.table
for flag in (False, True):
    tv.show_mid.set(flag)
    out = tempfile.mktemp(suffix=".pdf")
    ctx.choose_file = lambda *x, **k: out
    ctx.say = lambda *x, **k: None
    a.pdf(); print(flag, os.path.exists(out) and os.path.getsize(out))
    os.system(f"pdftotext -layout {out} - | tail -14")
