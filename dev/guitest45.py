"""Multisim 'Show results for': choose parts / nets, every analysis follows (DC table, phasors, probe lists, noise)."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=4):
    for _ in range(n): root.update(); time.sleep(0.02)
CIR = {"kind": "analog", "components": [
    {"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["in", "0"]},
    {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["in", "mid"]},
    {"id": "R2", "type": "Resistor", "value": "2k", "nodes": ["mid", "0"]},
    {"id": "C1", "type": "Capacitor", "value": "100n", "nodes": ["mid", "0"]}]}
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); pump(); d = w.adoc
rv = w.pages["multisim"].views["results"]; fo = rv.focus
chk("circuit valid", d.valid)
rows = lambda: [rv.tree.item(i, "values")[0] for i in rv.tree.get_children()]
all_rows = rows(); chk("without a choice, every part and net is listed", any(r.startswith("R1") for r in all_rows) and any(r.startswith("R2") for r in all_rows) and "in" in all_rows)
fo.set({"R2"}, set()); pump()
r = rows(); chk("choosing R2 lists only R2 (and its nets mid / ground-side)", any(x.startswith("R2") for x in r) and not any(x.startswith("R1") for x in r) and not any(x.startswith("C1") for x in r) and "mid" in r and "in" not in r)
vals = [rv.tree.item(i, "values") for i in rv.tree.get_children() if rv.tree.item(i, "values")[0].startswith("R2")][0]
chk("R2 row shows 6.667 V and 3.333 mA", "6.66" in vals[1] and "3.33" in vals[2])
chk("status says what is shown", "R2" in rv.status.cget("text"))
chk("button label follows", "R2" in rv.picker.btn.text)
fo.set(set(), {"in"}); pump(); r = rows(); chk("choosing only a net shows that net and no parts", "in" in r and "mid" not in r and not any(x.startswith("R") for x in r))
fo.clear(); pump(); chk("clearing shows everything again", any(x.startswith("R1") for x in rows()))
# probe lists
fo.set({"R1"}, set())
for mode, attr in (("bo", "probes"), ("tr", "probes")):
    rv.set_mode(mode); pump(); lb = rv.panels[mode].probes; names = list(lb.get(0, "end"))
    chk(f"{mode}: probe list limited to R1 and its nets", "I(R1)" in names and "I(R2)" not in names and "V(in)" in names and "V(mid)" in names)
    chk(f"{mode}: those probes are selected", {lb.get(i) for i in lb.curselection()} >= {"I(R1)"})
fo.set({"R2"}, set()); pump(); lb = rv.panels["tr"].probes if rv.mode == "tr" else None
chk("changing the choice re-filters the open analysis", lb is not None and "I(R2)" in lb.get(0, "end") and "I(R1)" not in lb.get(0, "end"))
rv.set_mode("an"); pump(); pl = rv.panels["an"].probes; chk("DC sweep probe list follows", "I(R2)" in pl.get(0, "end") and "I(R1)" not in pl.get(0, "end"))
rv.set_mode("ph"); pump(); ph = rv.panels["ph"]; ph.vars["f"].set("1k"); ph.run(); pump()
names = [ph.tree.item(i, "values")[0] for i in ph.tree.get_children()]; chk("phasor table limited to R2", "R2" in names and "R1" not in names and "C1" not in names)
fo.set({"R1"}, set()); pump(); names = [ph.tree.item(i, "values")[0] for i in ph.tree.get_children()]; chk("phasor table re-filters without re-solving", "R1" in names and "R2" not in names)
fo.clear(); pump(); names = [ph.tree.item(i, "values")[0] for i in ph.tree.get_children()]; chk("phasor: all again", {"R1", "R2", "C1"} <= set(names))
rv.set_mode("mc"); pump(); fo.set({"C1"}, set()); pump(); chk("Monte Carlo probes follow", "I(C1)" in rv.panels["mc"].probes.get(0, "end") and "I(R1)" not in rv.panels["mc"].probes.get(0, "end"))
rv.set_mode("op"); fo.clear(); pump()
# stale choice after the part is removed
fo.set({"R2"}, set()); d.load_text(json.dumps({"kind": "analog", "components": [CIR["components"][0], dict(CIR["components"][1], nodes=["in", "0"])]})); pump(); chk("a removed part drops out of the choice", "R2" not in fo.parts)
# picker popup
rv.picker.toggle(); pump(); chk("popup opens with parts and nets", rv.picker.pop is not None and rv.picker.lp.size() == 2 and rv.picker.ln.size() >= 1)
rv.picker.lp.selection_set(0); rv.picker.lp.event_generate("<<ListboxSelect>>"); pump(); chk("clicking a part in the popup applies it", fo.parts == {"V1"} or len(fo.parts) == 1)
rv.picker.everything(); pump(); chk("'Show everything' clears", not fo.active); rv.picker.close(); pump()
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
