import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.core import commands as C
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.logisim.memory_editor import to_text, from_text, MemoryEditor
from vibesimulation.ui.logisim.parts_palette import PropsDialog
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
d = w.doc; ctx.say = lambda t, m, *a, **k: print("SAY", t, m)
d.load_text(""); w.show("logisim"); root.update(); v = w.pages["logisim"].views["circuit"]
v.run(C.AddComponent("ROM", {"addr": 4, "width": 8}, pos=(200, 100))); root.update()
v.run(C.SetAttrs("g1", {"contents": {0: 0x12, 1: 0xAB, 9: 7}})); root.update()
print(d.text); print(d.valid, d.errors)
t = to_text(d.circuit.component("g1").attrs["contents"], 4, 8); print(t)
assert from_text(t, 4, 8) == {0: 0x12, 1: 0xAB, 9: 7}
assert from_text("0: 3*5 7", 4, 8) == {0: 5, 1: 5, 2: 5, 3: 7}
for bad in ("20: 1", "0: 1FF"):
    try: from_text(bad, 4, 8); print("FAIL accepted", bad)
    except ValueError as e: print("ok rejects", bad, "->", e)
dlg = PropsDialog(ctx, d.circuit.component("g1")); root.update(); os.system("import -display :97 -window root /tmp/pv/rom.png"); dlg.destroy()
ed = MemoryEditor(ctx, "Contents", {0: 1}, 4, 8); root.update(); ed.txt.insert("end", "\nA: FF"); ed.ok(); print("editor result", ed.result)
os.system("import -display :97 -window root /tmp/pv/rom2.png")
ctx.cfg.clear(); ctx.save_cfg(); print("OK")
