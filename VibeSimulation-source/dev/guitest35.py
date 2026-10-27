"""Logisim-style wire editing: select a wire, Delete; pull a wire end off a pin and drop it on another."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
CIR = {"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NAND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["C"], "out": "n2"}, {"id": "g3", "type": "NOR", "in": ["n1", "n2"], "out": "Y"}]}
def fresh():
    w.show("logisim"); w.doc.load_text(json.dumps(CIR)); root.update(); return w.pages["logisim"].views["circuit"] if hasattr(w.pages["logisim"], "views") else None
v = fresh(); print(type(v))
def scr(x, y): s = v.scale; ox, oy = v.org; return int(ox + x * s), int(oy + y * s)
def ev(kind, x, y, **kw): v.canvas.event_generate(kind, x=x, y=y, **kw); root.update()
def click(x, y):
    import time; time.sleep(1.0); ev("<Button-1>", x, y); ev("<ButtonRelease-1>", x, y)
def drag(a, b, n=6):
    import time; time.sleep(1.0)
    ev("<Button-1>", *a)
    for i in range(1, n + 1): ev("<B1-Motion>", int(a[0] + (b[0] - a[0]) * i / n), int(a[1] + (b[1] - a[1]) * i / n))
    ev("<ButtonRelease-1>", *b)
d = w.doc; lay = d.layout
print([ (k, x) for k, x in enumerate(lay.wires)][:12])
# 1. select the wire carrying n1 and delete it: g3 input unplugged
k = next(i for i, x in enumerate(lay.wires) if x[4] == "n1"); x1, y1, x2, y2, net = lay.wires[k]
mid = scr((x1 + x2) / 2, (y1 + y2) / 2); click(*mid)
chk("wire selected", v.wsel and next(iter(v.wsel))[0] == "n1")
v.canvas.focus_force(); root.update(); v.canvas.event_generate("<Key-Delete>"); root.update()
g3 = d.circuit.component("g3"); print(g3.ins)
chk("Delete unplugged the pin fed by that wire", d.valid and "In1" not in g3.ins and g3.ins.get("In2") == "n2")
chk("circuit is still shown", d.layout is not None and not v.wsel)
d.undo(); root.update(); chk("undo brings the wire back", d.circuit.component("g3").ins.get("In1") == "n1")
# 2. delete a component with the Delete key
lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g2"); x0, y0, x1, y1 = pl.comp.bounds(); cx, cy = scr(pl.x + (x0 + x1) / 2, pl.y + (y0 + y1) / 2); click(cx, cy); v.canvas.focus_force(); root.update()
print('sel', v.sel, v.sels, v.wsel, root.focus_get()); v.canvas.event_generate("<Key-Delete>"); root.update(); print(d.errors, d.circuit.component('g2')); chk("gate deleted by Delete", d.circuit.component("g2") is None)
d.undo(); root.update()
# 3. pull the end of the wire on g3 input 1 off the pin and drop it on g3 input 2 (moves the wire)
lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g3"); pt1 = pl.comp.port("In1"); pt2 = pl.comp.port("In2")
a = scr(pl.x + pt1.dx, pl.y + pt1.dy); b = scr(pl.x + pt2.dx, pl.y + pt2.dy); drag(a, b)
g3 = d.circuit.component("g3"); print(g3.ins, d.errors)
chk("wire end moved to the other pin", g3.ins.get("In2") == "n1" and "In1" not in g3.ins)
d.undo(); root.update()
# 4. drag the end off a pin into empty space: unplug
lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g3"); a = scr(pl.x + pt2.dx, pl.y + pt2.dy); b2 = (a[0] - 10, a[1] - 150); drag(a, b2)
print(d.circuit.component('g3').ins, d.errors, v.status.cget('text'))
chk("dropped in empty space: pin unplugged", "In2" not in d.circuit.component("g3").ins and d.valid)
d.undo(); root.update()
# 5. an unplugged pin dragged onto a wire of another signal connects to it
C = __import__("vibesimulation.core.commands", fromlist=["x"]); d.run(C.Rewire("g3", "In1", None)); root.update()
lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g3"); a = scr(pl.x + pt1.dx, pl.y + pt1.dy)
k = next(i for i, x in enumerate(lay.wires) if x[4] == "A"); x1, y1, x2, y2, net = lay.wires[k]; drag(a, scr((x1 + x2) / 2, (y1 + y2) / 2))
chk("floating pin dragged onto a wire connects to its signal", d.circuit.component("g3").ins.get("In1") == "A")
print("ALL OK" if ok else "SOME FAILED")
