import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root)
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
snap("h_home")
for p in ("logisim","import","multisim","settings"): w.show(p); snap("h_"+p)
w.show("logisim"); wk=w.pages["logisim"]; wk.swap("circuit","json"); snap("h_swap")
wk.toggle("table"); snap("h_hide"); wk.toggle("table"); wk.toggle("json"); wk.toggle("circuit"); snap("h_one"); wk.reset()
w.pages["settings"].pick("Logisim"); w.toggle_dark(); w.show("settings"); snap("h_dark")
w.actions.new(); print("blank valid", w.doc.valid, w.doc.errors)
w.undo(); print("undo ok", w.doc.valid)
w.menubar.file_menu(w.ctx.menu()); w.menubar.download_menu(w.ctx.menu()); w.menubar.view_menu(w.ctx.menu())
print("DONE")
