import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
for pg in ("logisim","multisim"):
    w.show(pg); snap("l_"+pg)
print("DONE")
ctx.cfg.clear(); ctx.save_cfg()
