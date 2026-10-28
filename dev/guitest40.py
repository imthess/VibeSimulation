"""VLSI bottom dock: Problems / Output / Waveform, testbench tab, Verilog line <-> circuit part."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import tkinter as tk
from vibesimulation.components import load_all; load_all()
from vibesimulation.ui.main_window import MainWindow
root = tk.Tk(); root.geometry("1400x900"); w = MainWindow(root); ok = True; w.ctx.cfg.clear()
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
def pump(n=3):
    for _ in range(n): root.update(); time.sleep(0.02)
w.show("vlsi"); pump(); vp = w.pages["vlsi"]; d = w.vdoc; vv = vp.views["verilog"]; cv = vp.views["circuit"]; dock = vp.dock
def type_text(s):
    vv.txt.delete("1.0", "end"); vv.txt.insert("1.0", s); vv.txt.edit_modified(True); vv._modified()
    for _ in range(80):
        pump(2)
        if not vv._timer: break
    pump(3)
chk("dock exists with three tabs", dock is not None and set(dock.tab) == {"problems", "output", "wave"})
chk("dock is on screen", dock.winfo_ismapped() and dock.winfo_height() > 100)
# problems: warning for an unused input
type_text("module top(input A, B, C, output Y);\n  assign Y = A & B;\nendmodule\n")
chk("compiled", d.valid)
pt = dock.tab["problems"]; rows = [pt.t.item(i, "values") for i in pt.t.get_children()]
chk("a warning is listed", any("C" in str(r[1]) for r in rows) and pt.counts()[1] >= 1)
chk("tab title shows the count", "⚠" in dock.tabs.opts[0][0])
# click on a problem jumps to the line
pt.t.selection_set(pt.t.get_children()[0]); pt._go(); pump()
chk("jump put the cursor on the line", int(vv.txt.index("insert").split(".")[0]) == pt.rows[pt.t.get_children()[0]])
# errors listed
type_text("module top(input A, output Y);\n  assign Y = A ^ Q;\nendmodule\n")
chk("an error is listed", pt.counts()[0] >= 1)
# generated run -> waveform
type_text("module cnt(input clk, rst, output reg [3:0] q);\n  always @(posedge clk) if (rst) q <= 0; else q <= q + 1;\nendmodule\n")
dock.run(); pump()
r = d.last_run
chk("run ok", r is not None and r.error is None and "q" in r.waves)
chk("waveform tab shown", dock.cur == "wave")
chk("the counter counts", max(v for _, v in r.waves["q"]) >= 8)
wt = dock.tab["wave"]; pump(); chk("waveform drew items", len(wt.c.find_all()) > 20)
s0 = wt.scale; wt.cursor = 55; wt.draw(); wt.zoom(300, 2); chk("zoom works", wt.scale > s0)
# testbench tab
vv.switch("tb"); pump()
vv.txt.delete("1.0", "end"); vv.txt.insert("1.0", 'module tb;\n reg clk=0, rst=1; wire [3:0] q;\n cnt u(clk, rst, q);\n always #5 clk=~clk;\n initial begin #12 rst=0; #100 $display("q=%d", q); $finish; end\nendmodule\n'); vv.txt.edit_modified(True); vv._modified()
for _ in range(60):
    pump(2)
    if not vv._timer: break
chk("testbench text stored", "module tb" in d.tb_text)
dock.run(); pump()
chk("written testbench used", d.last_run.error is None and any(l.startswith("q=") for l in d.last_run.lines))
chk("output tab has the print", "q=" in dock.tab["output"].t.get("1.0", "end"))
vv.switch("design"); pump()
chk("design text back", "module cnt" in vv.get_text())
chk("design not polluted by the testbench", "module tb" not in vv.get_text())
# line <-> part
type_text("module top(input A, B, output Y);\n  assign Y = A & B; // @g1\nendmodule\n")
vv.goto(2); pump(); vp.line_picked(2); pump()
chk("line highlights the part", "g1" in cv.sels)
cv.sels = set(); cv.select("g1"); pump()
chk("clicking the part jumps to its line", int(vv.txt.index("insert").split(".")[0]) == 2)
dock.toggle(); pump(); chk("dock hides", not dock.body.winfo_ismapped()); dock.toggle(); pump(); chk("dock shows", dock.body.winfo_ismapped())
os.system("import -display :97 -window root /tmp/pv/dock.png 2>/dev/null")
print("ALL OK" if ok else "SOME FAILED"); root.destroy()
