import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.analog import components as AC
root = tk.Tk(); root.geometry("1400x850"); w = MainWindow(root); ctx = w.ctx
ok = True
def chk(name, c):
    global ok; print(("ok  " if c else "FAIL"), name); ok = ok and bool(c)
CIR = {"title": "t", "components": [
 {"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["n1", "0"]},
 {"id": "S1", "type": "Switch", "state": "closed", "nodes": ["n1", "n2"]},
 {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["n2", "n3"]},
 {"id": "Z1", "type": "Zener", "vz": "5.1", "nodes": ["0", "n3"]},
 {"id": "A1", "type": "Ammeter", "nodes": ["n3", "n4"]},
 {"id": "R2", "type": "Resistor", "value": "2k", "nodes": ["n4", "0"]},
 {"id": "E1", "type": "VCVS", "value": "2", "control": ["n3", "0"], "nodes": ["n5", "0"]},
 {"id": "R3", "type": "Resistor", "value": "1k", "nodes": ["n5", "0"]}]}
w.adoc.load_text(json.dumps(CIR)); w.show("multisim"); root.update()
d = w.adoc; chk("valid", d.valid and not d.errors)
sv = w.pages["multisim"].views["schematic"]; rv = w.pages["multisim"].views["results"]; root.update()
chk("zener clamps n3 ~5.1", abs(d.volts["n3"] - 5.1) < 0.2)
chk("vcvs 2x", abs(d.volts["n5"] - 2 * d.volts["n3"]) < 1e-6)
# click-toggle the switch
pl = next(p for p in sv.L.parts if p.part.id == "S1"); s, ox, oy = sv.sc
x, y = ox + pl.cx * s, oy + pl.cy * s
sv.canvas.event_generate("<Button-1>", x=int(x), y=int(y)); root.update(); sv.canvas.event_generate("<ButtonRelease-1>", x=int(x), y=int(y)); root.update()
chk("switch opened by click", d.netlist.part("S1").extra["state"] == "open")
chk("open switch: n3 ~0", abs(d.volts["n3"]) < 1e-3)
d.undo(); root.update(); chk("undo closes switch", d.netlist.part("S1").is_closed())
# add every part type through the menu code
for cls in AC.part_types():
    n0 = len(d.netlist.parts); sv.add(cls); root.update()
    chk(f"add {cls.type_name}", len(d.netlist.parts) == n0 + 1 and not d.errors or print(d.errors))
    if len(d.netlist.parts) != n0 + 1: d.undo()
# analysis panel
rv.set_mode("an"); root.update(); pn = rv.panel
d.load_text(json.dumps(CIR)); root.update(); pn.refresh()
pn.part.set("V1"); pn.a.set("0"); pn.b.set("10"); pn.n.set("11"); pn.run(); root.update()
chk("sweep ran", pn.data and len(pn.data["x"]) == 11)
chk("sweep saved in JSON", '"analysis"' in d.text and '"sweep"' in d.text)
pn.probes.selection_clear(0, "end"); pn.probes.selection_set(0); pn.plot(); root.update(); print(pn.canvas.winfo_width(), pn.canvas.winfo_height(), len(pn.series()))
chk("plot has lines", len(pn.canvas.find_all()) > 10)
os.system("import -display :97 -window root /tmp/pv/ms32an.png 2>/dev/null")
LIN = dict(CIR); LIN["components"] = [c for c in CIR["components"] if c["id"] != "Z1"]; d.load_text(json.dumps(LIN)); root.update(); pn.refresh(); rv.set_mode("th"); root.update(); pn.load.set("R2"); pn.thevenin(); root.update(); print(pn.res.cget("text"))
chk("thevenin text", "Vth" in pn.res.cget("text"))
d.undo(); root.update()
rv.set_mode("op"); root.update(); chk("op mode shows rows", len(rv.rows) > 5)
os.system("import -display :97 -window root /tmp/pv/ms32.png 2>/dev/null")
ctx.cfg.clear(); ctx.save_cfg()
print("ALL OK" if ok else "SOME FAILED")
