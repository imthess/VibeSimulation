import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.core import commands as C
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
d.load_text(""); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
print("blank valid", d.valid, "text", repr(d.text))
os.system("import -display :97 -window root /tmp/pv/blank.png")
v.run(C.AddInput(pos=(100, 100))); v.run(C.AddInput(pos=(100, 160)))
v.run(C.AddComponent("AND", pos=(240, 130))); root.update()
print(d.text); print("state", d.state)
assert '"pos"' not in d.text and '"wires"' not in d.text
# drag the gate with the mouse
cv = v.canvas
def ev(t, x, y, **k): cv.event_generate(t, x=int(x), y=int(y), **k); root.update()
pl = next(p for p in d.layout.parts if p.comp.id == "g1"); s = v.scale; ox, oy = v.org
sx, sy = ox + (pl.x - 20) * s, oy + pl.y * s
ev("<Button-1>", sx, sy)
for i in range(1, 8): ev("<B1-Motion>", sx + i * 8 * s, sy + i * 9 * s)
ev("<ButtonRelease-1>", sx + 56 * s, sy + 63 * s)
print("pos after drag", d.circuit.component("g1").pos, "selected", v.sel)
assert '"pos"' not in d.text and '"wires"' not in d.text and d.state["pos"]
# turn with the keyboard
cv.focus_force(); root.update()
cv.event_generate("<Key-r>"); root.update()
print("facing", d.state["facing"], d.valid, d.layout_error)
assert d.state["facing"] == {"g1": "south"}
os.system("import -display :97 -window root /tmp/pv/rot.png")
cv.event_generate("<Key-r>"); root.update(); cv.event_generate("<Key-r>"); root.update(); print("facing", d.state["facing"])
# JSON edit keeps layout
t = d.text.replace('"AND"', '"OR"'); d.set_text(t); print("after JSON edit", d.state["pos"], d.state["facing"], d.valid)
assert d.state["pos"] and d.state["facing"]
# undo / redo
w.undo(); root.update(); print("undo ->", d.state["facing"]); w.redo(); root.update(); print("redo ->", d.state["facing"], d.circuit.component("g1").type_name)
# delete key
cv.event_generate("<Key-Delete>"); root.update(); print("after delete", len(d.circuit.components), repr(d.text[:60]))
# empty JSON again: still editable
d.set_text(""); root.update(); v.run(C.AddInput()); print("from empty again:", d.valid, d.text.strip()[:40])
# save/open sidecar
import tempfile
from vibesimulation.ui.actions import write_sidecar, load_file
d.load_text(""); v.run(C.AddComponent("NOT", pos=(200, 100))); v.run(C.RotatePart("g1", 2))
p = tempfile.mkdtemp() + "/c.json"; open(p, "w").write(d.text); write_sidecar(p, d.state)
d.load_text(""); load_file(d, p); print("reopened", d.state["pos"], d.state["facing"], '"pos"' in d.text)
ctx.cfg.clear(); ctx.save_cfg()
print("OK")
