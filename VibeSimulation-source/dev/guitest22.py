import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.adoc.load_sample(); w.show("multisim"); root.update(); v = w.pages["multisim"].views["schematic"]; root.update()
cv = v.canvas
def ev(t, x, y): cv.event_generate(t, x=int(x), y=int(y)); root.update()
L = v.L; s, ox, oy = v.sc
cands = [(k, t) for k, t in enumerate(L.wires) if t[1] == t[3] and t[2] - t[0] >= 60 and t[4] not in ("0",)]
print(cands)
k, t = cands[0]; sx, sy = ox + (t[0] + t[2]) / 2 * s, oy + (t[1] + t[3]) / 2 * s
print("hit", v.hit_wire(type("E", (), {"x": sx, "y": sy})()), v.hit(type("E", (), {"x": sx, "y": sy})()))
ev("<Button-1>", sx, sy)
for i in range(1, 6): ev("<B1-Motion>", sx, sy - i * 10 * s)
ev("<ButtonRelease-1>", sx, sy - 50 * s)
print("wires" , w.adoc.netlist.wires, "valid", w.adoc.valid, v.status.cget("text"))
os.system("import -display :97 -window root /tmp/pv/wire3.png")
w.undo(); root.update(); print("undo", w.adoc.netlist.wires)
ctx.cfg.clear(); ctx.save_cfg()
