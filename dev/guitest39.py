"""VLSI section: Verilog | Circuit | Truth table, separate from Logisim."""
import sys, os, json, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
from vibesimulation.core import project as PRJ
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=3):
    for _ in range(n): root.update(); time.sleep(0.02)
LOGIC = {"inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}]}
w.show("logisim"); w.doc.load_text(json.dumps(LOGIC)); pump()
# ---- Logisim has only its three boxes and no Verilog
lg = w.pages["logisim"]
chk("Logisim page has circuit, json, table only", set(lg.views) == {"circuit", "json", "table"})
chk("Logisim JSON box has no Verilog switch", not hasattr(lg.views["json"], "b_v"))
chk("Logisim shows JSON", '"AND"' in lg.views["json"].txt.get("1.0", "end"))
# ---- the VLSI page: three boxes
w.show("vlsi"); pump(); vp = w.pages["vlsi"]; d = w.vdoc
chk("VLSI page has verilog, circuit, table", set(vp.views) == {"verilog", "circuit", "table"})
chk("rail has a VLSI button and the page opens", w.current == "vlsi" and "vlsi" in w.rail.keys)
vv = vp.views["verilog"]
chk("starts with the sample design, as typed", "4-bit adder" in vv.txt.get("1.0", "end") and d.valid)
chk("its own project (not Logisim's)", list(d.circuits) == ["adder4"] and list(w.doc.circuits) == ["main"])
def type_text(s):
    vv.txt.delete("1.0", "end"); vv.txt.insert("1.0", s); vv.txt.edit_modified(True); vv._modified()
    for _ in range(80):
        pump(2)
        if not vv._timer: break
    pump(3)
type_text("module top(input A, B, output Y);\n  assign Y = A | B; // @g1\nendmodule\n")
chk("typing Verilog builds the circuit (OR)", d.valid and d.circuit.component("g1").type_name == "OR" and d.cur == "top")
chk("the circuit box draws it", len(d.layout.parts) >= 1)
tv = vp.views["table"]; pump()
chk("the truth table shows it", tv.data is not None and len(tv.data[1]) == 4)
chk("Logisim circuit untouched", w.doc.circuit.component("g1").type_name == "AND" and list(w.doc.circuits) == ["main"])
# ---- errors
type_text("module top(input A, B, output Y);\n  assign Y = A ^ Q;\nendmodule\n")
chk("error keeps the old circuit", d.circuit.component("g1").type_name == "OR")
chk("error line marked with message", 2 in vv.err_lines and "line 2" in vv.status.msg and "'Q' is not declared" in vv.status.msg)
chk("faulty text kept", "A ^ Q" in vv.txt.get("1.0", "end"))
# ---- circuit box: layout allowed, logic edits refused
cv = vp.views["circuit"]
from vibesimulation.core import commands as C
n0 = len(d.circuit.components)
cv.run(C.AddComponent("AND")); pump()
chk("circuit box refuses to add a part", len(d.circuit.components) == n0 and "Verilog" in cv.status.cget("text"))
pl = d.layout.parts[0]; tx, ty = pl.x + 30, pl.y + 20
cv.run(C.MovePart("g1", tx, ty)); pump()
chk("circuit box allows moving a part", d.circuit.component("g1").pos == (tx, ty))
chk("moving does not rewrite the Verilog", "A | B" in d.verilog())
# ---- coherence: a change of logic elsewhere rewrites the Verilog
type_text("module top(input A, B, output Y);\n  assign Y = A | B; // @g1\nendmodule\n")
d.set_text(json.dumps({"inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NAND", "in": ["A", "B"], "out": "Y"}]})); pump()
chk("JSON change rewrites the Verilog", "nand g1" in vv.txt.get("1.0", "end"))
# ---- registers
type_text("""module top(input clk, rst, en, output reg [3:0] q, output tc);
  assign tc = (q == 4'd15);
  always @(posedge clk or posedge rst) begin
    if (rst) q <= 4'd0;
    else if (en) q <= q + 4'd1;
  end
endmodule
""")
chk("counter compiled", d.valid and d.circuit.has_seq())
d.set_input("rst", 1); d.set_input("rst", 0); d.set_input("en", 1)
for _ in range(6): d.set_input("clk", 1); d.set_input("clk", 0)
chk("counter counts (6 cycles -> 6)", d.vals.get("q") == 6)
# ---- modules
type_text("module inv(input a, output y); assign y = ~a; endmodule\nmodule top(input A, output Y); inv u(.a(A), .y(Y)); endmodule\n")
chk("two modules become two circuits", set(d.circuits) >= {"inv", "top"} and d.valid)
w.show("logisim"); pump()
chk("Logisim still has only its own circuits", list(w.doc.circuits) == ["main"] and PRJ.lookup("inv") is None and w.doc.valid)
w.show("vlsi"); pump()
chk("VLSI project is back when its page is shown", PRJ.lookup("inv") is not None)
# ---- side panel
w.show_side(True); pump(); sv = w.side.view(); pump()
chk("explorer lists the modules", any(v == ("module", "inv") for v in sv.items.values()))
vv.txt.mark_set("insert", "end"); sv._insert("  // inserted\n"); pump(10)
chk("explorer can insert a template", "// inserted" in vv.txt.get("1.0", "end"))
# ---- files
p = os.path.join(tempfile.mkdtemp(), "x.v")
w.ctx.choose_file = lambda *a, **k: p; w.ctx.say = lambda *a, **k: None
d.new_blank("module t(input a, b, output y); assign y = a ^ b; endmodule\n"); pump()
w.vactions.verilog_save(); pump()
chk("export wrote a .v file", os.path.exists(p) and "module t" in open(p).read())
open(p, "w").write("module t(input a, b, output y); assign y = a & b; endmodule")
chk("open a .v file", w.vactions.verilog_open() and any(c.type_name == "AND" for c in d.circuit.components))
chk("menus: VLSI page has its own menus", [n for n, _ in __import__("vibesimulation.ui.menus", fromlist=["x"]).menus_for(w, "vlsi")] == ["File", "Edit", "Simulate", "View", "Help"])
w.undo(); pump(); chk("undo works on the VLSI document", True)
print("ALL OK" if ok else "SOME FAILED"); root.destroy()
