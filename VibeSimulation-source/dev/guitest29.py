import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import json, tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.core import commands as C
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
d.load_text('{"inputs":["a","b"],"outputs":["s","c"],"gates":[{"id":"x","type":"XOR","in":["a","b"],"out":"s"},{"id":"n","type":"AND","in":["a","b"],"out":"c"}]}')
w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]
d.rename_circuit("main", "half"); root.update()
print(d.add_circuit("main"), d.cur); root.update()
d.set_text('{"inputs":["A","B","Cin"],"outputs":[],"gates":[]}'); root.update()
v.run(C.AddComponent("Circuit", {"circuit": "half"}, pos=(200, 100))); root.update()
print(d.valid, d.errors, d.layout_error, d.text)
v.run(C.AddComponent("Circuit", {"circuit": "half"}, pos=(400, 200), facing="east")); root.update()
print(d.valid, d.errors, d.layout_error)
print(d.text)
os.system("import -display :97 -window root /tmp/pv/sub1.png")
# rotate an instance
cid = d.circuit.components[0].id
v.run(C.RotatePart(cid, 1)); print("rot", d.valid, d.layout_error); root.update()
v.run(C.RotatePart(cid, 1)); print("rot", d.valid, d.layout_error); root.update()
os.system("import -display :97 -window root /tmp/pv/sub2.png")
# double click opens inside
d.switch("half"); root.update(); print(d.cur, d.valid)
d.switch("main"); print(d.cur, d.valid)
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
