import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.core.serializer import parse
from vibesimulation.export.logisim import to_circ
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.doc.load_sample(); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
cv = v.canvas; d = w.doc
def ev(t, x, y, state=0):
    st = state | (0x100 if "Motion" in t else 0)
    cv.event_generate(t, x=int(x), y=int(y), state=st); root.update()
def L2S(x, y): s = v.scale; ox, oy = v.org; return ox + x * s, oy + y * s
def drag(x0, y0, x1, y1, state=0, steps=8):
    sx, sy = L2S(x0, y0); ex, ey = L2S(x1, y1)
    ev("<Button-1>", sx, sy, state)
    for i in range(1, steps + 1): ev("<B1-Motion>", sx + (ex - sx) * i / steps, sy + (ey - sy) * i / steps, state)
    ev("<ButtonRelease-1>", ex, ey, state)
def ok(name, cond): print(("ok   " if cond else "FAIL ") + name)
# 1. click toggles input
sx, sy = L2S(110, 120); ev("<Button-1>", sx, sy); ev("<ButtonRelease-1>", sx, sy); ok("click toggles A", d.invals.get("A") == 1)
ev("<Button-1>", sx, sy); ev("<ButtonRelease-1>", sx, sy)
# 2. move input pin B downward
drag(110, 160, 110, 260); pb = next(p for p, x, y in d.circuit.inputs and [(p, 0, 0) for p in d.circuit.inputs] if p.name == "B")
ok("pin B moved", pb.pos is not None and d.valid); print("   B pos", pb.pos)
# 3. move output pin
pl = d.layout.outputs[0]; drag(pl[1] + 20, pl[2], pl[1] + 20, pl[2] - 60); ok("output Y moved", d.circuit.outputs[0].pos is not None and d.valid)
# 4. drag a vertex (corner) of net n1 and Shift-bend
n1 = [t for t in d.layout.wires if t[4] == "n1"]; print("   n1", n1)
long = max(n1, key=lambda t: (t[2] - t[0]) + (t[3] - t[1]))
mx, my = (long[0] + long[2]) // 20 * 10, (long[1] + long[3]) // 20 * 10
before = str(d.state); drag(mx, my, mx, my + 40, state=1)
ok("shift-bend created", str(d.state) != before and d.valid and "n1" in d.circuit.wires); print("   n1 route", d.circuit.wires.get("n1"))
cs = d.circuit.wires["n1"]; corner = next(((t[0], t[1]) for t in cs if t[0] == mx and t[1] == my + 40), None) or (mx, my + 40)
before = str(d.state); drag(corner[0], corner[1], corner[0] + 20, corner[1] + 10)
ok("corner moved", str(d.state) != before and d.valid)
# 5. delete a redundant piece: add a dangling stub through the JSON, then delete it
c2 = d.circuit.copy(); c2.wires["A"] = [list(t[:4]) for t in d.layout.wires if t[4] == "A"] + [[130, 100, 130, 120]]
from vibesimulation.core.serializer import dumps
d.set_text(dumps(c2)); root.update()
k = next((i for i, t in enumerate(d.layout.wires) if t[4] == "A" and tuple(t[:4]) == (130, 100, 130, 120)), None); print("   stub", k)
if k is not None: v.delete_piece(k); ok("stub deleted", not any(tuple(t[:4]) == (130, 100, 130, 120) for t in d.layout.wires))
# 6. connect: drag from NOT's output pin to the NAND input? ( g2 out n2 -> g1 In3 ) 
g1 = next(p for p in d.layout.parts if p.comp.id == "g1"); g2 = next(p for p in d.layout.parts if p.comp.id == "g2")
pin = g1.comp.port("In3"); out = g2.comp.port("Out")
drag(g2.x + out.dx, g2.y + out.dy, g1.x + pin.dx, g1.y + pin.dy)
ok("connect drag rewired g1.In3 to n2", d.circuit.component("g1").ins.get("In3") == "n2" and d.valid); print("   ", d.circuit.component("g1").ins)
to_circ(d.circuit); c3, e = parse(d.text); ok("json reloads", not e)
os.system("import -display :97 -window root /tmp/pv/drag5.png")
d.undo(); root.update()
ctx.cfg.clear(); ctx.save_cfg()
