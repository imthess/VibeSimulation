import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.presets import PRESETS
root = tk.Tk(); w = MainWindow(root)
def snap(name):
    root.update(); os.system(f"import -window root /tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/{name}.png 2>/dev/null || xwd -root -silent | convert xwd:- /tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/{name}.png")
root.update(); snap("g_all")
w.doc.set_circuit(PRESETS[2].build(4)); snap("g_adder")
w.set_mode("2,3"); snap("g_23")
w.doc.set_circuit(PRESETS[4].build(2)); w.set_mode("3,4"); snap("g_mux")
w.toggle_dark(); snap("g_dark")
w.doc.set_input("A0", 1) if False else None
print("OK", w.doc.valid, w.doc.errors, w.doc.layout_error)
