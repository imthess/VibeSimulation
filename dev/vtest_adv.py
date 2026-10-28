"""Newer Verilog features (loops, generate, functions, tasks, memories, wide values, tri-state) against iverilog."""
import sys; sys.path.insert(0, "dev")
from vcheck import compare
T = {}
T["for_popcount"] = ("""module pc(input [11:0] a, output reg [3:0] n, output reg [11:0] r);
 integer i;
 always @* begin
  n = 0;
  for (i = 0; i < 12; i = i + 1) n = n + a[i];
  for (i = 0; i < 12; i = i + 1) r[i] = a[11 - i];
 end
endmodule""", "pc", ())
T["while_loop"] = ("""module w(input [7:0] a, output reg [3:0] lz);
 integer k;
 always @* begin
  lz = 0; k = 7;
  while (k >= 0) begin if (a[k] == 1'b0 && lz == 7 - k) lz = lz + 1; k = k - 1; end
 end
endmodule""", "w", ())
T["repeat_loop"] = ("""module r(input [7:0] a, output reg [7:0] y);
 integer j;
 always @* begin
  y = a;
  repeat (3) y = {y[6:0], y[7]} ^ 8'h1d;
 end
endmodule""", "r", ())
T["func_basic"] = ("""module f(input [7:0] a, b, output [7:0] y, output [3:0] c, output signed [8:0] d);
 function [7:0] maxf(input [7:0] x, input [7:0] z);
  begin if (x > z) maxf = x; else maxf = z; end
 endfunction
 function [3:0] ones(input [7:0] v);
  integer i;
  begin ones = 0; for (i = 0; i < 8; i = i + 1) ones = ones + v[i]; end
 endfunction
 function signed [8:0] sdiff(input signed [7:0] p, input signed [7:0] q);
  sdiff = p - q;
 endfunction
 assign y = maxf(a, b) + 8'd1;
 assign c = ones(a) + ones(b);
 assign d = sdiff(a, b);
endmodule""", "f", ())
T["func_nested_const"] = ("""module g #(parameter N = 20)(input [7:0] a, output [clog(N)-1:0] y, output [7:0] z);
 function integer clog(input integer v);
  integer t;
  begin t = v - 1; clog = 0; while (t > 0) begin clog = clog + 1; t = t >> 1; end end
 endfunction
 function [7:0] twice(input [7:0] v); twice = v << 1; endfunction
 function [7:0] quad(input [7:0] v); quad = twice(twice(v)); endfunction
 assign y = a[clog(N)-1:0];
 assign z = quad(a) + twice(a);
endmodule""", "g", ())
T["task_out"] = ("""module t(input [7:0] a, b, output reg [7:0] s, output reg c, output reg [7:0] d);
 task addc(input [7:0] x, input [7:0] y, output [7:0] sum, output carry);
  reg [8:0] t;
  begin t = x + y; sum = t[7:0]; carry = t[8]; end
 endtask
 always @* begin addc(a, b, s, c); d = a ^ b; end
endmodule""", "t", ())
T["gen_ripple"] = ("""module fa(input a, b, ci, output s, co);
 assign s = a ^ b ^ ci; assign co = (a & b) | (ci & (a ^ b));
endmodule
module add #(parameter N = 6)(input [N-1:0] a, b, input ci, output [N-1:0] s, output co);
 wire [N:0] c;
 assign c[0] = ci;
 genvar i;
 generate
  for (i = 0; i < N; i = i + 1) begin : stage
   fa u(.a(a[i]), .b(b[i]), .ci(c[i]), .s(s[i]), .co(c[i+1]));
  end
 endgenerate
 assign co = c[N];
endmodule""", "add", ())
T["gen_if_case"] = ("""module g #(parameter MODE = 2, W = 5)(input [W-1:0] a, b, output [W-1:0] y, output [W-1:0] z);
 generate
  if (MODE == 1) begin : m1 assign y = a & b; end
  else if (MODE == 2) begin : m2 wire [W-1:0] t; assign t = a | b; assign y = t ^ 1; end
  else begin : m3 assign y = a; end
 endgenerate
 generate
  case (W)
   4: begin : c4 assign z = a + b; end
   5: begin : c5 assign z = a - b; end
   default: begin : cd assign z = 0; end
  endcase
 endgenerate
endmodule""", "g", ())
T["gen_nested_wires"] = ("""module g(input [3:0] a, output [3:0] y, output [3:0] p);
 genvar i, j;
 generate
  for (i = 0; i < 4; i = i + 1) begin : row
   wire t;
   assign t = a[i] ^ a[(i + 1) % 4];
   assign y[i] = t;
  end
  for (j = 0; j < 4; j = j + 1) begin : col
   if (j % 2 == 0) begin : ev assign p[j] = a[j]; end
   else begin : od assign p[j] = ~a[j]; end
  end
 endgenerate
endmodule""", "g", ())
T["ram_single"] = ("""module ram(input clk, we, input [3:0] a, input [7:0] d, output [7:0] q);
 reg [7:0] mem [0:15];
 always @(posedge clk) if (we) mem[a] <= d;
 assign q = mem[a];
endmodule""", "ram", ())
T["ram_syncread"] = ("""module ram(input clk, we, input [2:0] a, input [5:0] d, output reg [5:0] q);
 reg [5:0] mem [0:7];
 always @(posedge clk) begin
  if (we) mem[a] <= d;
  q <= mem[a];
 end
endmodule""", "ram", ())
T["regfile"] = ("""module rf(input clk, we, input [2:0] wa, ra, rb, input [7:0] d, output [7:0] qa, qb);
 reg [7:0] r [0:7];
 always @(posedge clk) if (we) r[wa] <= d;
 assign qa = r[ra];
 assign qb = r[rb];
endmodule""", "rf", ())
T["rom_init"] = ("""module rom(input [2:0] a, output [7:0] q, output [3:0] hi);
 reg [7:0] m [0:7];
 initial begin
  m[0] = 8'h11; m[1] = 8'h22; m[2] = 8'h35; m[3] = 8'hff;
  m[4] = 8'h00; m[5] = 8'h5a; m[6] = 8'ha5; m[7] = 8'h80;
 end
 assign q = m[a];
 assign hi = m[a][7:4];
endmodule""", "rom", ())
T["rom_loop_init"] = ("""module rom(input [3:0] a, output [7:0] q);
 reg [7:0] m [0:9];
 integer i;
 initial for (i = 0; i < 10; i = i + 1) m[i] = i * 7;
 assign q = m[a];
endmodule""", "rom", ())
T["wide64"] = ("""module w(input [63:0] a, b, output [63:0] s, x, output [47:0] m, output lt, output [63:0] sh);
 assign s = a + b;
 assign x = a ^ {b[31:0], b[63:32]};
 assign m = a[47:0] & b[47:0];
 assign lt = a < b;
 assign sh = a << b[5:0];
endmodule""", "w", ())
T["wide40_mul"] = ("""module w(input [39:0] a, input [39:0] b, output [39:0] p, output [39:0] d);
 assign p = a * b;
 assign d = a - b;
endmodule""", "w", ())
T["tri_bus"] = ("""module bus(input e0, e1, input [3:0] a, b, output [3:0] y);
 assign y = e0 ? a : 4'bz;
 assign y = e1 ? b : 4'bz;
endmodule""", "bus", ())
T["dontcare"] = ("""module d(input [1:0] s, input [3:0] a, output reg [3:0] y);
 always @* begin
  case (s)
   2'd0: y = a;
   2'd1: y = ~a;
   2'd2: y = a + 1;
   default: y = 4'bx;
  endcase
 end
endmodule""", "d", ())
T["clocked_for"] = ("""module lf(input clk, rst, input [7:0] d, output reg [7:0] q, output reg [3:0] cnt);
 integer i;
 always @(posedge clk) begin
  if (rst) begin q <= 8'd1; cnt <= 0; end
  else begin
   for (i = 0; i < 3; i = i + 1) cnt <= cnt + d[i];
   q <= {q[6:0], q[7] ^ q[5] ^ q[4] ^ q[3]};
  end
 end
endmodule""", "lf", ())
T["var_partsel_loop"] = ("""module v(input [31:0] a, output reg [7:0] mx);
 integer i;
 always @* begin
  mx = a[7:0];
  for (i = 1; i < 4; i = i + 1) if (a[i*8 +: 8] > mx) mx = a[i*8 +: 8];
 end
endmodule""", "v", ())
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
