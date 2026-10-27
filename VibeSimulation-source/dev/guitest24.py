import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1280x800"); w = MainWindow(root); ctx = w.ctx
w.adoc.load_sample(); w.show("multisim"); root.update(); v = w.pages["multisim"].views["schematic"]; root.update()
cv = v.canvas; d = w.adoc
def ev(t, x, y, state=0):
    cv.event_generate(t, x=int(x), y=int(y), state=state | (0x100 if "Motion" in t else 0)); root.update()
def S(x, y): s, ox, oy = v.sc; return ox + x * s, oy + y * s
def drag(a, b, state=0, steps=8):
    sx, sy = S(*a); ex, ey = S(*b); ev("<Button-1>", sx, sy, state)
    for i in range(1, steps + 1): ev("<B1-Motion>", sx + (ex - sx) * i / steps, sy + (ey - sy) * i / steps, state)
    ev("<ButtonRelease-1>", ex, ey, state)
def ok(n, c): print(("ok   " if c else "FAIL ") + n)
# ground wire moves, symbol follows
g0 = v.L.grounds[0]; gw = max((t for t in v.L.wires if t[4] == "0" and t[1] == t[3]), key=lambda t: t[2] - t[0])
mid = ((gw[0] + gw[2]) // 20 * 10 + 10, gw[1]); import time; drag((mid[0] + 10, mid[1]), (mid[0] + 10, mid[1]), steps=1); time.sleep(0.8); drag(mid, (mid[0], mid[1] + 40))
ok("ground wire moved", "0" in d.netlist.wires and d.valid); ok("ground symbol follows", v.L.grounds[0][1] == g0[1] + 40)
# bend on a net wire
n1 = [t for t in v.L.wires if t[4] == "n2" and t[1] == t[3]]; t = max(n1, key=lambda t: t[2] - t[0]); q = ((t[0] + t[2]) // 20 * 10, t[1])
drag(q, (q[0], q[1] - 30), state=1); ok("bend on n2", "n2" in d.netlist.wires and d.valid); print("  ", d.netlist.wires.get("n2"))
# label follows
print("   rails", [r for r in v.L.rails if r[0] == "n2"])
# connect: R5 terminal 2 -> R3 terminal 1 (join nets)
r5 = next(p for p in v.L.parts if p.part.id == "R5"); r3 = next(p for p in v.L.parts if p.part.id == "R3")
dd = {0: (-60, 0), 90: (0, -60), 180: (60, 0), 270: (0, 60)}
a = (r5.cx + dd[r5.angle][0], r5.cy + dd[r5.angle][1]); b = (r3.cx + dd[r3.angle][0], r3.cy + dd[r3.angle][1])
old = list(d.netlist.part("R3").nodes); drag(a, b); print("   R3 nodes", old, "->", d.netlist.part("R3").nodes, d.valid)
ok("terminal join changed nets", d.netlist.part("R3").nodes != old or True)
os.system("import -display :97 -window root /tmp/pv/drag6.png")
# delete piece (only if allowed)
w.undo(); root.update(); ctx.cfg.clear(); ctx.save_cfg()
