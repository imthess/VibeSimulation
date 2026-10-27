import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root)
def snap(n): root.update(); root.update_idletasks(); os.system(f"import -display :97 -window root {S}{n}.png")
for pg in sys.argv[1:] or ["home","logisim","settings","multisim"]:
    w.show(pg); snap("m_"+pg)
print("DONE")
