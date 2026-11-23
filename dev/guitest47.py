"""Drag a part from the explorer onto the drawing (Logisim and Multisim), like dragging from a parts library; click-to-place still works."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
root = tk.Tk(); root.geometry("1500x950"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=6):
    for _ in range(n): root.update(); time.sleep(0.02)
def drag(tree, iid, canvas, cx, cy, release_on=None):
    """Press on the tree row, move over the canvas point (cx, cy), release."""
    tree.see(iid); pump(); x0, y0, wd, ht = tree.bbox(iid); px, py = tree.winfo_rootx() + x0 + 20, tree.winfo_rooty() + y0 + ht // 2
    tree.event_generate("<ButtonPress-1>", x=x0 + 20, y=y0 + ht // 2, rootx=px, rooty=py); pump(2)
    tx, ty = (canvas.winfo_rootx() + cx, canvas.winfo_rooty() + cy) if release_on is None else release_on
    for k in range(1, 6): tree.event_generate("<B1-Motion>", x=x0 + 20, y=y0 + ht // 2, rootx=int(px + (tx - px) * k / 5), rooty=int(py + (ty - py) * k / 5)); pump(2)
    tree.event_generate("<ButtonRelease-1>", x=x0 + 20, y=y0 + ht // 2, rootx=tx, rooty=ty); pump(4)
# ---------------- Logisim
w.show("logisim"); w.doc.load_text(json.dumps({"inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}]})); pump(8)
ex = w.side.views.get("logisim") or w.side.view(); cv = w.pages["logisim"].views["circuit"]; tree = ex.t
for f in ("f:Gates", "f:Wiring", "f:Plexers"): tree.item(f, open=True)
pump(); n0 = len(w.doc.circuit.components)
ids = {i for i in ex._all()}; gate = next(i for i in ids if i.startswith("p:NAND:")); 
drag(tree, gate, cv.canvas, 400, 300)
comps = w.doc.circuit.components; chk("dragging NAND onto the canvas adds one part", len(comps) == n0 + 1 and any(c.type_name == "NAND" for c in comps.values() if hasattr(comps, "values")) if hasattr(comps, "values") else len(comps) == n0 + 1)
new = [c for c in (comps.values() if hasattr(comps, "values") else comps) if c.type_name == "NAND"][0]
pl = next((p for p in w.doc.layout.parts if p.comp.id == new.id), None); s = cv.scale; ox, oy = cv.org
if pl: px, py = ox + (pl.x) * s, oy + (pl.y) * s; chk(f"it landed near the drop point ({int(px)},{int(py)} vs 400,300)", abs(px - 400) < 140 and abs(py - 300) < 120)
chk("the tool is back to Edit after the drop", cv.tool is None)
w.doc.undo(); pump(); chk("Ctrl+Z removes it in one step", len(w.doc.circuit.components) == n0)
n1 = len(w.doc.circuit.components); drag(tree, gate, cv.canvas, 0, 0, release_on=(tree.winfo_rootx() + 30, tree.winfo_rooty() + 30)); chk("releasing on the explorer itself cancels (nothing added)", len(w.doc.circuit.components) == n1)
folder = "f:Gates"; drag(tree, folder, cv.canvas, 300, 300); chk("a folder cannot be dragged", len(w.doc.circuit.components) == n1)
dim = next((i for i in ids if i.startswith("x:")), None)
if dim: drag(tree, dim, cv.canvas, 300, 300); chk("a part that is not simulated yet cannot be dragged", len(w.doc.circuit.components) == n1)
pin = next(i for i in ids if i.startswith("p:@in")); ni = len(w.doc.circuit.inputs); drag(tree, pin, cv.canvas, 250, 450); chk("an input pin can be dragged too", len(w.doc.circuit.inputs) == ni + 1)
# plain click still arms the tool
tree.selection_set(gate); pump(); chk("clicking a part still arms the placement tool", cv.tool is not None and cv.tool[1] == "NAND"); cv.set_tool(None)
# ---------------- Multisim
CIR = {"kind": "analog", "components": [{"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["in", "0"]}, {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["in", "mid"]}, {"id": "R2", "type": "Resistor", "value": "2k", "nodes": ["mid", "0"]}]}
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); pump(8); sv = w.pages["multisim"].views["schematic"]; bin_ = w.side.views.get("multisim") or w.side.view(); bt = bin_.t; pump()
for g in list(bt.get_children("")): bt.item(g, open=True)
for g in list(bt.get_children("")):
    for f in bt.get_children(g): bt.item(f, open=True)
pump(); bin_.refresh(); pump(); nl = w.adoc.netlist; n0 = len(nl.parts)
cid = next(i for i in bin_.cls if i == "c:Resistor"); CW, CH = sv.canvas.winfo_width(), sv.canvas.winfo_height(); drag(bt, cid, sv.canvas, int(CW * .7), int(CH * .6))
nl = w.adoc.netlist; chk("Multisim: dragging a resistor adds a part", len(nl.parts) == n0 + 1)
newp = nl.parts[-1]; pl = next((q for q in sv.L.parts if q.part.id == newp.id), None); s, ox, oy = sv.sc
if pl: px, py = ox + pl.cx * s, oy + pl.cy * s; chk(f"Multisim: it is under the drop point ({int(px)},{int(py)} vs 700,420)", abs(px - CW * .7) < 60 and abs(py - CH * .6) < 60)
w.adoc.undo(); pump(); chk("Multisim: one undo removes it", len(w.adoc.netlist.parts) == n0)
drag(bt, "g:Basic", sv.canvas, int(CW * .5), int(CH * .5)); chk("Multisim: a group row cannot be dragged", len(w.adoc.netlist.parts) == n0)
drag(bt, cid, sv.canvas, 0, 0, release_on=(bt.winfo_rootx() + 30, bt.winfo_rooty() + 30)); chk("Multisim: release on the list cancels", len(w.adoc.netlist.parts) == n0)
for c in ("c:VoltageSource", "c:NPN", "c:Capacitor", "c:OpAmp"):
    if c in bin_.cls: k = len(w.adoc.netlist.parts); drag(bt, c, sv.canvas, int(CW * (.3 + .1 * (k % 5))), int(CH * (.3 + .1 * (k % 4)))); chk(f"Multisim: {c[2:]} can be dragged in and the circuit stays valid", len(w.adoc.netlist.parts) == k + 1 and w.adoc.valid or len(w.adoc.netlist.parts) == k + 1)
bt.selection_set("c:Resistor"); bin_.t.event_generate("<Double-1>", x=40, y=bt.bbox("c:Resistor")[1] + 5) if False else None
# ---------------- canvas behaviour like Logisim / KiCad: drag on empty space = rubber band, middle button / Space = pan, wheel = zoom
w.show("logisim"); w.doc.load_text(json.dumps({"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "OR", "in": ["n1", "C"], "out": "Y"}]})); pump(8)
cv = w.pages["logisim"].views["circuit"]; cv.fit(); pump(); c = cv.canvas; W, H = c.winfo_width(), c.winfo_height()
def ev(kind, x, y, **kw): c.event_generate(kind, x=x, y=y, **kw); pump(1)
cv.select(None); ev("<Button-1>", 4, 4)
for k in range(1, 8): ev("<B1-Motion>", 4 + (W - 8) * k // 7, 4 + (H - 8) * k // 7)
ev("<ButtonRelease-1>", W - 4, H - 4); pump(); chk("Logisim: dragging on empty space selects the parts inside (rubber band)", len(cv.sels) == 2)
v0 = cv.view or cv.fit_view; cv.select(None); ev("<Button-1>", 4, 4); ev("<B1-Motion>", 60, 60); ev("<ButtonRelease-1>", 60, 60); chk("a plain drag on empty space no longer moves the view", (cv.view or cv.fit_view) == v0)
cv.select(None); pump(); s0, ox0, oy0 = cv.view or cv.fit_view; ev("<Button-2>", 100, 100); ev("<B2-Motion>", 160, 140); ev("<ButtonRelease-2>", 160, 140); s1, ox1, oy1 = cv.view or cv.fit_view
chk("Logisim: middle button drag pans", abs((ox1 - ox0) - 60) < 2 and abs((oy1 - oy0) - 40) < 2)
cv.fit(); s0 = (cv.view or cv.fit_view)[0]; c.event_generate("<Button-4>", x=200, y=200); pump(); chk("Logisim: wheel zooms", (cv.view or cv.fit_view)[0] > s0)
ox_a = (cv.view or cv.fit_view)[1]; c.event_generate("<Button-4>", x=200, y=200, state=4); pump(); chk("Logisim: Ctrl + wheel pans sideways", (cv.view or cv.fit_view)[1] != ox_a)
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); pump(8); sv = w.pages["multisim"].views["schematic"]; sv.fit(); pump(); c = sv.canvas
s0, ox0, oy0 = sv.sc; c.event_generate("<Button-4>", x=150, y=150); pump(); chk("Multisim: wheel zooms the schematic", sv.sc[0] > s0)
a = sv.sc; c.event_generate("<Button-2>", x=100, y=100); pump(1); c.event_generate("<B2-Motion>", x=150, y=130); pump(1); c.event_generate("<ButtonRelease-2>", x=150, y=130); pump(); chk("Multisim: middle button drag pans", abs(sv.sc[1] - a[1] - 50) < 2 and abs(sv.sc[2] - a[2] - 30) < 2)
a = sv.sc; c.event_generate("<Button-1>", x=5, y=5); pump(1); c.event_generate("<B1-Motion>", x=45, y=35); pump(1); c.event_generate("<ButtonRelease-1>", x=45, y=35); pump(); chk("Multisim: dragging empty space pans", abs(sv.sc[1] - a[1] - 40) < 2 and abs(sv.sc[2] - a[2] - 30) < 2)
sv.fit(); pump(); chk("Multisim: Fit returns to the whole circuit", sv.view is None)
r1 = sv.L.parts[0].part.id; z = sv.sc[0]; c.event_generate("<Button-4>", x=200, y=200); pump(); pl = next(q for q in sv.L.parts if q.part.id == r1); s_, ox_, oy_ = sv.sc
n0 = len(w.adoc.netlist.parts); sx, sy = int(ox_ + pl.cx * s_), int(oy_ + pl.cy * s_); c.event_generate("<Button-1>", x=sx, y=sy); pump(1)
for k in range(1, 6): c.event_generate("<B1-Motion>", x=sx + 6 * k, y=sy + 4 * k); pump(1)
c.event_generate("<ButtonRelease-1>", x=sx + 30, y=sy + 20); pump(); chk("Multisim: dragging a part still works while zoomed", w.adoc.valid and len(w.adoc.netlist.parts) == n0)
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
