import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from bigtest import big
import tkinter as tk
from vibesimulation.components import load_all
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
seed = int(sys.argv[1]); out = sys.argv[2]
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ctx = w.ctx
w.show("logisim"); pg = w.pages["logisim"]
for k in ("json", "table"):
    if k not in pg.hidden: pg.toggle(k)
root.update(); pg.views["json"].doc.set_text(json.dumps(big(seed))); root.update(); root.update()
cv = pg.views["circuit"]
if len(sys.argv) > 3: cv.zoom_at(float(sys.argv[3]), 500, 330); root.update()
os.system(f"import -display :97 -window root {S}{out}.png")
ctx.cfg.clear(); ctx.save_cfg()
