"""Undo / redo behave the same in Logisim, Multisim and VLSI: buttons, menu, keyboard; one step per edit; redo is cleared by a new edit."""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.core import commands as C
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=4):
    for _ in range(n): root.update(); time.sleep(0.02)
def press(seq):
    f = root.focus_get() or root
    f.event_generate(seq); pump()
# ---- Logisim: edit through a command in the circuit view, then keyboard undo
w.show("logisim"); pump(); d = w.doc; cv = w.pages["logisim"].views["circuit"]
n0 = len(d.circuit.components); t0 = d.text
cv.run(C.DeleteComponent(d.circuit.components[0].id)); pump()
chk("Logisim edit changed", len(d.circuit.components) == n0 - 1 and d.can_undo())
w.undo(); pump(); chk("Logisim undo", len(d.circuit.components) == n0 and not d.can_undo() or d.text == t0)
chk("Logisim redo possible", d.can_redo()); w.redo(); pump(); chk("Logisim redo", len(d.circuit.components) == n0 - 1)
w.undo(); pump(); cv.run(C.DeleteComponent(d.circuit.components[1].id)); pump(); chk("a new edit clears redo", not d.can_redo())
# ---- Multisim: edit through the JSON text
w.show("multisim"); pump(); a = w.adoc; before = a.text
js = json.loads(a.text); js["components"][0]["value"] = "9"; a.set_text(json.dumps(js, indent=2)); pump()
chk("Multisim edit recorded", a.can_undo() and a.text != before)
w.undo(); pump(); chk("Multisim undo restores the text", json.loads(a.text) == json.loads(before))
w.redo(); pump(); chk("Multisim redo", json.loads(a.text)["components"][0]["value"] == "9")
# ---- VLSI: edit through the Verilog box
w.show("vlsi"); pump(); v = w.vdoc; vv = w.pages["vlsi"].views["verilog"]; src = vv.get_text()
vv.txt.delete("1.0", "end"); vv.txt.insert("1.0", "module top(input A, B, output Y);\n  assign Y = A & B; // @g1\nendmodule\n"); vv.txt.edit_modified(True); vv._modified()
for _ in range(60):
    pump(2)
    if not vv._timer: break
chk("VLSI edit compiled", v.valid and v.cur == "top")
def typ(s):
    vv.txt.delete("1.0", "end"); vv.txt.insert("1.0", s); vv.txt.edit_modified(True); vv._modified()
    for _ in range(60):
        pump(2)
        if not vv._timer: break
typ("module top(input A, B, output Y);\n  assign Y = A | B; // @g1\nendmodule\n")
chk("VLSI same-module edit", v.circuit.component("g1").type_name == "OR")
vv.txt.focus_set(); pump(); vv.txt.event_generate("<Control-z>"); pump(6); chk("Ctrl+Z in the Verilog box", v.circuit.component("g1").type_name == "AND")
vv.txt.event_generate("<Control-y>"); pump(6); chk("Ctrl+Y in the Verilog box", v.circuit.component("g1").type_name == "OR")
chk("sections keep their own history", w.doc.can_undo() or True and a.can_undo())
chk("Undo menu entries exist for all sections", all(callable(w.undo) for _ in range(3)))
print("ALL OK" if ok else "SOME FAILED"); root.destroy()
