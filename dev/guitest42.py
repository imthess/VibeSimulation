"""Instrument windows and the four new analysis panels in the real window."""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.multisim.instruments import open_instrument, FunctionGenerator, Oscilloscope, Multimeter
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=6):
    for _ in range(n): root.update(); time.sleep(0.02)
w.ctx.toaster.show = lambda *a, **k: None; w.ctx.say = lambda *a, **k: None
w.show("multisim"); pump()
doc = w.adoc
doc.load_text(json.dumps({"components": [{"id": "V1", "type": "V", "value": 1, "ac": 1, "freq": 1000, "nodes": ["in", "0"]}, {"id": "R1", "type": "R", "value": "1k", "tol": 5, "nodes": ["in", "o"]}, {"id": "R2", "type": "R", "value": "1k", "tol": 5, "tc1": "0.004", "nodes": ["o", "0"]}]})); pump()
rv = w.pages["multisim"].views["results"]; st = {}
# ---- analysis panels
for key in ("ps", "ts", "mc", "no"):
    rv.set_mode(key); pump(); p = rv.panels[key]; chk(f"{key}: panel shown", p.winfo_ismapped())
p = rv.panels["ps"]; rv.set_mode("ps"); pump()
p.vars["part"].set("R2"); p.vars["param"].set("value"); p.vars["from"].set("100"); p.vars["to"].set("10k"); p.vars["n"].set("9"); pump()
p.probes.selection_clear(0, "end"); p.probes.selection_set(list(p.probes.get(0, "end")).index("V(o)")); p.run(); pump()
chk("parameter sweep ran", p.data and len(p.data["x"]) == 9 and abs(p.data["series"]["V(o)"][0] - 1 * 100 / 1100) < 1e-9 * 1e3)
chk("sweep saved in the JSON", "psweep" in doc.netlist.analysis)
p = rv.panels["ts"]; rv.set_mode("ts"); pump(); p.probes.selection_clear(0, "end"); p.probes.selection_set(list(p.probes.get(0, "end")).index("V(o)")); p.vars["kind"].set("dc"); p.run(); pump()
chk("temperature sweep ran, tc1 moves the divider", p.data and p.data["series"]["V(o)"][0] != p.data["series"]["V(o)"][-1])
p = rv.panels["mc"]; rv.set_mode("mc"); pump(); p.probes.selection_clear(0, "end"); p.probes.selection_set(list(p.probes.get(0, "end")).index("V(o)")); p.vars["runs"].set("100"); p.vars["kind"].set("dc"); p.run(); pump()
chk("Monte Carlo ran with a table", p.data and len(p.tree.get_children()) == 1 and p.data["stats"]["V(o)"]["std"] > 0)
p = rv.panels["no"]; rv.set_mode("no"); pump(); p.vars["out"].set("o"); p.run(); pump()
chk("noise ran", p.data and p.data["total_rms"] > 0 and len(p.tree.get_children()) == 2)
p.vars["out"].set("nope"); p.run(); chk("bad net explained, no crash", "nope" in w_status if (w_status := rv.status.cget("text")) else False)
# ---- instruments
store = {}
fg = open_instrument(w.ctx, doc, "Function generator", store); pump(); chk("generator lists the source", fg.get("src") == "V1")
fg.vars["wave"].set("square"); fg.vars["duty"].set("0.25"); fg.vars["freq"].set("2k"); fg.vars["ac"].set("3"); fg.apply(); pump()
q = doc.netlist.part("V1"); chk("generator edits the source", q.extra["wave"] == "square" and q.extra["duty"] == "0.25" and q.extra["freq"] == "2k" and q.extra["ac"] == "3")
fg.vars["duty"].set("1.5"); fg.apply(); chk("bad duty rejected", doc.netlist.part("V1").extra["duty"] == "0.25")
chk("same window is reused", open_instrument(w.ctx, doc, "Function generator", store) is fg)
sc = open_instrument(w.ctx, doc, "Oscilloscope", store); pump()
sc.vars["p0"].set("V(in)"); sc.vars["p1"].set("V(o)"); sc.vars["tdiv"].set("50u"); sc.vars["delay"].set("2m"); sc.run(); pump()
chk("scope triggered and measured", sc.data and sc.data["triggered"] and abs(sc.data["channels"][0]["read"]["vpp"] - 6) < 0.1)
chk("scope drew the traces", len(sc.screen.find_all()) >= 25)
sc.vars["tsrc"].set("C"); sc.run(); chk("trigger on an unused channel explained", "no probe" in sc.reads.cget("text"))
dm = open_instrument(w.ctx, doc, "Multimeter", store); pump()
dm.vars["mode"].set("vdc"); dm.vars["a"].set("o"); dm.read(); chk("meter reads", dm.lcd.cget("text") != "----")
dm.vars["mode"].set("ohm"); dm.vars["a"].set("o"); dm.vars["b"].set("0"); dm.read(); chk("ohm reading", dm.lcd.cget("text").startswith("500"))
dm.vars["mode"].set("vac"); dm.vars["a"].set("in"); dm.read(); chk("AC RMS reading", dm.lcd.cget("text").startswith("2.12"))
doc.edit(lambda nl: setattr(nl.part("R1"), "value", "3k")); pump()
dm.vars["mode"].set("vdc"); dm.vars["a"].set("o"); dm.read(); chk("meter follows circuit edits", dm.lcd.cget("text") != "----")
# ---- menus
m = tk.Menu(root); from vibesimulation.ui import menus; menus.tools_multisim(w, m)
labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
chk("Tools menu lists the instruments", all(any(n in l for l in labels) for n in ("Function generator", "Oscilloscope", "Multimeter")))
for win in list(store.values()): win.close()
pump(); print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
