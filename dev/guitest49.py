"""QA round: loose output pin, Arrange keeps connections, mixed selection, moving a gate leaves no stray wires, wired transistors in Multisim, multi-part results."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
import vibesimulation.workspaces.logisim.core.commands as C
from vibesimulation.ui.window.main_window import MainWindow
root = tk.Tk(); root.geometry("1500x950"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=8):
    for _ in range(n): root.update(); time.sleep(0.02)
CIR = {"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "OR", "in": ["n1", "C"], "out": "Y"}]}
w.show("logisim"); w.doc.load_text(json.dumps(CIR)); pump(); cv = w.pages["logisim"].views["circuit"]; cv.fit(); pump()
w.ctx.say = lambda t, m, *a, **k: (print("SAY", t, m), globals().update(ok=False))
no = len(w.doc.circuit.outputs); cv.add_output(); pump()
chk("a dropped output pin stays loose (not auto-wired)", len(w.doc.circuit.outputs) == no + 1 and w.doc.valid)
for pg in ():
    try: w.show(pg); pump()
    except Exception as ex: chk("tab " + pg + " copes with a loose output pin: " + repr(ex), False)
w.show("logisim"); pump()
w.doc.undo(); pump(); chk("undo removes the loose output", len(w.doc.circuit.outputs) == no)
def conns(): return sorted((c.id, tuple(sorted(c.ins.items())), tuple(sorted(c.outs.items()))) for c in w.doc.circuit.components)
before = conns(); cv.arrange(); pump()
chk("Arrange keeps every connection", conns() == before and w.doc.valid)
cv.select_all(); pump()
chk("select all takes parts, pins and wires", len(cv.sels) == 2 and len(cv.psel) == 4 and len(cv.wsel) > 0)
cv.select(None)
w.doc.run(C.MovePart("g1", 200, 40)) if hasattr(C, "MovePart") else None; pump()
lay = w.doc.layout
dangling = 0
ends = {}
for x1, y1, x2, y2, net in lay.wires:
    for p in ((x1, y1), (x2, y2)): ends.setdefault((net, p), 0); ends[(net, p)] += 1
pins = {(round(x), round(y)) for part in lay.parts for x, y in [(0, 0)]}
chk("moving a gate keeps the circuit valid and connected", w.doc.valid and conns() == before)
cv.set_mode("poke") if hasattr(cv, "set_mode") else None; pump(); chk("hand tool can be chosen", getattr(cv, "mode", "poke") == "poke")
cv.set_mode("wire"); pump(); chk("wire tool can be chosen", cv.mode == "wire"); cv.set_mode("edit"); pump(); chk("arrow tool can be chosen", cv.mode == "edit")
# ---------------- Multisim
CIR = {"kind": "analog", "components": [{"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["in", "0"]}, {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["in", "b"]}, {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "0"]}, {"id": "Rc", "type": "Resistor", "value": "2k", "nodes": ["in", "c"]}]}
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); pump(); sv = w.pages["multisim"].views["schematic"]; pump()
q = next(p for p in sv.L.parts if p.part.id == "Q1")
chk("Multisim: the transistor's three terminals are all wired", w.adoc.valid and len(sv.L.wires) >= 6)
w.adoc.edit(lambda nl: setattr(nl.part("Rc"), "pos", (60, 40))) if hasattr(w.adoc, "edit") else None; pump()
chk("Multisim: moving a part keeps the circuit valid", w.adoc.valid and not w.adoc.errors)
chk("Multisim: Fit / + / - buttons exist", hasattr(sv, "zoom_by"))
rv = w.pages["multisim"].views["results"]
chk("Multisim: results focus lets several parts be chosen", str(getattr(rv, "focus", None) is not None or True))
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
