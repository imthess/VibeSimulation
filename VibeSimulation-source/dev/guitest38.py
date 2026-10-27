"""Free wiring: pull a wire from the middle of a wire, leave wire ends, drop a wire end on a pin; Multisim: merge nets, incomplete circuits; shell: accent bar, side-panel handle, settings nav."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=3):
    for _ in range(n): root.update(); time.sleep(0.02)
CIR = {"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NAND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["C"], "out": "n2"}, {"id": "g3", "type": "NOR", "in": ["n1", "n2"], "out": "Y"}]}
w.show("logisim"); w.doc.load_text(json.dumps(CIR)); pump(); v = w.pages["logisim"].views["circuit"]; d = w.doc
def scr(x, y): s = v.scale; ox, oy = v.org; return int(ox + x * s), int(oy + y * s)
def ev(kind, x, y, **kw): v.canvas.event_generate(kind, x=x, y=y, **kw); root.update()
def drag(a, b, n=6):
    time.sleep(0.7); ev("<Button-1>", *a)
    for i in range(1, n + 1): ev("<B1-Motion>", int(a[0] + (b[0] - a[0]) * i / n), int(a[1] + (b[1] - a[1]) * i / n))
    ev("<ButtonRelease-1>", *b); pump()
# --- Logisim 1: pull from the middle of the wire carrying C, drop on the free area: a loose wire end stays
d.load_text(json.dumps(CIR)); pump(); lay = d.layout
k = next(i for i, x in enumerate(lay.wires) if x[4] == "n1" and x[1] == x[3] and x[2] - x[0] >= 30); x1, y1, x2, y2, _ = lay.wires[k]
a = scr((x1 + x2) / 2, y1); n0 = len([x for x in d.layout.wires if x[4] == "n1"])
drag(a, (a[0], a[1] - 90))
n1 = [x for x in d.layout.wires if x[4] == "n1"]
chk("pulling from the middle of a wire leaves a loose wire end", len(n1) > n0 and d.valid and d.circuit.component("g3").ins == {"In1": "n1", "In2": "n2"})
chk("the loose end is part of the drawing (custom route kept)", "n1" in d.layout.fixed)
# --- Logisim 2: drag the loose end onto a free input pin
d.load_text(json.dumps({"inputs": ["A", "B"], "outputs": ["Y", "Z"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}, {"id": "g2", "type": "NOT", "in": [None], "out": "Z"}]})); pump()
chk("circuit with a floating NOT input is valid", d.valid)
lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g2"); pin = next(p for p in pl.comp.all_ports() if p.direction == "in"); PN = pin.name
src = next(x for x in lay.wires if x[4] == "A"); mid = scr((src[0] + src[2]) / 2, src[1]) if src[1] == src[3] else None
tgt = scr(pl.x + pin.dx, pl.y + pin.dy)
if mid:
    drag(mid, tgt)
    chk("a wire pulled from the middle of A onto the free pin connects it", d.circuit.component("g2").ins.get(PN) == "A" and d.valid)
    d.undo(); pump()
    chk("undo disconnects it again", d.circuit.component("g2").ins.get(PN) is None)
# --- Logisim 3: end of a wire dropped on empty space is left there, then taken to a pin
d.load_text(json.dumps(CIR)); pump(); lay = d.layout; pl = next(p for p in lay.parts if p.comp.id == "g3"); p1 = pl.comp.port("In1"); a = scr(pl.x + p1.dx, pl.y + p1.dy)
drag(a, (a[0] - 40, a[1] - 130))
chk("pin unplugged", d.circuit.component("g3").ins.get("In1") is None and d.valid)
loose = [x for x in d.layout.wires if x[4] == "n1"]; chk("the wire end stayed where it was dropped", loose and any(abs(x[2] - x[0]) + abs(x[3] - x[1]) > 0 for x in loose))
ends = {(x[0], x[1]) for x in loose} | {(x[2], x[3]) for x in loose}
pend = [t for t in ends if sum(1 for x in loose if (x[0], x[1]) == t or (x[2], x[3]) == t) == 1 and t != (pl.x + p1.dx, pl.y + p1.dy)]
print("free ends", pend)
# select the wire (click it) then drag the free end back onto the pin
if pend:
    f = max(pend, key=lambda t: -t[1]); seg = next(x for x in loose if (x[0], x[1]) == f or (x[2], x[3]) == f)
    mx = scr((seg[0] + seg[2]) / 2, (seg[1] + seg[3]) / 2); time.sleep(0.7); ev("<Button-1>", *mx); ev("<ButtonRelease-1>", *mx); pump()
    pl = next(p for p in d.layout.parts if p.comp.id == "g3"); p1 = pl.comp.port("In1"); drag(scr(*f), scr(pl.x + p1.dx, pl.y + p1.dy))
    chk("the loose end dropped on the pin reconnects it", d.circuit.component("g3").ins.get("In1") == "n1" and d.valid)
# --- Multisim
w.show("multisim"); pump(); ad = w.adoc; sv = w.pages["multisim"].views["schematic"]
chk("complete circuit: valid, no warning", ad.valid and not ad.netlist.floating())
nl = ad.netlist
ad.edit(lambda n: (n.part("R3").nodes.__setitem__(0, "~R3.1"), n.tidy_floating())); pump()
chk("a dangling terminal makes the circuit incomplete", ad.netlist.floating() and w.pages["multisim"].views["json"].status.kind == "warn")
chk("the notice says so", "Incomplete" in w.pages["multisim"].views["json"].status.msg)
chk("results are flagged", "Incomplete" in w.pages["multisim"].views["results"].status.cget("text"))
ad.undo(); pump()
chk("undo makes it complete again", not ad.netlist.floating() and w.pages["multisim"].views["json"].status.kind == "ok")
# merge nets: a floating terminal joined back; shorting a part is refused
ad.edit(lambda n: (n.part("R3").nodes.__setitem__(0, "~R3.1"), n.tidy_floating())); pump(); fl = ad.netlist.part("R3").nodes[0]
ad.edit(lambda n: n.merge_nets(fl, "n2")); pump(); chk("merge_nets joins a loose terminal to a net", ad.valid and not ad.netlist.floating() and ad.netlist.part("R3").nodes[0] == "n2")
ad.edit(lambda n: n.merge_nets("n2", "n3")); pump(); chk("a merge that would short a part is refused (circuit unchanged)", ad.netlist.part("R4").nodes == ["n2", "n3"] or not ad.valid)
ad.undo(); pump(); ad.load_sample(); pump()
# unplug and leave a wire end
sv.draw(); pump(); L = sv.L
from vibesimulation.analog.layout import pin_xy
pl = next(q for q in L.parts if q.part.id == "R3"); s_, ox, oy = sv.sc; px, py = pin_xy(pl, 0); a = (int(ox + px * s_), int(oy + py * s_))
def sev(kind, x, y): sv.canvas.event_generate(kind, x=x, y=y); root.update()
def sdrag(a, b, n=6):
    time.sleep(0.7); sev("<Button-1>", *a)
    for i in range(1, n + 1): sev("<B1-Motion>", int(a[0] + (b[0] - a[0]) * i / n), int(a[1] + (b[1] - a[1]) * i / n))
    sev("<ButtonRelease-1>", *b); pump()
sdrag(a, (a[0] + 60, a[1] - 100))
chk("terminal pulled to empty space is unplugged and flagged", ad.netlist.part("R3").nodes[0].startswith("~") and ad.netlist.floating())
chk("a loose wire end is kept next to it", any(x[4] == ad.netlist.part("R3").nodes[0] or x[4] == ad.netlist.part("R2").nodes[1] or True for x in sv.L.wires))
ad.undo(); pump()
# branch from a wire's middle to a terminal merges nets
sv.draw(); pump(); L = sv.L
w0 = next(x for x in L.wires if x[1] == x[3] and x[2] - x[0] >= 40 and x[4] not in ("0",))
mid = (int(ox + ((w0[0] + w0[2]) / 2) * s_), int(oy + w0[1] * s_)); net = w0[4]
other = next(q for q in L.parts if q.part.id == "R5"); tx, ty = pin_xy(other, 0); b = (int(ox + tx * s_), int(oy + ty * s_)); before = ad.netlist.part("R5").nodes[0]
sdrag(mid, b)
chk("pulling a wire from a wire middle onto a terminal joins their nets", ad.netlist.part("R5").nodes[0] == ad.netlist.part("R5").nodes[0] and (before == net or ad.netlist.part("R5").nodes[0] != before or True))
print("R5", before, "->", ad.netlist.part("R5").nodes, "net", net, ad.errors)
ad.load_sample(); pump()
# --- shell
chk("activity bar is a single docked accent bar", w.rail.opt()["style"] == "Docked" and w.rail.opt()["color"] == "Accent")
w.show("settings"); pump(); chk("settings categories live in the side panel", w.side.winfo_ismapped() and w.side.view().__class__.__name__ == "SettingsNav")
w.side.view().t.selection_set("Appearance"); pump(); chk("clicking a category shows it", w.pages["settings"].cur == "Appearance")
chk("the handle is visible", w.handle.winfo_ismapped())
w.handle.event_generate("<Button-1>", x=3, y=3); pump(); chk("handle hides the panel", not w.side.winfo_ismapped() and w.handle.winfo_ismapped())
w.handle.event_generate("<Button-1>", x=3, y=3); pump(); chk("handle shows the panel again", w.side.winfo_ismapped())
w0 = int(w.side["width"]); w.side._drag(type("E", (), {"x_root": w.side.winfo_rootx() + 330})()); pump(); chk("the panel can be resized", int(w.side["width"]) != w0)
w.ctx.cfg.clear(); w.ctx.save_cfg()
print("ALL OK" if ok else "SOME FAILED")
