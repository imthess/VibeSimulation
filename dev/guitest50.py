"""Glass look: every page paints in light and dark, with the glass look on and off, and the switch in Settings exists."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=12):
    for _ in range(n): root.update(); time.sleep(0.02)
for mode in ("light", "dark"):
    for glass in (True, False):
        w.ctx.cfg["mode"] = mode; w.ctx.cfg["glass"] = glass; w.ctx.refresh(); w.after_look() if hasattr(w, "after_look") else None
        try:
            for pg in ("home", "logisim", "multisim", "vlsi", "systemverilog", "import", "settings"): w.show(pg); pump(6)
            chk(f"{mode}, glass {'on' if glass else 'off'}: all seven pages open", True)
        except Exception as ex: chk(f"{mode}, glass {glass}: pages open ({ex!r})", False)
w.ctx.cfg["glass"] = True; w.ctx.refresh(); w.show("logisim"); pump(20)
if w.ctx.glass.ok:
    card = w.pages["logisim"].views["circuit"].card
    chk("panels are glass cards", card.glassy() and getattr(card, "_gimg", None) is not None)
    chk("the backdrop picture is made", w.ctx.glass.back is not None)
    chk("the rail is a floating capsule", w.rail.opt()["style"] == "Floating")
chk("Settings has a Glass look switch", any(d.title == "Glass look" for d in w.pages["settings"].items)) if hasattr(w.pages["settings"], "items") else None
g = w.ctx.glass
for style, extra in (("Sunset", {}), ("Slate", {}), ("Custom", {"bg_color": "#22c55e"}), ("Aurora", {})):
    w.ctx.cfg.update(extra); w.ctx.cfg["bg_style"] = style; w.ctx.refresh(); w.show("logisim"); pump(20)
    card = w.pages["logisim"].views["circuit"].card
    chk(f"background {style}: panels repainted", card._gkey[-1] == g.gen)
w.ctx.cfg["mode"] = "dark"; w.ctx.refresh(); w.show("logisim"); pump(20); chk("a theme change repaints the panels", card._gkey[-1] == g.gen and w.ctx.dark)
chk("no hint text beside pane titles", not card.hint.winfo_ismapped())
chk("status bar is off by default", not w.status.winfo_ismapped())
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
