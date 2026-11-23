"""The IC window: Gate view, IC view and X-ray view of the same circuit; flipping an input, moving a chip, rewiring a pin in the X-ray view (the
circuit and its JSON stay as they were) and the circuit tabs."""
import sys, os, json, tkinter as tk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
from vibesimulation.workspaces.logisim.ic.view import open_ic_view
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
doc = w.doc
text = json.dumps({"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [
    {"id": "g1", "type": "NAND", "in": ["A", "B", "C"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["C"], "out": "n2"},
    {"id": "g3", "type": "AND", "in": ["A", "n2"], "out": "n3"}, {"id": "g4", "type": "NOR", "in": ["n1", "n3"], "out": "Y"}]})
w.show("logisim"); doc.load_text(text); root.update()
win = open_ic_view(w.ctx, doc, w.pages["logisim"]); root.update(); win.refresh(); root.update()
chk("tabs: Summary, Gate view, IC view, X-ray", [t for t, _ in __import__("vibesimulation.workspaces.logisim.ic.view", fromlist=["TABS"]).TABS][:4] == ["Summary", "Gate view", "IC view", "X-ray"])
for key in ("gate", "ic", "xray", "sum", "chips", "wires", "lib"):
    win.show(key); root.update(); win.update()
    chk(f"tab {key} draws", True)
win.show("ic"); root.update()
items = win.ic_zoom.c.find_all(); chk("IC view has drawn items", len(items) > 50)
chk("IC view: 4 chips (7410, 7404, 7408, 7402)", sorted(c.part for c in win.plan.chips) == ["7402", "7404", "7408", "7410"])
for n in win.sch.nodes:                                              # one VCC and one GND pin per chip
    if n.kind == "chip": chk(f"{n.ref}: one VCC pin and one GND pin", sum(1 for p in n.pins if p.key in (str(n.chip.chip.vcc), str(n.chip.chip.gnd))) == 2)
doc.set_input("A", 1); doc.set_input("B", 1); doc.set_input("C", 0); root.update(); win.live(); root.update()
chk("chips agree with the gates", win.sess.status().endswith("✓"))
win.show("xray"); root.update(); chk("X-ray view draws the whole circuit", len(win.x_zoom.c.find_all()) > 150 and win.xsch.width > win.sch.width)
# dragging chips and terminals is a view setting: the circuit text stays
before = doc.text
for xray in (False, True):
    ref = next(n.ref for n in (win.xsch if xray else win.sch).nodes if n.kind == "chip")
    n0 = (win.xsch if xray else win.sch).node(ref); x0, y0 = n0.x, n0.y
    win.move_node(ref, 120, 80, xray); win.move_node(ref, None, None, xray)
    n1 = (win.xsch if xray else win.sch).node(ref)
    chk(f"{'X-ray' if xray else 'IC'} view: a dragged chip moves ({x0:.0f},{y0:.0f}) -> ({n1.x:.0f},{n1.y:.0f})", abs(n1.x - x0 - 120) <= 10 and abs(n1.y - y0 - 80) <= 10)
    for w_ in (win.xsch if xray else win.sch).wires:
        ends = {(win.xsch if xray else win.sch).pin_xy[(n.ref, pn.key)] for n in (win.xsch if xray else win.sch).nodes for pn in n.pins if pn.net == w_.net}
        chk(f"wire {w_.name} still reaches every pin after the move", ends <= {pt for sg in w_.segs for pt in sg}) if w_.net != "x" else None
    win.arrange(xray)
chk("moving keeps the circuit text", doc.text == before)
# rewire in the X-ray view
ch = win.plan.chips[0]; win.sess.set_pin(ch.ref, 1, "GND"); root.update(); win.refresh(); root.update()
chk("rewiring leaves the circuit JSON alone", doc.text == before)
chk("the rewired pin is marked", (ch.ref, 1) in win.sess.plan().edited)
win.x_reset_all(); root.update()
# editing from the IC view changes the circuit (and the Gate view follows)
from vibesimulation.workspaces.logisim.ic import edit as E
c7410 = next(c for c in win.plan.chips if c.part == "7410")
src = E.pin_source(doc, c7410, 2); chk("pin 2 of the 7410 is input In2 of gate g1", src and src[0].id == "g1" and src[1] == "In2")
chk("rewiring in the IC view edits the circuit", E.set_input(doc, "g1", "In2", "C") is None and doc.circuit.component("g1").ins["In2"] == "C" and '"A", "C", "C"' in doc.text)
win.refresh(); root.update()
c7410 = next(c for c in win.plan.chips if c.part == "7410"); chk("change IC offers the 7411 (AND3)", ("AND3", "7411") in E.swap_choices(doc, c7410))
E.swap_type(doc, c7410, "AND3"); win.refresh(); root.update()
chk("changing the IC changes the gates and the chips follow", doc.circuit.component("g1").type_name == "AND" and "7411" in [c.part for c in win.plan.chips])
chk("no option checkboxes in the IC window", not hasattr(win, "reuse") and not hasattr(win, "alt_adder"))
rows = __import__("vibesimulation.workspaces.logisim.ic.report", fromlist=["x"]).logisim_rows(doc.circuit, win.plan)
chk("Summary lists the Logisim parts only", all("readboard" not in r[1] and "esistor" not in r[1] and "umper" not in r[1] for r in rows) and any("gate" in r[1] for r in rows))
# circuit tabs
chk("circuit tab strip exists", w.pages["logisim"].strip is not None)
win.destroy(); root.update()
print("PASS" if ok else "FAILED"); root.destroy(); sys.exit(0 if ok else 1)
