"""Verilog and SystemVerilog files in and out of the app: open a .v / .sv file, check the inputs and outputs shown, save it again, open the saved file in a
fresh project and get the same inputs and outputs (and every sample of the .v / .sv text in the two tabs' own sample list opens without errors)."""
import sys, os, time, tempfile, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vibesimulation.ui.window.main_window import MainWindow
root = tk.Tk(); root.geometry("1300x820"); w = MainWindow(root); ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def ports(doc): return sorted([(p.name, "in", p.width) for p in doc.circuit.inputs] + [(p.name, "out", p.width) for p in doc.circuit.outputs])
V = {"mux": ("mux4", "module mux4 (input [7:0] d0, d1, d2, d3, input [1:0] s, output reg [7:0] y);\n always @* case (s) 2'd0: y = d0; 2'd1: y = d1; 2'd2: y = d2; default: y = d3; endcase\nendmodule\n",
             [("d0", "in", 8), ("d1", "in", 8), ("d2", "in", 8), ("d3", "in", 8), ("s", "in", 2), ("y", "out", 8)]),
     "counter": ("cnt", "module cnt (input clk, rst, output reg [3:0] q);\n always @(posedge clk) if (rst) q <= 0; else q <= q + 1;\nendmodule\n", [("clk", "in", 1), ("q", "out", 4), ("rst", "in", 1)]),
     "adder": ("add", "module add (input [3:0] a, b, output [4:0] s);\n assign s = a + b;\nendmodule\n", [("a", "in", 4), ("b", "in", 4), ("s", "out", 5)])}
SV = {"alu": ("alu", "module alu (input logic [7:0] a, b, input logic op, output logic [7:0] y);\n always_comb y = op ? a - b : a + b;\nendmodule\n", [("a", "in", 8), ("b", "in", 8), ("op", "in", 1), ("y", "out", 8)]),
      "fsm": ("fsm", "typedef enum logic [1:0] {A, B, C} st_t;\nmodule fsm (input logic clk, rst, x, output logic y);\n st_t s;\n always_ff @(posedge clk) if (rst) s <= A; else case (s) A: if (x) s <= B; B: s <= C; default: s <= A; endcase\n assign y = (s == C);\nendmodule\n",
             [("clk", "in", 1), ("rst", "in", 1), ("x", "in", 1), ("y", "out", 1)])}
tmp = tempfile.mkdtemp()
for page, acts, doc, samples, ext in (("vlsi", w.vactions, w.vdoc, V, ".v"), ("systemverilog", w.sactions, w.sdoc, SV, ".sv")):
    w.show(page); root.update()
    for key, (top, text, want) in samples.items():
        p = f"{tmp}/{top}{ext}"; open(p, "w").write(text)
        chk(f"{ext} {key}: file opens", acts.verilog_open(p) is True)
        chk(f"{ext} {key}: inputs and outputs shown = declared", ports(doc) == sorted(want))
        saved = doc.verilog_project()
        chk(f"{ext} {key}: the saved text contains the module", re.search(rf"\bmodule\s+{top}\b", saved) is not None)
        out = f"{tmp}/saved_{top}{ext}"; open(out, "w").write(saved)
        fresh = type(doc)(); fresh.load_sample() if hasattr(fresh, "load_sample") else None
        errs = fresh.set_verilog(open(out).read())
        chk(f"{ext} {key}: the saved file opens again with the same inputs and outputs", not errs and ports(fresh) == sorted(want))
print("ALL OK" if ok else "SOME FAILED"); root.destroy(); sys.exit(0 if ok else 1)
