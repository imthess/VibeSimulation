import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import json, tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
j = {"inputs": ["En"], "outputs": [{"name": "cq", "width": 4}, {"name": "rq", "width": 4}, "q", "qn"], "gates": [
 {"id": "ck", "type": "Clock", "out": "clk"},
 {"id": "c", "type": "Counter", "width": 4, "in": {"Clk": "clk", "En": "En"}, "out": {"Q": "cq"}},
 {"id": "r", "type": "Register", "width": 4, "in": {"D": "cq", "Clk": "clk"}, "out": {"Q": "rq"}},
 {"id": "f", "type": "D Flip-Flop", "in": {"D": "qn", "Clk": "clk"}, "out": {"Q": "q", "Qn": "qn"}}]}
d.load_text(json.dumps(j)); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
print(d.valid, d.errors, d.layout_error)
d.set_input("En", 1)
for i in range(11): d.tick(1)
root.update(); print(d.tick_n, {k: d.vals[k] for k in ("cq", "rq", "q")})
os.system("import -display :97 -window root /tmp/pv/seq2.png")
from vibesimulation.core import commands as C
v.run(C.RotatePart("f", 2)); print("rotated FF", d.valid, d.layout_error); root.update(); os.system("import -display :97 -window root /tmp/pv/seq3.png")
# pdf + circ
from vibesimulation.export.pdf import make_pdf
from vibesimulation.export.logisim import to_circ
print(len(make_pdf(d.layout, d.circuit, d.invals, None, values=d.values())), len(to_circ(d.circuit)))
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
