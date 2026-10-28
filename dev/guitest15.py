import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.show("logisim"); root.update()
pg = w.pages["logisim"]; jv = pg.views["json"]
txt = jv.doc.text.replace('"NOT"', '"NOTT"', 1) if False else jv.doc.text
lines = txt.split("\n"); 
bad = "\n".join(lines[:-3]) + "\n" + '    {"id": "g9", "type": "NOR", "in": ["A", "zzz"], "out": "q"}\n  ]\n}\n'
jv.doc.set_text(bad); root.update(); print(jv.err_lines, jv.doc.errors)
os.system(f"import -display :97 -window root {S}j1.png")
jv.doc.set_text(txt.replace('"outputs"', '"outputs" ,,', 1)); root.update(); print(jv.err_lines, jv.doc.errors)
os.system(f"import -display :97 -window root {S}j2.png")
t2 = txt.replace('"in": ["C"]', '"in": ["Q9"]'); jv.doc.set_text(t2); root.update(); print(jv.err_lines, jv.doc.errors)
t3 = txt.replace('"g2"', '"g1"'); jv.doc.set_text(t3); root.update(); print(jv.err_lines, jv.doc.errors)
t4 = txt.replace('"type": "NOT"', '"type": "FOO"'); jv.doc.set_text(t4); root.update(); print(jv.err_lines, jv.doc.errors)
ctx.cfg.clear(); ctx.save_cfg()
