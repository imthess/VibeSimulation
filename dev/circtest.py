"""Logisim .circ compatibility: open into Logisim and VLSI, round trip, and the report of unsupported parts."""
import sys, os, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=3):
    for _ in range(n): root.update(); time.sleep(0.02)
said = []
w.ctx.say = lambda t, m, parent=None: said.append((t, m))
w.ctx.choose_file = lambda *a, **k: None
# a circuit from the VLSI sample -> .circ -> back
d = w.vdoc; pump()
circ = d.circ_text(); tmp = tempfile.mkdtemp(); p = os.path.join(tmp, "a.circ"); open(p, "w").write(circ)
tt = d.circuit.table(12)
# open it in Logisim
chk("Logisim opens a .circ", w.actions.circ_open(p) and w.doc.valid)
tt2 = w.doc.circuit.table(12)
chk("same truth table after the round trip", tt2 == tt)
chk("clean file gives no report", not said)
# open it into the VLSI page
chk("VLSI opens a .circ", w.vactions.circ_open(p) and w.vdoc.valid and "module" in w.vdoc.verilog())
# a file with a part we do not support
bad = circ.replace("</circuit>", '    <comp lib="5" loc="(900,900)" name="Keyboard"/>\n  </circuit>', 1)
open(p, "w").write(bad); said.clear()
chk("opens with an unsupported part", w.actions.circ_open(p))
chk("the report names it", said and "Keyboard" in said[-1][1] and "Compatibility report" in said[-1][1])
chk("the rest is still there", w.doc.valid and w.doc.circuit.table(12) == tt)
open(p, "w").write("<nope"); said.clear()
chk("garbage is refused with a message", not w.actions.circ_open(p) and said)
print("ALL OK" if ok else "SOME FAILED"); root.destroy()
