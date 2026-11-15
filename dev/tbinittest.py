"""Testbench start values (reg a = 8'hA5) and localparam in a parameter header, as Icarus Verilog / Verilator accept them."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.workspaces.verilog.engine.tb import run_testbench
bad = 0
def chk(name, src, want):
    global bad
    r = run_testbench(src, top="t"); got = [l.strip() for l in r.lines if l.strip()]
    if got != want or r.error: bad += 1; print("FAIL", name, got, r.error and r.error.msg)
    else: print("ok  ", name)
chk("start value read by the program", "module t; reg [7:0] a=8'hA5, b=8'h3C; initial $display(\"%h %h\", a&b, a|b); endmodule", ["24 bd"])
chk("start value, signed", "module t; reg signed [7:0] a=-8'sd5; initial $display(\"%d\", a); endmodule", ["-5"])
chk("localparam in header", "module m #(parameter W=4, localparam M=W*2)(input [W-1:0] a, output [M-1:0] y); assign y={a,a}; endmodule module t; wire [7:0] y; m #(4) u(4'h9,y); initial #1 $display(\"%h\", y); endmodule", ["99"])
print("ALL OK" if not bad else "SOME FAILED"); sys.exit(1 if bad else 0)
