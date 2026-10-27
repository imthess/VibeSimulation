import sys; sys.path.insert(0, "dev")
from vcheck import compare
T = {}
T["alu_case"] = ("""module alu(input [7:0] a, b, input [2:0] op, output reg [7:0] y, output reg z);
 always @* begin
  case (op)
   3'd0: y = a + b;
   3'd1: y = a - b;
   3'd2, 3'd3: y = a & b;
   3'd4: y = a | b;
   3'd5: y = a ^ b;
   3'd6: y = a << 1;
   default: y = ~a;
  endcase
  z = (y == 8'd0);
 end
endmodule""", "alu", ())
T["ifelse_default"] = ("""module m(input [3:0] a, input s, t, output reg [3:0] y, output reg [1:0] p);
 always @(a or s or t) begin
  y = 4'd0; p = 2'b00;
  if (s) begin y = a; if (t) p = 2'b11; else p = 2'b01; end
  else if (t) y = a + 4'd1;
 end
endmodule""", "m", ())
T["casez_prio"] = ("""module pe(input [3:0] r, output reg [1:0] y, output reg v);
 always @* begin
  v = 1'b1;
  casez (r)
   4'b1???: y = 2'd3;
   4'b01??: y = 2'd2;
   4'b001?: y = 2'd1;
   4'b0001: y = 2'd0;
   default: begin y = 2'd0; v = 1'b0; end
  endcase
 end
endmodule""", "pe", ())
T["partial"] = ("""module m(input [3:0] a, b, output [7:0] y, output [3:0] z);
 wire [3:0] t;
 assign y[3:0] = a;
 assign y[7:4] = b;
 assign {z[1:0], z[3:2]} = {a[0], b[1:0], a[3]};
 assign t = a;
endmodule""", "m", ())
T["gates"] = ("""module g(input a, b, c, output y1, y2, y3, y4);
 and u1(y1, a, b, c);
 wire n;
 nor u2(n, a, b);
 xor u3(y2, n, c, a);
 not (y3, c);
 xnor u4(y4, a, b);
endmodule""", "g", ())
T["counter_sync"] = ("""module cnt(input clk, rst, en, output reg [3:0] q);
 always @(posedge clk) begin
  if (rst) q <= 4'd0;
  else if (en) q <= q + 4'd1;
 end
endmodule""", "cnt", ())
T["counter_async"] = ("""module cnt(input clk, rst_n, en, output reg [3:0] q, output tc);
 assign tc = (q == 4'd15);
 always @(posedge clk or negedge rst_n) begin
  if (!rst_n) q <= 4'd0;
  else if (en) q <= q + 4'd1;
 end
endmodule""", "cnt", (("rst_n", 0),))
T["dff_pre"] = ("""module d(input clk, pre, d, output reg q, output reg r);
 always @(posedge clk or posedge pre) if (pre) q <= 1'b1; else q <= d;
 always @(negedge clk) r <= q ^ d;
endmodule""", "d", (("pre", 1),))
T["shiftreg"] = ("""module sr(input clk, rst, d, output [3:0] q);
 reg [3:0] s;
 assign q = s;
 always @(posedge clk) if (rst) s <= 0; else s <= {s[2:0], d};
endmodule""", "sr", ())
T["fsm"] = ("""module fsm(input clk, rst, x, output reg y, output [1:0] st);
 reg [1:0] s, ns;
 assign st = s;
 always @(posedge clk) if (rst) s <= 2'd0; else s <= ns;
 always @* begin
  ns = s; y = 1'b0;
  case (s)
   2'd0: if (x) ns = 2'd1;
   2'd1: begin if (x) ns = 2'd2; else ns = 2'd0; end
   2'd2: begin y = 1'b1; if (!x) ns = 2'd0; end
   default: ns = 2'd0;
  endcase
 end
endmodule""", "fsm", ())
T["blocking_seq"] = ("""module b(input clk, rst, input [3:0] a, output reg [3:0] q, output reg [3:0] r);
 reg [3:0] t;
 always @(posedge clk) begin
  if (rst) begin q <= 0; r <= 0; end
  else begin t = a + 4'd1; q <= t; r <= q; end
 end
endmodule""", "b", ())
T["hier"] = ("""module add4(input [3:0] a, b, input ci, output [3:0] s, output co);
 assign {co, s} = a + b + ci;
endmodule
module top(input [7:0] a, b, output [7:0] s, output co);
 wire c0;
 add4 lo(.a(a[3:0]), .b(b[3:0]), .ci(1'b0), .s(s[3:0]), .co(c0));
 add4 hi(a[7:4], b[7:4], c0, s[7:4], co);
endmodule""", "top", ())
T["param"] = ("""module sh #(parameter N = 4, parameter K = 1)(input [N-1:0] a, output [N-1:0] y, output p);
 assign y = (a << K) | (a >> (N - K));
 assign p = ^a;
endmodule
module top(input [5:0] a, output [5:0] y, output p);
 sh #(.N(6), .K(2)) u(.a(a), .y(y), .p(p));
endmodule""", "top", ())
T["nonansi"] = ("""module m(a, b, y, z);
 input [3:0] a; input [3:0] b; output [3:0] y; output z;
 reg [3:0] y;
 always @(a or b) y = a & b;
 assign z = |y;
endmodule""", "m", ())
T["signed_cmp"] = ("""module m(input signed [3:0] a, b, output lt, output signed [7:0] x, output [7:0] u, output [3:0] sr);
 assign lt = a < b;
 assign x = a * b;
 assign u = a + 8'd1;
 assign sr = a >>> 1;
endmodule""", "m", ())

T["swap_nb"] = ("""module sw(input clk, rst, input [2:0] a, b, output reg [2:0] x, y);
 always @(posedge clk) if (rst) begin x <= a; y <= b; end else begin x <= y; y <= x; end
endmodule""", "sw", ())
T["partial_always"] = ("""module pa(input [3:0] a, input s, output reg [7:0] y);
 always @* begin
  y = 8'd0;
  y[3:0] = a;
  if (s) y[7:4] = ~a;
  y[7] = y[7] ^ s;
 end
endmodule""", "pa", ())
T["negedge_async_vec"] = ("""module na(input clk, arst, input [4:0] d, input en, output reg [4:0] q, output reg [4:0] p);
 always @(negedge clk or negedge arst) begin
  if (!arst) begin q <= 5'd0; p <= 5'd0; end
  else begin if (en) q <= d; p <= p + q; end
 end
endmodule""", "na", (("arst", 0),))
T["ternary_chain"] = ("""module t(input [1:0] s, input [3:0] a, b, c, d, output [3:0] y, output signed [4:0] z);
 assign y = s == 2'd0 ? a : s == 2'd1 ? b : s == 2'd2 ? c : d;
 assign z = $signed(a) - $signed(b);
endmodule""", "t", ())
T["wide_logic"] = ("""module w(input [15:0] a, b, output [15:0] y, output p, output [15:0] sh, output [15:0] m);
 assign y = (a & ~b) | (~a & b);
 assign p = ^a & |b;
 assign sh = (a << b[3:0]) ^ (a >> b[7:4]);
 assign m = a * b[3:0] + (a % (b[7:0] | 8'd1));
endmodule""", "w", ())
T["gate_arrays_mix"] = ("""module g(input [3:0] a, output [3:0] y, output z);
 wire t;
 and (t, a[0], a[1]);
 or  (y[0], t, a[2]);
 assign y[3:1] = a[3:1] ^ {3{t}};
 assign z = ~(a[0] | a[3]);
endmodule""", "g", ())
bad_total = 0
only = sys.argv[1:] 
for name, (src, top, rs) in T.items():
    if only and name not in only: continue
    try:
        bad, n = compare(src, top, nvec=80, resets=rs)
    except Exception as e:
        import traceback; traceback.print_exc(); print("FAIL", name, "->", repr(e)[:300]); bad_total += 1; continue
    print(("ok  " if not bad else "BAD ") + name, f"({n} values compared)"); bad_total += bool(bad)
print("failures:", bad_total)
