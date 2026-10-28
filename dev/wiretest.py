import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DISPLAY", ":97")
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.core.serializer import parse
from vibesimulation.export.logisim import to_circ
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.doc.load_sample(); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
lay = w.doc.layout; s = v.scale; ox, oy = v.org
vert = [(k, x) for k, x in enumerate(lay.wires) if x[0] == x[2] and x[3] - x[1] >= 20]; print(lay.wires)
print("n1 vertical pieces", vert)
k, seg = vert[0]; sx, sy = ox + seg[0] * s, oy + (seg[1] + seg[3]) / 2 * s
cv = v.canvas
def ev(t, x, y): cv.event_generate(t, x=int(x), y=int(y)); root.update()
print("hit", v.hit(type("E", (), {"x": sx, "y": sy})()))
ev("<Button-1>", sx, sy)
for i in range(1, 7): ev("<B1-Motion>", sx - i * 10 * s, sy)
os.system("import -display :97 -window root /tmp/pv/wire1.png")
ev("<ButtonRelease-1>", sx - 60 * s, sy)
print("wires in json:", '"wires"' in w.doc.text, "valid", w.doc.valid, v.status.cget("text"))
print(w.doc.text)
os.system("import -display :97 -window root /tmp/pv/wire2.png")
to_circ(w.doc.circuit)
c2, e = parse(w.doc.text); assert not e and w.doc.state["wires"] and not c2.wires
w.undo(); root.update(); print("undo ->", '"wires"' in w.doc.text)
ctx.cfg.clear(); ctx.save_cfg()
