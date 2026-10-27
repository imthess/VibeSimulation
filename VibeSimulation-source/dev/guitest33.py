import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x1000"); w = MainWindow(root); ctx = w.ctx
ok = True
def chk(name, c):
    global ok; print(("ok  " if c else "FAIL"), name); ok = ok and bool(c)
CIR = {"title": "RLC", "components": [
 {"id": "V1", "type": "VoltageSource", "value": "0", "ac": "1", "freq": "1.5915k", "nodes": ["in", "0"]},
 {"id": "L1", "type": "Inductor", "value": "10m", "nodes": ["in", "a"]},
 {"id": "C1", "type": "Capacitor", "value": "1u", "nodes": ["a", "out"]},
 {"id": "R1", "type": "Resistor", "value": "10", "nodes": ["out", "0"]}]}
w.adoc.load_text(json.dumps(CIR)); w.show("multisim"); root.update()
d = w.adoc; chk("valid", d.valid and not d.errors)
sv = w.pages["multisim"].views["schematic"]; rv = w.pages["multisim"].views["results"]; root.update()
# source edit through the form (monkeypatch the dialog)
ctx.ask_form = lambda title, msg, fields, check=None: {"value": "2", "ac": "3", "freq": "60", "phase": "20", "wave": "square"}
sv.source(d.netlist.part("V1")); root.update()
p = d.netlist.part("V1"); chk("source form applied", p.number() == 2 and p.ac_amp() == 3 and p.extra["wave"] == "square" and p.freq() == 60)
d.undo(); root.update(); chk("undo", d.netlist.part("V1").ac_amp() == 1)
# every mode shows
for m in ("an", "ph", "bo", "tr", "th", "op"):
    rv.set_mode(m); root.update(); chk(f"mode {m}", rv.mode == m)
# Bode
rv.set_mode("bo"); root.update(); b = rv.panels["bo"]; b.vars["from"].set("100"); b.vars["to"].set("10k"); b.vars["points"].set("121"); b.run(); root.update()
chk("bode ran", b.data and len(b.data["f"]) == 121); chk("bode saved in json", '"ac"' in d.text)
chk("bode plots drawn", len(b.pm.find_all()) > 10 and len(b.pp.find_all()) > 10); print(b.note.cget("text"))
chk("bode text: band-pass Q 10", "band-pass" in b.note.cget("text") and "Q = 9.9" in b.note.cget("text") or "Q = 10" in b.note.cget("text"))
os.system("import -display :97 -window root /tmp/pv/ms33bode.png 2>/dev/null")
# phasors
rv.set_mode("ph"); root.update(); ph = rv.panels["ph"]; ph.run(); root.update(); print(ph.res.cget("text"))
chk("phasor rows", len(ph.tree.get_children()) >= 8); chk("power text", "power factor 1" in ph.res.cget("text"))
kids = ph.tree.get_children(); ph.tree.selection_set(kids[1:4]); root.update(); ph.plot(); chk("diagram drawn", len(ph.dia.find_all()) > 5)
os.system("import -display :97 -window root /tmp/pv/ms33ph.png 2>/dev/null")
# transient
rv.set_mode("tr"); root.update(); t = rv.panels["tr"]; t.vars["stop"].set("5m"); t.vars["steps"].set("2000"); t.run(); root.update()
chk("tran ran", t.data and len(t.data["t"]) == 2001); chk("tran saved", '"tran"' in d.text); chk("tran plot", len(t.pl.find_all()) > 20); print(t.note.cget("text"))
os.system("import -display :97 -window root /tmp/pv/ms33tr.png 2>/dev/null")
# switching the circuit refreshes lists
w.adoc.load_text(json.dumps(CIR)); root.update(); chk("probes after reload", t.probes.size() > 3)
rv.set_mode("op"); root.update(); chk("op rows", len(rv.rows) > 5)
ctx.cfg.clear(); ctx.save_cfg()
print("ALL OK" if ok else "SOME FAILED")
