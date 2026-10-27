import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.core import commands as C
from vibesimulation.presets import PRESETS, merge
root = tk.Tk(); w = MainWindow(root); root.update()
w.show("logisim"); cv = w.pages["logisim"].views["circuit"]; d = w.doc; root.update()
# click on input A
pin, x, y = d.layout.inputs[0]
s = cv.scale; ox, oy = cv.org
class E: pass
e = E(); e.x = ox + (x - 8) * s; e.y = oy + y * s; e.x_root = e.y_root = 0
print("hit", cv.hit(e)); cv.on_click(e); print("invals", d.invals)
for cmd in (C.AddInput(), C.AddComponent("XOR"), C.AddComponent("MUX"), C.AddComponent("Decoder"), C.AddOutput("n1")):
    d.run(cmd); print(type(cmd).__name__, d.valid, d.errors, d.layout_error)
d.run(C.SetAttrs("g1" if d.circuit.component("g1") else d.circuit.components[0].id, {})) 
w.undo(); w.undo(); print("undo", d.valid)
for p in PRESETS:
    for ch in (p.choices[:1] + p.choices[-1:]):
        d.set_circuit(p.build(ch[1])); assert d.valid, (p.name, d.errors, d.layout_error)
d.set_circuit(merge(d.circuit.copy(), PRESETS[0].build(None))); print("merge", d.valid, d.layout_error)
import tempfile
from vibesimulation.export.pdf import make_pdf
open("/tmp/t.pdf","wb").write(make_pdf(d.layout, d.circuit, d.invals, d.circuit.table(12)))
print("pdf ok", os.path.getsize("/tmp/t.pdf"))
