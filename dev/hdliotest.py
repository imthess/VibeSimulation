"""Verilog / SystemVerilog input-output check on a corpus of sample designs written independently of the feature tests:
 1. the ports the program finds (names, directions, widths) equal the ports written in the source;
 2. every output of the elaborated circuit equals what iverilog computes, for random inputs (combinational and clocked designs).
Run:  python3 dev/hdliotest.py"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
from vibesimulation.workspaces.logisim.components import load_all; load_all()
from vcheck import compare
from svcheck import check
from vibesimulation.workspaces.verilog.core.elab import elaborate
from vibesimulation.workspaces.systemverilog.core.compiler import lower
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)

def declared(src, top):
    """{name: (dir, width)} from the module header / ANSI port list of `top` (simple regex, enough for these samples)."""
    m = re.search(r"module\s+" + top + r"\b(?:\s*#\s*\((.*?)\))?\s*\((.*?)\)\s*;", src, re.S); params = {}
    for p in re.findall(r"parameter\s+(?:int\s+|integer\s+)?(\w+)\s*=\s*(\d+)", m.group(1) or ""): params[p[0]] = int(p[1])
    out, d, w = {}, None, 1
    for part in re.split(r",(?![^\[]*\])", m.group(2)):
        t = part.strip()
        if not t: continue
        dm = re.match(r"(input|output|inout)\b", t)
        if dm:
            d = dm.group(1); rng = re.search(r"\[\s*([^:\]]+?)\s*:\s*0\s*\]", t); w = 1
            if rng: w = eval(rng.group(1), {}, dict(params)) + 1
        out[re.findall(r"\w+", t)[-1]] = (d, w)
    return out

def ports_ok(name, src, top, sv=False, want=None):
    v = lower(src).verilog if sv else src
    circs, _, _ = elaborate(v, top); c = dict(circs)[top]
    got = {p.name: ("input", p.width) for p in c.inputs}; got.update({p.name: ("output", p.width) for p in c.outputs})
    want = want or declared(src, top)
    ok(got == want, f"{name}: ports {len(want)} match the source" if got == want else f"{name}: ports differ: program {got} source {want}")

def run(name, src, top, sv=False, resets=(), nvec=120, seed=3, want=None, ref=None):
    """ref: hand-written Verilog for SystemVerilog that iverilog itself cannot run (compared instead of the SystemVerilog source)."""
    try:
        ports_ok(name, src, top, sv, want)
        if ref: m, n = compare(lower(src).verilog, top, nvec, seed, resets=list(resets), ref_src=ref)
        else: m, n = (check(src, top, nvec=nvec, seed=seed, resets=list(resets)) if sv else compare(src, top, nvec, seed, resets=list(resets)))
    except Exception as e: ok(False, f"{name}: {type(e).__name__}: {str(e)[:200]}"); return
    ok(m == 0 and n > 0, f"{name}: {n} output values agree with iverilog" if m == 0 else f"{name}: {m} of {n} differ")

def refused(name, src, top, word, sv=False):
    """A construct the program does not support must be refused with a clear message and a line number, never turned into a wrong circuit."""
    from vibesimulation.workspaces.verilog.core.lexer import VError
    try: elaborate(lower(src).verilog if sv else src, top); ok(False, f"{name}: should have been refused")
    except VError as e: ok(word.lower() in e.msg.lower() and e.line >= 1, f"{name}: refused cleanly (line {e.line}): {e.msg[:75]}")
    except Exception as e: ok(False, f"{name}: crashed instead of a clear message: {type(e).__name__}: {e}")

# ------------------------------------------------------------------ Verilog
V = {}
V["gates"] = ("g", """module g (input a, b, c, output y1, y2, y3, y4, y5);
  and (y1, a, b, c); or (y2, a, b); xor (y3, a, b, c); nand (y4, a, b); xnor (y5, a, c);
endmodule""")
V["mux4"] = ("mux4", """module mux4 (input [7:0] d0, d1, d2, d3, input [1:0] s, output reg [7:0] y);
  always @* case (s) 2'd0: y = d0; 2'd1: y = d1; 2'd2: y = d2; default: y = d3; endcase
endmodule""")
V["adder8"] = ("add8", """module add8 (input [7:0] a, b, input cin, output [7:0] sum, output cout);
  assign {cout, sum} = a + b + cin;
endmodule""")
V["subcmp"] = ("subcmp", """module subcmp (input [5:0] a, b, output [5:0] d, output lt, eq, gt);
  assign d = a - b; assign lt = a < b; assign eq = a == b; assign gt = a > b;
endmodule""")
V["decoder"] = ("dec", """module dec (input [2:0] a, input en, output [7:0] y);
  assign y = en ? (8'b1 << a) : 8'b0;
endmodule""")
V["prio_enc"] = ("penc", """module penc (input [7:0] r, output reg [2:0] y, output reg v);
  integer i;
  always @* begin y = 0; v = 0; for (i = 0; i < 8; i = i + 1) if (r[i]) begin y = i[2:0]; v = 1; end end
endmodule""")
V["reduction"] = ("red", """module red (input [7:0] a, output p, output all1, output any1, output n);
  assign p = ^a; assign all1 = &a; assign any1 = |a; assign n = ~|a;
endmodule""")
V["concat_rep"] = ("cr", """module cr (input [3:0] a, input [1:0] b, output [11:0] y, output [7:0] z);
  assign y = {a, b, a[1:0], {4{b[0]}}}; assign z = {2{a}};
endmodule""")
V["shifts"] = ("sh", """module sh (input [7:0] a, input [2:0] n, output [7:0] l, r, output [7:0] rot);
  assign l = a << n; assign r = a >> n; assign rot = (a << n) | (a >> (8 - n));
endmodule""")
V["param_width"] = ("pw", """module pw #(parameter W = 6) (input [W-1:0] a, b, output [W-1:0] y, output [W:0] s);
  assign y = a & ~b; assign s = a + b;
endmodule""")
V["function"] = ("fn", """module fn (input [7:0] a, output [3:0] ones, output [7:0] rev);
  function [3:0] cnt; input [7:0] x; integer i; begin cnt = 0; for (i = 0; i < 8; i = i + 1) cnt = cnt + x[i]; end endfunction
  assign ones = cnt(a);
  genvar k; generate for (k = 0; k < 8; k = k + 1) begin : g assign rev[k] = a[7-k]; end endgenerate
endmodule""")
V["ternary_chain"] = ("tc", """module tc (input [3:0] a, output [1:0] grade);
  assign grade = a > 12 ? 2'd3 : a > 8 ? 2'd2 : a > 4 ? 2'd1 : 2'd0;
endmodule""")
V["alu"] = ("alu", """module alu (input [7:0] a, b, input [2:0] op, output reg [7:0] y, output z);
  always @* begin
    case (op) 3'd0: y = a + b; 3'd1: y = a - b; 3'd2: y = a & b; 3'd3: y = a | b; 3'd4: y = a ^ b; 3'd5: y = ~a; 3'd6: y = a << 1; default: y = a >> 1; endcase
  end
  assign z = (y == 8'd0);
endmodule""")
V["bitslice"] = ("bs", """module bs (input [15:0] w, input [1:0] i, output [3:0] nib, output msb, output [3:0] hi);
  assign nib = w[7:4]; assign msb = w[15]; assign hi = w[15:12];
endmodule""")
V["counter"] = ("cnt", """module cnt (input clk, rst, en, output reg [3:0] q, output tc);
  always @(posedge clk or posedge rst) if (rst) q <= 0; else if (en) q <= q + 1;
  assign tc = &q;
endmodule""", [("rst", 1)])
V["shiftreg"] = ("sr", """module sr (input clk, rst, d, output reg [7:0] q, output out);
  always @(posedge clk) if (rst) q <= 0; else q <= {q[6:0], d};
  assign out = q[7];
endmodule""", [("rst", 1)])
V["dff_en"] = ("dffe", """module dffe (input clk, rstn, en, input [3:0] d, output reg [3:0] q);
  always @(posedge clk or negedge rstn) if (!rstn) q <= 4'h0; else if (en) q <= d;
endmodule""", [("rstn", 0)])
V["fsm_seq"] = ("fsm", """module fsm (input clk, rst, x, output y);
  parameter S0 = 2'd0, S1 = 2'd1, S2 = 2'd2, S3 = 2'd3;
  reg [1:0] s, n;
  always @(posedge clk or posedge rst) if (rst) s <= S0; else s <= n;
  always @* case (s) S0: n = x ? S1 : S0; S1: n = x ? S1 : S2; S2: n = x ? S3 : S0; S3: n = x ? S1 : S2; default: n = S0; endcase
  assign y = (s == S3);
endmodule""", [("rst", 1)])
V["lfsr"] = ("lfsr", """module lfsr (input clk, rst, output [7:0] q);
  reg [7:0] r; wire fb = r[7] ^ r[5] ^ r[4] ^ r[3];
  always @(posedge clk) if (rst) r <= 8'h01; else r <= {r[6:0], fb};
  assign q = r;
endmodule""", [("rst", 1)])
V["hier"] = ("top", """module ha (input a, b, output s, c); assign s = a ^ b; assign c = a & b; endmodule
module fa (input a, b, ci, output s, co); wire s1, c1, c2; ha h1 (a, b, s1, c1); ha h2 (s1, ci, s, c2); assign co = c1 | c2; endmodule
module top (input [3:0] a, b, input cin, output [3:0] s, output cout);
  wire [4:0] c; assign c[0] = cin;
  fa f0 (a[0], b[0], c[0], s[0], c[1]); fa f1 (a[1], b[1], c[1], s[1], c[2]);
  fa f2 (a[2], b[2], c[2], s[2], c[3]); fa f3 (a[3], b[3], c[3], s[3], c[4]);
  assign cout = c[4];
endmodule""")
V["mem_rom"] = ("rom", """module rom (input [2:0] a, output reg [7:0] d);
  always @* case (a) 0: d = 8'h3F; 1: d = 8'h06; 2: d = 8'h5B; 3: d = 8'h4F; 4: d = 8'h66; 5: d = 8'h6D; 6: d = 8'h7D; default: d = 8'h07; endcase
endmodule""")
V["gray"] = ("gray", """module gray (input [5:0] b, output [5:0] g, output [5:0] back);
  assign g = b ^ (b >> 1);
  assign back[5] = g[5]; assign back[4] = back[5] ^ g[4]; assign back[3] = back[4] ^ g[3]; assign back[2] = back[3] ^ g[2]; assign back[1] = back[2] ^ g[1]; assign back[0] = back[1] ^ g[0];
endmodule""")
for k, v in V.items(): run("Verilog " + k, v[1], v[0], resets=(v[2] if len(v) > 2 else ()))

# ------------------------------------------------------------------ SystemVerilog
S = {}
S["alu_comb"] = ("alu", """module alu (input logic [7:0] a, b, input logic [1:0] op, output logic [7:0] y, output logic c);
  always_comb begin
    c = 1'b0; y = '0;
    unique case (op)
      2'd0: {c, y} = a + b;
      2'd1: y = a - b;
      2'd2: y = a & b;
      2'd3: y = a ^ b;
    endcase
  end
endmodule""")
S["enum_fsm"] = ("fsm", """typedef enum logic [1:0] {IDLE, RUN, DONE, ERR} state_t;
module fsm (input logic clk, rst, go, fail, output logic busy, output logic [1:0] code);
  state_t s, n;
  always_ff @(posedge clk or posedge rst) if (rst) s <= IDLE; else s <= n;
  always_comb begin
    n = s;
    case (s) IDLE: if (go) n = RUN; RUN: if (fail) n = ERR; else n = DONE; DONE: n = IDLE; ERR: n = IDLE; default: n = IDLE; endcase
  end
  assign busy = (s == RUN); assign code = s;
endmodule""", [("rst", 1)])
S["struct_pack"] = ("sp", """typedef struct packed { logic [3:0] hi; logic [3:0] lo; } byte_t;
module sp (input byte_t a, output byte_t swapped, output logic [4:0] sum);
  always_comb begin swapped.hi = a.lo; swapped.lo = a.hi; end
  assign sum = a.hi + a.lo;
endmodule""", [], {"a": ("input", 8), "swapped": ("output", 8), "sum": ("output", 5)})
S["param_counter"] = ("pc", """module pc #(parameter int W = 5) (input logic clk, rst, up, output logic [W-1:0] q, output logic wrap);
  always_ff @(posedge clk) if (rst) q <= '0; else q <= up ? q + 1'b1 : q - 1'b1;
  assign wrap = up ? &q : ~|q;
endmodule""", [("rst", 1)])
S["for_loop"] = ("pop", """module pop (input logic [11:0] a, output logic [3:0] n, output logic [11:0] r);
  always_comb begin n = '0; for (int i = 0; i < 12; i++) begin n += a[i]; r[11-i] = a[i]; end end
endmodule""")
S["inside_op"] = ("ins", """module ins (input logic [3:0] a, output logic hit, output logic vowelish);
  assign hit = a inside {[4'd3:4'd6], 4'd9};
  assign vowelish = a inside {4'd1, 4'd5, 4'd9, 4'd13};
endmodule""", [], None, """module ins (input [3:0] a, output hit, output vowelish);
  assign hit = (a >= 3 && a <= 6) || a == 9;
  assign vowelish = a == 1 || a == 5 || a == 9 || a == 13;
endmodule""")
S["always_ff_en"] = ("reg4", """module reg4 (input logic clk, rst, en, input logic [3:0] d, output logic [3:0] q, output logic same);
  always_ff @(posedge clk) begin if (rst) q <= '0; else if (en) q <= d; end
  assign same = (q == d);
endmodule""", [("rst", 1)])
S["compound"] = ("acc", """module acc (input logic clk, rst, input logic [3:0] x, output logic [7:0] sum);
  always_ff @(posedge clk) if (rst) sum <= '0; else sum += x;
endmodule""", [("rst", 1)])
S["fill_ops"] = ("fo", """module fo (input logic [7:0] a, output logic [7:0] ones, zeros, mix);
  assign ones = '1; assign zeros = '0; assign mix = a & '1 | 8'h0;
endmodule""")
S["typedef_logic"] = ("td", """typedef logic [5:0] word_t;
module td (input word_t a, b, output word_t y, output logic eq);
  assign y = (a > b) ? a : b; assign eq = (a == b);
endmodule""", [], {"a": ("input", 6), "b": ("input", 6), "y": ("output", 6), "eq": ("output", 1)})
S["package_import"] = ("pk", """package defs; localparam int K = 3; typedef logic [3:0] nib_t; endpackage
module pk import defs::*; (input nib_t a, output nib_t y);
  assign y = ~a;
endmodule""", [], {"a": ("input", 4), "y": ("output", 4)})
S["nested_hier"] = ("top", """module inv #(parameter int W = 4) (input logic [W-1:0] a, output logic [W-1:0] y); assign y = ~a; endmodule
module top (input logic [3:0] a, b, output logic [3:0] y, output logic z);
  logic [3:0] na, nb;
  inv #(4) u1 (.a(a), .y(na)); inv #(4) u2 (.a(b), .y(nb));
  assign y = na & nb; assign z = |y;
endmodule""")
S["decoder_case"] = ("dec2", """module dec2 (input logic [1:0] a, input logic en, output logic [3:0] y);
  always_comb begin y = '0; if (en) case (a) 2'd0: y = 4'b0001; 2'd1: y = 4'b0010; 2'd2: y = 4'b0100; default: y = 4'b1000; endcase end
endmodule""")
S["shift_sv"] = ("shs", """module shs (input logic clk, rst, ld, input logic [7:0] d, output logic [7:0] q);
  always_ff @(posedge clk) if (rst) q <= '0; else if (ld) q <= d; else q <= {q[0], q[7:1]};
endmodule""", [("rst", 1)])
S["int_arith"] = ("ia", """module ia (input logic [7:0] a, b, output logic [15:0] p, output logic [7:0] q, r);
  assign p = a * b; assign q = (b == 0) ? 8'hFF : a / b; assign r = (b == 0) ? 8'h00 : a % b;
endmodule""")
for k, v in S.items(): run("SystemVerilog " + k, v[1], v[0], sv=True, resets=(v[2] if len(v) > 2 else ()), want=(v[3] if len(v) > 3 else None), ref=(v[4] if len(v) > 4 else None))

# ------------------------------------------------------------------ constructs the program refuses (must be a clear message, never a wrong circuit)
refused("Verilog variable part select", """module bs (input [15:0] w, input [1:0] i, output [3:0] sel); assign sel = w[i*4 +: 4]; endmodule""", "bs", "part select")
refused("Verilog reset to a non-zero value", """module r (input clk, rstn, output reg [3:0] q);
  always @(posedge clk or negedge rstn) if (!rstn) q <= 4'hA; else q <= q + 1; endmodule""", "r", "resets to")
refused("SystemVerilog bit chosen by a variable", """module d (input logic [1:0] a, output logic [3:0] y); always_comb begin y = '0; y[a] = 1'b1; end endmodule""", "d", "variable index", sv=True)
refused("SystemVerilog '{} inside an expression", """typedef struct packed {logic [3:0] hi, lo;} t; module m (input t a, output t y); assign y = '{hi: a.lo, lo: a.hi}; endmodule""", "m", "not supported", sv=True)
refused("SystemVerilog scoped type in a port", """package p; typedef logic [3:0] n_t; endpackage module m (input p::n_t a, output p::n_t y); assign y = a; endmodule""", "m", "not supported", sv=True)

print("ALL OK" if bad == 0 else f"{bad} FAILED"); sys.exit(1 if bad else 0)
