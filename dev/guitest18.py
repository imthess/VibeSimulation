import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
ctx.cfg["play_secs"] = 0.25
w.show("logisim"); root.update(); tv = w.pages["logisim"].views["table"]; doc = w.doc
seen = []
def pump(t):
    end = time.time() + t
    while time.time() < end: root.update(); time.sleep(0.01)
doc.subscribe(lambda k: seen.append(tuple(sorted(doc.invals.items()))) if k == "values" else None) if hasattr(doc, "subscribe") else None
tv.toggle_play(); pump(0.25 * 8 + 0.4)
print("playing after full pass (no repeat):", tv.playing, "| rows seen:", len(seen), "| status:", tv.status.cget("text"))
seen.clear(); tv.toggle_repeat(); tv.toggle_play(); pump(0.25 * 11)
print("repeat on, playing:", tv.playing, "| pos", tv.pos, "| steps seen", len(seen), "| status:", tv.status.cget("text"))
os.system(f"import -display :97 -window root {S}play.png")
tv.toggle_play(); print("stopped:", not tv.playing, tv.btn_play.text)
doc.set_text("{bad"); root.update(); print("invalid -> play enabled:", tv.btn_play.on)
ctx.cfg.clear(); ctx.save_cfg()
