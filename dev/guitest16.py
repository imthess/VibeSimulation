import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); root.geometry("1000x640"); w = MainWindow(root); ctx = w.ctx
w.show("multisim")
for name, kw in (("a", dict(rail_color="Accent")), ("b", dict(rail_style="Docked", rail_color="Light", rail_size="Medium")), ("c", dict(rail_style="Floating", rail_color="Soft", rail_side="Right", rail_size="Large", mode="dark")), ("d", dict(rail_style="Docked", rail_color="Dark", mode="dark"))):
    for k in ("rail_color","rail_style","rail_side","rail_size","mode"): ctx.cfg.pop(k, None)
    ctx.cfg.update(kw); ctx.refresh(); w.after_look(); root.update(); root.update()
    os.system(f"import -display :97 -window root {S}r_{name}.png")
ctx.cfg.clear(); ctx.save_cfg(); print("DONE")
