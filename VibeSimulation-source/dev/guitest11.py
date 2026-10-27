import sys, os, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all
load_all()
from vibesimulation.ui.main_window import MainWindow
S="/tmp/claude-0/-home-claude/872dc6ac-ca5f-5a34-9449-2aadb4ac7a79/scratchpad/"
root = tk.Tk(); w = MainWindow(root); ctx = w.ctx
f = tempfile.NamedTemporaryFile(suffix=".json", delete=False); f.write(b'{}'); f.close(); ctx.add_recent(f.name)
def snap(n): root.update(); os.system(f"import -display :97 -window root {S}{n}.png")
def ok(c, m): print(("PASS " if c else "FAIL ")+m)
def pump(n=5):
    for _ in range(n): root.update(); time.sleep(0.02)
def click(widget, x=5, y=5):
    widget.event_generate("<Enter>"); widget.event_generate("<ButtonPress-1>", x=x, y=y); widget.event_generate("<ButtonRelease-1>", x=x, y=y); pump()
w.show("logisim"); pump()
b = w.menubar.buttons[0]
click(b); ok(ctx.popup is not None, "File menu opens on click"); snap("p1")
# click elsewhere closes
t = w.pages["logisim"].views["json"].txt
t.event_generate("<ButtonPress-1>", x=10, y=10); pump(); ok(ctx.popup is None, "click elsewhere closes menu")
click(b); ok(ctx.popup is not None, "reopen"); click(b); ok(ctx.popup is None, "click on same button toggles closed")
# Alt+F then Esc
root.focus_force(); root.event_generate("<Alt-Key-f>"); pump(); ok(ctx.popup is not None, "Alt+F opens"); ctx.popup.frame.event_generate("<Escape>"); pump(); ok(ctx.popup is None, "Esc closes")
# keyboard navigation + submenu
w.menubar.popup(b); pump(); m = ctx.popup
m.frame.event_generate("<Down>"); pump(); m.frame.event_generate("<Down>"); pump(); ok(m.sel is not None, f"arrow nav sel={m.sel}")
# find Open Recent index
i = next(k for k, it in enumerate(m.items) if it["label"] == "Open Recent"); m.hilite(i); m.frame.event_generate("<Right>"); pump(); ok(m.child is not None, "Right opens submenu"); snap("p2")
m.child.frame.event_generate("<Left>"); pump(); ok(m.child is None and ctx.popup is m, "Left closes submenu")
click(w.rail, 40, 140)
pump(); ok(ctx.popup is None, "rail click closes menu"); 
# item executes
called = []
mm = ctx.menu(); mm.add_command(label="Do it", command=lambda: called.append(1)); mm.add_separator(); mm.add_checkbutton(label="Flag", variable=tk.BooleanVar(value=True))
mm.tk_popup(300, 300); pump(); row = mm.rows[0][1]; row.event_generate("<Enter>"); row.event_generate("<ButtonRelease-1>"); pump(8); ok(called==[1] and ctx.popup is None, "item runs and menu closes")
# right-click text menu closes
t.event_generate("<Button-3>", x=20, y=20); pump(); ok(ctx.popup is not None, "text context menu"); snap("p3"); root.event_generate("<ButtonPress-1>"); t.event_generate("<ButtonPress-1>", x=3, y=3); pump(); ok(ctx.popup is None, "context menu closes on outside click")
# rail navigation
for k in ("home","import","multisim","settings","logisim"):
    w.rail.event_generate("<Enter>"); w.show(k); pump()
snap("p4")
w.show("settings"); pump(); snap("p5")
w.show("home"); pump(); w.rail.focus_force(); ctx.kbd = True; w.rail.event_generate("<Down>"); w.rail.event_generate("<Return>"); pump(); ok(w.current=="logisim", f"rail keyboard -> {w.current}")
print("DONE")
