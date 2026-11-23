"""Properties panel at the bottom of the side bar (Logisim and Multisim): shows the selection and applies edits at once."""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
root = tk.Tk(); root.geometry("1500x950"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=8):
    for _ in range(n): root.update(); time.sleep(0.02)
def field(panel, label):
    for i, f in enumerate(panel.fields):
        if f.label.startswith(label): return f, panel.vars[i]
    return None, None
w.show("logisim"); w.doc.load_text(json.dumps({"inputs": ["A", "B", "C"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}]})); pump()
ex = w.side.view(); cv = w.pages["logisim"].views["circuit"]; pn = ex.props; pump()
chk("Logisim: nothing selected shows the circuit summary", pn.head.cget("text").startswith("Circuit"))
cv.select("g1"); pump()
chk("Logisim: selecting the AND shows its properties", pn.head.cget("text") == "AND" and field(pn, "Name")[0] is not None)
f, v = field(pn, "Number of inputs")
chk("Logisim: it has a Number of inputs box", f is not None)
if f: f.apply(3); pump(); chk("Logisim: changing Inputs to 3 applies at once", len(w.doc.circuit.component("g1").ins) == 3 or w.doc.circuit.component("g1").attrs["inputs"] == 3)
cv.select(None); cv.psel = {("in", "A")}; cv.draw(); pump()
chk("Logisim: selecting an input pin shows Label and Width", pn.head.cget("text") == "Input pin" and field(pn, "Label")[0] is not None)
f, v = field(pn, "Label")
if f: f.apply("Q"); pump(); chk("Logisim: renaming the input pin works", any(p.name == "Q" for p in w.doc.circuit.inputs))
# ---------------- Multisim
CIR = {"kind": "analog", "components": [{"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["in", "0"]}, {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["in", "mid"]}, {"id": "R2", "type": "Resistor", "value": "2k", "nodes": ["mid", "0"]}]}
w.show("multisim"); w.adoc.load_text(json.dumps(CIR)); pump(); sv = w.pages["multisim"].views["schematic"]; bn = w.side.view(); pn = bn.props; pump()
chk("Multisim: nothing selected shows the circuit", pn.head.cget("text") == "Circuit")
sv.select_part("R1"); pump()
chk("Multisim: selecting R1 shows its properties", pn.head.cget("text") == "Resistor" and field(pn, "Label")[0] is not None)
f, v = field(pn, "Value")
if f: f.apply("4.7k"); pump(); chk("Multisim: editing Value applies at once", str(w.adoc.netlist.part("R1").value) == "4.7k")
sv.select_part("R1"); pump(); f, v = field(pn, "Label")
if f: f.apply("RLOAD"); pump(); chk("Multisim: Label renames the part", w.adoc.netlist.part("RLOAD") is not None and w.adoc.netlist.part("R1") is None)
f, v = field(pn, "Value")
if f:
    try: f.apply("abc"); chk("Multisim: a bad value is refused", False)
    except Exception: chk("Multisim: a bad value is refused", True)
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
