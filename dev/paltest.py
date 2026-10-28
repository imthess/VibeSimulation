import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.ui.logisim.parts_palette import PaletteDialog
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx; root.update()
d = PaletteDialog(ctx); d.update()
t = d.tree
for top in t.get_children(): t.item(top, open=True)
d.update()
print([t.item(i, "text") for i in t.get_children()])
t.selection_set([i for i,(k,o) in d.items.items() if k=="todo"][0]); d.select(); d.update()
t.item(t.get_children()[0], open=True); d.update()
print(sum(1 for k,o in d.items.values() if k=="part"), "parts,", sum(1 for k,o in d.items.values() if k=="todo"), "greyed")
os.system("import -display :97 -window root /tmp/pv/pal.png")
