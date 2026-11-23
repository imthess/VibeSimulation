"""Regenerates the screenshots in docs/images (needs a display, e.g. xvfb-run -a -s "-screen 0 1500x950x24" python3 dev/docshots.py)."""
import sys, os, json, tkinter as tk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from PIL import ImageGrab
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
from vibesimulation.workspaces.logisim.ic.view import open_ic_view
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
W, H = 1360, 860
root = tk.Tk(); root.geometry(f"{W}x{H}+0+0"); w = MainWindow(root)
def snap(name, box=(0, 0, W, H)):
    import time
    for _ in range(8): root.update(); time.sleep(0.15)
    ImageGrab.grab(box).save(os.path.join(OUT, name + ".png")); print("saved", name)
half = {"inputs": ["A", "B"], "outputs": ["S", "C"], "gates": [{"id": "x", "type": "XOR", "in": ["A", "B"], "out": "S"}, {"id": "a", "type": "AND", "in": ["A", "B"], "out": "C"}]}
full = {"inputs": ["A", "B", "Cin"], "outputs": ["Sum", "Cout"], "gates": [
    {"id": "x1", "type": "XOR", "in": ["A", "B"], "out": "p"}, {"id": "x2", "type": "XOR", "in": ["p", "Cin"], "out": "Sum"},
    {"id": "a1", "type": "AND", "in": ["A", "B"], "out": "g"}, {"id": "a2", "type": "AND", "in": ["p", "Cin"], "out": "t"}, {"id": "o1", "type": "OR", "in": ["g", "t"], "out": "Cout"}]}
snap("home")
w.show("logisim"); pg = w.pages["logisim"]; doc = w.doc
doc.load_project(json.dumps({"main": "full adder", "circuits": {"full adder": full, "half adder": half}})); root.update()
pg.strip.open.append("half adder"); pg.strip.rebuild()
try: w.side.views["logisim"].refresh_circuits()
except Exception: pass
doc.set_input("A", 1); doc.set_input("B", 1); doc.set_input("Cin", 0)
snap("logisim")
win = open_ic_view(w.ctx, doc, pg); win.geometry(f"{W}x{H}+0+0"); root.update(); win.update()
for key, name in (("gate", "ic-gate"), ("ic", "ic-view"), ("xray", "ic-xray")):
    win.show(key); win.update()
    for z in (win.gate_zoom, win.ic_zoom, win.x_zoom):
        try: z.fit()
        except Exception: pass
    win.update(); snap(name)
win.destroy(); root.update()
from vibesimulation.product import examples as EX
from vibesimulation.product.gallery import open_example
for sec, key, name in (("multisim", "rectifier", "multisim"), ("vlsi", "counter", "vlsi"), ("systemverilog", "traffic", "systemverilog")):
    open_example(w, EX.find(sec, key)); root.update(); w.ctx.toaster.hide(); snap(name)
w.ctx.cfg.clear(); w.ctx.save_cfg()
