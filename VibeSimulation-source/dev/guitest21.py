import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.adoc.load_sample(); w.show("multisim"); root.update(); v = w.pages["multisim"].views["schematic"]; root.update()
cv = v.canvas
def ev(t, x, y): cv.event_generate(t, x=int(x), y=int(y)); root.update()
pl = next(p for p in v.L.parts if p.part.id == "R3"); s, ox, oy = v.sc
sx, sy = ox + pl.cx * s, oy + pl.cy * s
print("hit", v.hit(type("E",(),{"x":sx,"y":sy})()), pl.cx, pl.cy, v.sc); ev("<Button-1>", sx, sy); print(v._drag and v._drag["id"])
for i in range(1, 9): ev("<B1-Motion>", sx + i * 10 * s, sy + i * 5 * s)
print(v._drag); ev("<ButtonRelease-1>", sx + 80 * s, sy + 40 * s)
print("pos", w.adoc.netlist.part("R3").pos, "valid", w.adoc.valid, '"pos"' in w.adoc.text)
os.system("import -display :97 -window root /tmp/pv/drag3.png")
w.undo(); root.update(); print("undo", w.adoc.netlist.part("R3").pos)
ctx.cfg.clear(); ctx.save_cfg()
