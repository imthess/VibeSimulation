"""Multisim: select a part / wire, Delete, drag a terminal to another net or into empty space."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.analog.layout import pin_xy
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
CIR = {"components": [{"id": "V1", "type": "VoltageSource", "value": "12", "nodes": ["a", "0"]}, {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["a", "b"]},
                      {"id": "R2", "type": "Resistor", "value": "2k", "nodes": ["b", "0"]}, {"id": "R3", "type": "Resistor", "value": "3k", "nodes": ["b", "c"]}, {"id": "R4", "type": "Resistor", "value": "4k", "nodes": ["c", "0"]}]}
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); root.update(); d = w.adoc; sv = w.pages["multisim"].views["schematic"]; root.update()
def ev(kind, x, y, **kw): sv.canvas.event_generate(kind, x=int(x), y=int(y), **kw); root.update()
def click(x, y): time.sleep(0.8); ev("<Button-1>", x, y); ev("<ButtonRelease-1>", x, y)
def drag(a, b, n=6):
    time.sleep(0.8); ev("<Button-1>", *a)
    for i in range(1, n + 1): ev("<B1-Motion>", a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
    ev("<ButtonRelease-1>", *b)
def tp(pid, k): pl = next(p for p in sv.L.parts if p.part.id == pid); X, Y = pin_xy(pl, k); s, ox, oy = sv.sc; return ox + X * s, oy + Y * s
def part_xy(pid): pl = next(p for p in sv.L.parts if p.part.id == pid); s, ox, oy = sv.sc; return ox + pl.cx * s, oy + pl.cy * s
nodes = lambda pid: list(d.netlist.part(pid).nodes)
# 1. click a part, Delete
click(*part_xy("R4")); chk("part selected", sv.sel == "R4"); sv.canvas.focus_force(); root.update(); sv.canvas.event_generate("<Key-Delete>"); root.update()
chk("Delete removed R4", d.netlist.part("R4") is None and d.valid); print(nodes("R3"), d.errors, sv.status.cget("text"))
chk("R3's free end is left unplugged", nodes("R3")[1].startswith("~"))
d.undo(); root.update(); chk("undo restores R4", d.netlist.part("R4") is not None)
# 2. drag the unplugged-side terminal: drag R3 terminal 2 into empty space -> unplugged; then back onto R4's terminal
drag(tp("R3", 1), (tp("R3", 1)[0] + 5, tp("R3", 1)[1] - 120))
print(nodes("R3"), nodes("R4"), sv.status.cget("text"))
chk("terminal dropped on empty space is unplugged", nodes("R3")[1].startswith("~") and d.valid)
a = tp("R3", 1); b = tp("R4", 0); drag(a, b)
print(nodes("R3"), nodes("R4"), sv.status.cget("text"))
chk("unplugged terminal dropped on a terminal joins that net", d.valid and nodes("R3")[1] == nodes("R4")[0] and not nodes("R3")[1].startswith("~"))
d.undo(); d.undo(); root.update()
# 3. select a wire piece and delete it
from vibesimulation.layout.routing import norm
wires = [w_ for w_ in sv.L.wires if w_[4] == "b"]; print(wires)
w_ = max(wires, key=lambda t: abs(t[2] - t[0]) + abs(t[3] - t[1])); s, ox, oy = sv.sc; mid = (ox + (w_[0] + w_[2]) / 2 * s, oy + (w_[1] + w_[3]) / 2 * s)
click(*mid); chk("wire selected", bool(sv.wsel)); sv.canvas.focus_force(); sv.canvas.event_generate("<Key-Delete>"); root.update()
print([ (p.id, p.nodes) for p in d.netlist.parts], d.errors, sv.status.cget("text"))
chk("wire deleted: circuit still valid, some terminal unplugged", d.valid and any(str(n).startswith("~") for p in d.netlist.parts for n in p.nodes))
d.undo(); root.update()
# 4. a change that would be invalid is refused: delete V1 would leave no source? (still valid) -> instead delete the only ground connections
print("ALL OK" if ok else "SOME FAILED")
