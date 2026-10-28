import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
ctx.cfg["mode"]="dark"; ctx.refresh(); w.after_look()
for pg in ("home","logisim","multisim","import","settings"):
    w.show(pg); snap("d_"+pg)
w.show("logisim"); ctx.menu_test=None
m = ctx.menu(); m.add_command(label="New", accelerator="Ctrl+N"); m.add_separator(); m.add_command(label="Exit"); m.tk_popup(700, 120); snap("d_menu"); m.close_all()
ctx.cfg.clear(); ctx.save_cfg()
print("DONE")
