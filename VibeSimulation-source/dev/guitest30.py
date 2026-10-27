import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import json, tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
j = {"inputs": [{"name": "A", "width": 4}], "outputs": [{"name": "q", "width": 8}], "gates": [
 {"id": "r", "type": "RAM", "addr": 4, "asyncread": True, "in": {"A": "A"}, "out": {"Dout": "q"}}]}
d.load_text(json.dumps(j)); w.show("logisim"); root.update()
print(d.valid, d.errors, d.layout_error)
d.set_memory("r", {3: 77, 5: 9}); d.set_input("A", 3); root.update(); print(d.vals["q"])
d.set_input("A", 5); print(d.vals["q"]); d.reset_sim(); print(d.vals["q"])
os.system("import -display :97 -window root /tmp/pv/ram1.png")
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
