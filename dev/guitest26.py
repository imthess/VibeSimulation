import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import json, tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.core import commands as C
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
d.load_text(""); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]; root.update()
# build a 3-bit counter with a clock from the circuit view
v.run(C.AddComponent("Clock", pos=(100, 100)))
v.run(C.AddComponent("Counter", {"width": 3}, pos=(300, 100)))
print(d.text); print(d.valid, d.layout_error, d.errors)
os.system("import -display :97 -window root /tmp/pv/seq0.png")
print("sim buttons shown", v.simbar.winfo_ismapped())
for i in range(6): d.tick(1)
root.update(); print("tick", d.tick_n, d.vals); os.system("import -display :97 -window root /tmp/pv/seq1.png")
cv = v.canvas; cv.focus_force(); root.update(); cv.event_generate("<Control-Key-t>"); root.update(); print("after ctrl+T", d.tick_n)
v.toggle_auto(); root.update(); root.after(1200, root.quit); root.mainloop(); print("auto ticks", d.tick_n); v.toggle_auto()
v.reset_sim(); print("reset", d.tick_n, d.vals)
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
