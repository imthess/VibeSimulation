"""Platform layer: DPI scale, geometry fit, UTF-8 config I/O."""
import os, sys, tempfile, tkinter as tk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from vibesimulation.ui.look import platform
platform.prepare()                                  # no-op off Windows
root = tk.Tk()
os.environ["VIBE_UI_SCALE"] = "1.5"
assert platform.ui_scale(root) == 1.5
os.environ["VIBE_UI_SCALE"] = "9"; assert platform.ui_scale(root) == 3.0
os.environ["VIBE_UI_SCALE"] = "1.5"; platform.setup(root)
assert abs(float(root.tk.call("tk", "scaling")) - 2.0) < .01
g = platform.fit_geometry(root, "1360x860", 1.5); w, h = (int(x) for x in g.split("x"))
assert w <= root.winfo_screenwidth() and h <= root.winfo_screenheight(), g
from vibesimulation.ui.window import context
d = Path(tempfile.mkdtemp()); context.CFG = d / "c.json"
ctx = context.UiContext.__new__(context.UiContext); ctx.cfg = {"name": "é ü 日本"}; ctx.save_cfg()
import json; assert json.loads(context.CFG.read_text(encoding="utf-8"))["name"] == "é ü 日本"
root.destroy(); print("guitest58 ok")
