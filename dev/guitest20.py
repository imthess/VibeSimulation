import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.doc.load_sample(); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
pl = next(p for p in w.doc.layout.parts if p.comp.id == "g3"); s = v.scale; ox, oy = v.org
sx, sy = ox + (pl.x - 20) * s, oy + pl.y * s
cv = v.canvas
def ev(t, x, y, **k): cv.event_generate(t, x=int(x), y=int(y), **k); root.update()
print("hit", v.hit(type("E", (), {"x": sx, "y": sy})()))
ev("<Button-1>", sx, sy)
for i in range(1, 8): ev("<B1-Motion>", sx + i * 8 * s, sy + i * 9 * s)
os.system("import -display :97 -window root /tmp/pv/drag1.png")
ev("<ButtonRelease-1>", sx + 56 * s, sy + 63 * s)
print("pos", w.doc.circuit.component("g3").pos, "valid", w.doc.valid)
os.system("import -display :97 -window root /tmp/pv/drag2.png")
# drop onto g1 -> refused
pl1 = next(p for p in w.doc.layout.parts if p.comp.id == "g1"); before = w.doc.text
pl = next(p for p in w.doc.layout.parts if p.comp.id == "g3"); sx, sy = ox + (pl.x - 20) * s, oy + pl.y * s
ev("<Button-1>", sx, sy)
tx, ty = ox + (pl1.x - 20) * s, oy + pl1.y * s
for i in range(1, 11): ev("<B1-Motion>", sx + (tx - sx) * i / 10, sy + (ty - sy) * i / 10)
ev("<ButtonRelease-1>", tx, ty); print("refused:", w.doc.text == before, v.status.cget("text"))
# undo
w.undo(); root.update(); print("after undo pos", w.doc.circuit.component("g3").pos)
ctx.cfg.clear(); ctx.save_cfg()
