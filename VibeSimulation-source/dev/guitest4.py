import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root)
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
w.show("multisim"); snap("m_ms")
sv=w.pages["multisim"].views["schematic"]; sv.add(sv.__class__.__mro__[0] and __import__("vibesimulation.analog.components",fromlist=["x"]).Capacitor)
print(w.adoc.valid, w.adoc.errors, w.adoc.layout_error)
w.undo(); print("undo", w.adoc.valid, len(w.adoc.netlist.parts)); w.redo(); print(len(w.adoc.netlist.parts))
w.menubar.download_menu(w.ctx.menu()); w.menubar.file_menu(w.ctx.menu()); w.menubar.view_menu(w.ctx.menu())
w.adoc.set_text('{"components":[{"id":"R1","type":"R","value":"1k","nodes":["a","b"]}]}'); print(w.adoc.valid, w.adoc.errors)
w.adoc.set_text('{"components":[{"id":"V1","type":"V","value":5,"nodes":["a","0"]},{"id":"V2","type":"V","value":3,"nodes":["a","0"]}]}'); print(w.adoc.valid, w.adoc.layout_error[:60])
w.adoc.load_sample(); w.pages["multisim"].swap("schematic","results"); snap("m_ms2")
import tempfile; open("/tmp/x.cir","w").write(__import__("vibesimulation.analog.netlist",fromlist=["x"]).to_spice(w.adoc.netlist)); print("DONE")
