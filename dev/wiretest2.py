import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.doc.load_sample(); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
cv = v.canvas
def ev(t, x, y): cv.event_generate(t, x=int(x), y=int(y)); root.update()
before = {(x[4]): x for x in w.doc.layout.wires}
pl = next(p for p in w.doc.layout.parts if p.comp.id == "g2"); s = v.scale; ox, oy = v.org
sx, sy = ox + (pl.x - 15) * s, oy + pl.y * s
ev("<Button-1>", sx, sy)
for i in range(1, 9): ev("<B1-Motion>", sx + i * 5 * s, sy + i * 10 * s)
ev("<ButtonRelease-1>", sx + 40 * s, sy + 80 * s)
print(w.doc.circuit.component("g2").pos, w.doc.valid); print(w.doc.text)
print("A wires unchanged:", sorted(x[:4] for x in w.doc.layout.wires if x[4] == "A") == sorted(x[:4] for x in [y for y in before.values()] if False) or "see json")
os.system("import -display :97 -window root /tmp/pv/wire4.png")
w.undo(); root.update(); print("undo ok", w.doc.circuit.component("g2").pos, bool(w.doc.circuit.wires))
ctx.cfg.clear(); ctx.save_cfg()
