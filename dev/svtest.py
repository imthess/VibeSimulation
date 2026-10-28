"""SystemVerilog lowering: each feature against iverilog (-g2012 runs the SystemVerilog itself), plus the error messages."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from svcheck import check
from vibesimulation.systemverilog.compiler import lower
from vibesimulation.systemverilog.features import preprocess as _p
from vibesimulation.verilog.lexer import VError
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)
def diff(name, sv, top, resets=(), nvec=80):
    try: m, n = check(sv, top, nvec=nvec, resets=list(resets))
    except Exception as e: ok(False, f"{name}: {type(e).__name__}: {str(e)[:150]}"); return
    ok(m == 0 and n > 0, f"{name}: {n} values agree with iverilog" if m == 0 else f"{name}: {m} of {n} differ")
def diff_ref(name, sv, ref, top, resets=()):
    """iverilog cannot run this SystemVerilog: compare the lowering with Verilog written by hand."""
    from vcheck import compare
    try: m, n = compare(lower(sv).verilog, top, 80, 1, resets=list(resets), ref_src=ref)
    except Exception as e: ok(False, f"{name}: {type(e).__name__}: {str(e)[:150]}"); return
    ok(m == 0 and n > 0, f"{name}: {n} values agree with the hand-written Verilog" if m == 0 else f"{name}: {m} of {n} differ")
def fails(name, sv, word):
    try: lower(sv); ok(False, f"{name}: should be refused")
    except VError as e: ok(word.lower() in e.msg.lower() and e.line >= 1, f"{name}: refused with line {e.line}: {e.msg[:70]}")

# ---------------- logic, always_comb, always_ff, always_latch
diff("alu with logic / unique case / fill literals", open("/tmp/c1.sv").read() if os.path.exists("/tmp/c1.sv") else "", "alu") if False else None
diff("alu with unique case and fill literals", """module alu #(parameter int W = 8) (input logic [W-1:0] a, b, input logic [2:0] op, output logic [W-1:0] y, output logic zero);
  always_comb begin
    unique case (op)
      3'd0: y = a + b; 3'd1: y = a - b; 3'd2: y = a & b; 3'd3: y = a | b; 3'd4: y = a ^ b; 3'd5: y = a << 1; 3'd6: y = '1; default: y = '0;
    endcase
  end
  assign zero = (y == '0);
endmodule""", "alu")
diff("always_ff with async reset and ++", """module cnt (input logic clk, rst, en, output logic [3:0] q, output logic [2:0] ones);
  always_ff @(posedge clk or posedge rst) begin if (rst) q <= '0; else if (en) q++; end
  always_comb begin ones = 0; for (int i = 0; i < 4; i++) ones += q[i]; end
endmodule""", "cnt", [("rst", 1)])
try:
    from vibesimulation.vlsi.compiler import compile_text
    r = compile_text(lower("module lat (input logic en, input logic [3:0] d, output logic [3:0] q);\n  always_latch if (en) q <= d;\nendmodule").verilog, {}, "main")
    ok(r.errors and "latch" in r.errors[0][1] and r.errors[0][0] == 2, f"always_latch is reported like a latch in the Verilog tab (line {r.errors[0][0]})" if r.errors else "always_latch")
except Exception as e: ok(False, f"always_latch: {e}")
diff("mixed reg / wire outputs split in one declaration", """module mix (input logic clk, input logic [3:0] d, output logic [3:0] a, b);
  always_ff @(posedge clk) a <= d;
  assign b = ~a;
endmodule""", "mix")
diff("int, byte and shortint", """module ints (input logic [7:0] a, output int y, output byte z, output logic signed [15:0] w);
  assign y = a * 3;
  assign z = a;
  always_comb begin shortint t; t = a; w = t - 5; end
endmodule""", "ints")
# ---------------- enum / typedef / struct / package
diff("enum state machine", """typedef enum logic [1:0] {S0, S1, S2, S3} st_t;
module fsm (input logic clk, rst, x, output logic [1:0] y, output logic z);
  st_t s, n;
  always_ff @(posedge clk or posedge rst) if (rst) s <= S0; else s <= n;
  always_comb begin n = s; z = 1'b0; case (s) S0: if (x) n = S1; S1: if (x) n = S2; else n = S0; S2: begin n = S3; z = 1'b1; end S3: n = S0; endcase end
  assign y = s;
endmodule""", "fsm", [("rst", 1)])
diff("enum with explicit values, no base type", """module e (input logic [2:0] sel, output logic [2:0] y);
  typedef enum {A = 1, B = 3, C = 6} k_t;
  k_t k;
  always_comb begin case (sel) 0: k = A; 1: k = B; default: k = C; endcase y = k; end
endmodule""", "e")
diff("typedef alias", """typedef logic [7:0] byte_t;
module t (input byte_t a, b, output byte_t s);
  assign s = a + b;
endmodule""", "t")
diff("packed struct", """module st (input logic [7:0] x, output logic [3:0] hi, output logic [3:0] lo, output logic [7:0] sw);
  typedef struct packed { logic [3:0] a; logic [3:0] b; } pair_t;
  pair_t p, q;
  assign p = x;
  assign q.a = p.b; assign q.b = p.a;
  assign hi = p.a; assign lo = p.b; assign sw = q;
endmodule""", "st")
diff("package parameter, enum and function", """package pk;
  localparam int N = 4;
  typedef enum logic [1:0] {RED, GREEN, BLUE} col_t;
  function automatic logic [N-1:0] twice(input logic [N-1:0] v); return v + v; endfunction
endpackage
module u import pk::*; (input logic [N-1:0] a, input logic [1:0] c, output logic [N-1:0] y, output logic hit);
  col_t k;
  assign k = col_t'(c);
  assign y = twice(a);
  assign hit = (k == GREEN);
endmodule""", "u")
diff("pk::name without import", """package pk; localparam int N = 3; function logic [2:0] inv(logic [2:0] v); return ~v; endfunction endpackage
module u (input logic [pk::N-1:0] a, output logic [pk::N-1:0] y); assign y = pk::inv(a); endmodule""", "u")
# ---------------- operators and statements
diff_ref("inside", """module ins (input logic [3:0] a, output logic y, output logic z);
  assign y = a inside {1, 3, [8:11]};
  assign z = !(a inside {[0:2], 15});
endmodule""", """module ins (input [3:0] a, output y, output z);
  assign y = (a == 1) || (a == 3) || (a >= 8 && a <= 11);
  assign z = !((a >= 0 && a <= 2) || a == 15);
endmodule""", "ins")
diff("compound assignment operators", """module ops (input logic [7:0] a, b, output logic [7:0] y);
  always_comb begin y = a; y += b; y -= 1; y <<= 1; y ^= 8'h5a; y |= 1; end
endmodule""", "ops")
diff("return at the end of if / else", """module r (input logic [3:0] a, output logic [3:0] y);
  function automatic logic [3:0] f(input logic [3:0] v); if (v > 9) return v - 10; else return v + 1; endfunction
  assign y = f(a);
endmodule""", "r")
diff("function with a loop and int", """module pc (input logic [7:0] a, output logic [3:0] n);
  function automatic int count(input logic [7:0] v); int c; c = 0; for (int i = 0; i < 8; i++) if (v[i]) c++; return c; endfunction
  assign n = count(a);
endmodule""", "pc")
diff("generate with genvar", """module gx (input logic [7:0] a, output logic [7:0] y);
  genvar i;
  generate for (genvar k = 0; k < 8; k++) begin : g assign y[k] = a[7-k]; end endgenerate
endmodule""", "gx")
diff("casting", """module cs (input logic [7:0] a, output logic signed [15:0] y, output logic [3:0] z);
  assign y = signed'(a);
  assign z = 4'(a);
endmodule""", "cs")
diff_ref("end labels and unique if", """module lb (input logic a, b, output logic y);
  always_comb begin : blk
    unique if (a) y = b; else y = 1'b0;
  end : blk
endmodule : lb""", """module lb (input a, b, output reg y);
  always @* begin : blk
    if (a) y = b; else y = 1'b0;
  end
endmodule""", "lb")
diff("named port connections with .name and .*", """module sub (input logic a, b, output logic y); assign y = a ^ b; endmodule
module top (input logic a, b, output logic y);
  logic a2;
  assign a2 = a;
  sub u (.a(a2), .b, .y);
endmodule""", "top")
diff("wildcard port connection", """module sub (input logic a, b, output logic y); assign y = a & b; endmodule
module top2 (input logic a, b, output logic y);
  sub u (.*);
endmodule""", "top2")
diff("typed parameters", """module tp #(parameter int unsigned W = 4, parameter logic [3:0] K = 4'h3) (input logic [W-1:0] a, output logic [W-1:0] y);
  assign y = a + K;
endmodule""", "tp")
# ---------------- macros
out = lower("`define WIDTH 6\n`define MAX(a, b) ((a) > (b) ? (a) : (b))\n`ifdef WIDTH\nmodule m (input logic [`WIDTH-1:0] a, output logic [`MAX(2, 3)-1:0] y);\n`else\nBAD\n`endif\n assign y = a;\nendmodule\n").verilog
ok("[ 6 - 1 : 0 ]" in out and "BAD" not in out and out.count("\n") == 9, "macros, `ifdef and line numbers kept")
diff("macros in a design", """`define W 5
module mc (input logic [`W-1:0] a, output logic [`W-1:0] y); assign y = ~a; endmodule""", "mc")
# ---------------- lines are kept
src = "package p;\n  localparam int N = 2;\nendpackage\n\nmodule m import p::*; (\n  input logic a,\n  output logic y\n);\n  always_comb y = a;\nendmodule\n"
ver = lower(src).verilog.split("\n")
ok(ver[8].startswith("always") or "always" in ver[8], "the always_comb stays on line 9: " + ver[8][:40])

# ---------------- testbenches written in SystemVerilog, run by the section's document
from vibesimulation.systemverilog.document import SvDocument
from vibesimulation.vlsi import simulation
from vibesimulation.vlsi.testbench import testbench_names
def run_tb(design, tb):
    d = SvDocument(); errs = d.new_blank(design); d.set_inputs({}); d.set_testbench(tb)
    res, _ = simulation.run(d); return errs, res
DES = "module counter (input logic clk, rst, output logic [3:0] q);\n  always_ff @(posedge clk) begin if (rst) q <= '0; else q <= q + 1'b1; end\nendmodule\n"
TB = """module tb;
  logic clk = 0, rst = 1;
  logic [3:0] q;
  counter dut (.*);
  always #5 clk = ~clk;
  task automatic check(input logic [3:0] v);
    if (v != 4'd10) $warning("bad %0d", v); else $info("fine %0d", v);
  endtask
  initial begin
    #12 rst = 0;
    #100;
    CHECK
    $finish;
  end
endmodule
"""
def tb_with(code): return TB.replace("CHECK", code)
def show(res): return (res.text + (f" [error: {res.error.msg}]" if res.error else "")).replace("\n", " | ")
errs, res = run_tb(DES, tb_with('assert (q == 4\'d10) else $error("q is %0d", q);\n    $display("reached q=%0d", q);'))
ok(not errs and res.error is None and "reached q=10" in res.text and "ERROR" not in res.text, "a passing assert prints nothing: " + show(res))
errs, res = run_tb(DES, tb_with('assert (q == 4\'d3) else $error("q is %0d", q);'))
ok(res.error is None and "ERROR: q is 10" in res.text, "a failing assert runs $error: " + show(res))
errs, res = run_tb(DES, tb_with('if (q == 10) $fatal(1, "stop at %0d", q);\n    $display("not reached");'))
ok(res.finished and "FATAL: stop at 10" in res.text and "not reached" not in res.text, "$fatal prints and ends the run: " + show(res))
errs, res = run_tb(DES, tb_with("check(q);"))
ok(res.error is None and "INFO: fine 10" in res.text, "a task with $info: " + show(res))
_d = SvDocument(); _d.new_blank(DES)
ok(testbench_names(tb_with("check(q);"), _d.prepare) == ["tb"], "the testbench module is found after lowering")

from vibesimulation.systemverilog import features as _F
ok(sorted(_F.FALLBACK) == _F.FOUND, f"the fallback list names the {len(_F.FOUND)} feature files")
from vibesimulation.systemverilog.feature import REGISTRY
ok(len(REGISTRY.ordered()) == len(_F.FOUND), "every feature file registered exactly one feature")
# ---------------- errors
fails("interface", "interface bus; endinterface", "interface")
fails("class", "class c; endclass", "class")
fails("unpacked struct", "module m; typedef struct { logic a; } s_t; endmodule", "packed")
fails("early return", "module m(input logic [3:0] a, output logic [3:0] y);\n function automatic logic [3:0] f(input logic [3:0] v);\n if (v == 0) return 1;\n y = 3;\n return v;\n endfunction\n assign y = f(a);\nendmodule", "return")
fails("'1 inside a concatenation", "module m(input logic a, output logic [3:0] y);\n assign y = {a, '1};\nendmodule", "'1")
fails("wildcard of unknown module", "module m(input logic a, output logic y);\n nothere u (.*);\nendmodule", "nothere")
fails("include", "`include \"x.svh\"\nmodule m; endmodule", "include")
fails("unknown macro", "module m; wire [`NOPE:0] a; endmodule", "NOPE")
fails("unknown package", "module m import nope::*; (input logic a); endmodule", "nope")
fails("struct field", "module m(input logic [3:0] a, output logic y); typedef struct packed { logic [1:0] p; logic [1:0] q; } s_t; s_t s; assign s = a; assign y = s.zz; endmodule", "zz")
fails("++ inside an expression", "module m(input logic [3:0] a, output logic [3:0] y); logic [3:0] i; assign y = a[i++]; endmodule", "++")
print("ALL OK" if not bad else f"{bad} FAILED"); sys.exit(1 if bad else 0)
