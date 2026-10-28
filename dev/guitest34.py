import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.analog import components as AC
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ctx = w.ctx
ok = True
def chk(name, c):
    global ok; print(("ok  " if c else "FAIL"), name); ok = ok and bool(c)
CIR = {"title": "CE amplifier + op-amp + MOSFET + transformer", "components": [
 {"id": "Vcc", "type": "VoltageSource", "value": "12", "nodes": ["vcc", "0"]},
 {"id": "Vin", "type": "VoltageSource", "value": "0", "ac": "0.002", "freq": "10k", "nodes": ["in", "0"]},
 {"id": "Cc", "type": "Capacitor", "value": "10u", "nodes": ["in", "b"]},
 {"id": "R1", "type": "Resistor", "value": "47k", "nodes": ["vcc", "b"]}, {"id": "R2", "type": "Resistor", "value": "10k", "nodes": ["b", "0"]},
 {"id": "Re", "type": "Resistor", "value": "1k", "nodes": ["e", "0"]},
 {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "e"]},
 {"id": "Vg", "type": "VoltageSource", "value": "4", "nodes": ["g", "0"]}, {"id": "Rd", "type": "Resistor", "value": "500", "nodes": ["vcc", "d"]},
 {"id": "M1", "type": "NMOS", "nodes": ["d", "g", "0"]},
 {"id": "U1", "type": "OpAmp", "nodes": ["in", "m", "o"]}, {"id": "Rf", "type": "Resistor", "value": "10k", "nodes": ["m", "o"]}, {"id": "Rm", "type": "Resistor", "value": "1k", "nodes": ["m", "0"]},
 {"id": "T1", "type": "Transformer", "value": "100m", "ratio": "2", "nodes": ["vcc", "c", "s", "0"]}, {"id": "RL", "type": "Resistor", "value": "1k", "nodes": ["s", "0"]}]}
w.adoc.load_text(json.dumps(CIR)); w.show("multisim"); root.update()
d = w.adoc; chk("valid", d.valid and not d.errors); print(d.errors, d.layout_error)
sv = w.pages["multisim"].views["schematic"]; rv = w.pages["multisim"].views["results"]; root.update()
chk("layout has multi parts + labels", len([p for p in sv.L.parts if p.part.nterm != 2]) == 4 and len(sv.L.labels) == 3 + 3 + 3 + 4)
os.system("import -display :97 -window root /tmp/pv/ms34a.png 2>/dev/null")
# results rows
rv.set_mode("op"); root.update(); txt = [r[0] for r in rv.rows]; chk("op rows show the region", any("region" in t for t in txt)); print([r for r in rv.rows if "region" in r[0] or "Ic" in r[0]][:3])
# drag the transistor symbol
q = next(p for p in sv.L.parts if p.part.id == "Q1"); s, ox, oy = sv.sc; x, y = ox + q.cx * s, oy + q.cy * s
sv.canvas.event_generate("<Button-1>", x=int(x), y=int(y)); root.update()
for i in range(1, 7): sv.canvas.event_generate("<B1-Motion>", x=int(x + i * 12 * s), y=int(y + i * 6 * s)); root.update()
sv.canvas.event_generate("<ButtonRelease-1>", x=int(x + 72 * s), y=int(y + 36 * s)); root.update()
chk("transistor dragged", d.netlist.part("Q1").pos not in (None, (0, 0)) and d.valid)
d.undo(); root.update()
# join: drag base terminal of Q1 onto a drop terminal of Rm -> nets equal
sv.draw(); root.update()
def tpos(pid, k):
    from vibesimulation.analog.layout import pin_xy
    pl = next(p for p in sv.L.parts if p.part.id == pid); X, Y = pin_xy(pl, k); s, ox, oy = sv.sc; return ox + X * s, oy + Y * s
x0, y0 = tpos("M1", 1); x1, y1 = tpos("Rm", 0)
sv.canvas.event_generate("<Button-1>", x=int(x0), y=int(y0)); root.update()
for t in range(1, 5): sv.canvas.event_generate("<B1-Motion>", x=int(x0 + (x1 - x0) * t / 4), y=int(y0 + (y1 - y0) * t / 4)); root.update()
sv.canvas.event_generate("<ButtonRelease-1>", x=int(x1), y=int(y1)); root.update()
chk("terminal drag: the gate of M1 joined the net of Rm[0]", "is now on net" in sv.status.cget("text") and d.netlist.part("M1").nodes[1] == d.netlist.part("Rm").nodes[0] or print(sv.status.cget("text")))
d.undo(); root.update()
# add each new part via the menu code; edit settings via patched form
for cls in (AC.NPN, AC.PNP, AC.NMOS, AC.PMOS, AC.NJFET, AC.PJFET, AC.OpAmp, AC.Transformer):
    n0 = len(d.netlist.parts); sv.add(cls); root.update(); chk(f"add {cls.type_name}", len(d.netlist.parts) == n0 + 1 and not d.errors and d.valid or print(d.errors, d.layout_error))
ctx.ask_form = lambda title, msg, fields, check=None: {k: ("150" if k == "bf" else v) for k, _, v, _ in fields}
sv.settings(d.netlist.part("Q1")); root.update(); chk("settings form (bf=150)", d.netlist.part("Q1").extra["bf"] == "150")
os.system("import -display :97 -window root /tmp/pv/ms34b.png 2>/dev/null")
# AC / transient modes with transistors
rv.set_mode("ph"); root.update(); ph = rv.panels["ph"]; ph.run(); root.update(); chk("phasor rows include terminal currents", any(".b" in ph.tree.item(i)["values"][0] for i in ph.tree.get_children()))
rv.set_mode("bo"); root.update(); b = rv.panels["bo"]; b.vars["from"].set("100"); b.vars["to"].set("10meg"); b.run(); root.update(); chk("bode with transistors", b.data is not None)
print("probes:", [x for x in b.probes.get(0, "end") if x.startswith("I(Q1")])
rv.set_mode("op"); root.update()
ctx.cfg.clear(); ctx.save_cfg()
print("ALL OK" if ok else "SOME FAILED")
