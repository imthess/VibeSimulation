"""Testbenches (initial blocks, delays, $display ...) run by our interpreter must print what iverilog prints."""
import subprocess, sys, tempfile, re
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.verilog.tb import run_testbench

T = {}
T["format"] = """module t;
 reg [7:0] a; reg signed [7:0] b; integer i; reg [15:0] w; reg [3:0] n;
 initial begin
  a = 8'd5; b = -8'sd5; i = 42; w = 16'hBEEF; n = 4'b1010;
  $display("[%d] [%0d] [%3d] [%b] [%h] [%o] [%x] [%X]", a, a, a, a, a, a, a, w);
  $display("[%d] [%0d] [%5d]", b, b, b);
  $display("[%d] [%0d] [%b] [%h]", i, i, i, i);
  $display("[%d] [%d] [%d]", 5, 12345, -7);
  $display("[%b] [%h] [%o] [%d]", n, n, n, n);
  $display("[%c] [%s] [%s]", 8'd65, "hi", "abc");
  #7; $display("[%t] [%0t] [%d] [%0d] %m", $time, $time, $time, $time);
  $display("a=%d, b=%d", a, b, " extra", a);
  $display(a, b);
  $write("x"); $write("y\\n");
  $display("%%|%5s|%-5d|%05d|%-6h|", "ab", 7, 7, 8'h1f);
  $displayh(a, w); $displayb(n); $displayo(w);
  $display("done"); $finish;
 end
endmodule"""
T["random"] = """module t; integer s, k;
 initial begin
  $display("%0d %0d %0d", $random, $random, $random);
  s = 5; $display("%0d %0d", $random(s), s);
  s = 100; $display("%0d %0d", $random(s), s);
  for (k = 0; k < 5; k = k + 1) $display("%0d", $random % 100);
  $display("%0d", {$random} % 10);
 end endmodule"""
T["counter_tb"] = """module cnt(input clk, rst, en, output reg [3:0] q);
 always @(posedge clk) if (rst) q <= 0; else if (en) q <= q + 1;
endmodule
module tb;
 reg clk, rst, en; wire [3:0] q; integer i;
 cnt u(.clk(clk), .rst(rst), .en(en), .q(q));
 initial clk = 0;
 always #5 clk = ~clk;
 initial begin
  rst = 1; en = 0; #12; rst = 0; en = 1;
  for (i = 0; i < 20; i = i + 1) begin @(negedge clk); $display("%0t q=%d", $time, q); end
  en = 0; #20; $display("final %d", q);
  $finish;
 end
endmodule"""
T["alu_vectors"] = """module alu(input [7:0] a, b, input [1:0] op, output reg [7:0] y);
 always @* case (op) 0: y = a + b; 1: y = a - b; 2: y = a & b; default: y = a ^ b; endcase
endmodule
module tb;
 reg [7:0] a, b; reg [1:0] op; wire [7:0] y; integer i, errors; reg [7:0] exp;
 alu u(a, b, op, y);
 initial begin
  errors = 0;
  for (i = 0; i < 40; i = i + 1) begin
   a = $random; b = $random; op = i % 4; #1;
   case (op) 0: exp = a + b; 1: exp = a - b; 2: exp = a & b; default: exp = a ^ b; endcase
   if (y !== exp) begin errors = errors + 1; $display("MISMATCH %d %d %d -> %d (want %d)", a, b, op, y, exp); end
   if (i < 6) $display("%h %h %b -> %h", a, b, op, y);
  end
  $display("errors = %0d", errors); $finish;
 end
endmodule"""
T["task_delay"] = """module tb;
 reg [7:0] r; integer k;
 task pulse(input [7:0] v, input integer n, output [7:0] res);
  begin r = v; #n; r = ~v; #n; res = r; end
 endtask
 reg [7:0] out;
 initial begin
  pulse(8'h0f, 3, out); $display("%0t %h %h", $time, r, out);
  for (k = 1; k < 4; k = k + 1) begin pulse(k, k, out); $display("%0t %h %h", $time, r, out); end
  $finish;
 end
endmodule"""
T["func_in_tb"] = """module tb;
 function [7:0] rev(input [7:0] x); integer i; begin for (i = 0; i < 8; i = i + 1) rev[i] = x[7 - i]; end endfunction
 function integer fact(input integer n); integer j; begin fact = 1; for (j = 2; j <= n; j = j + 1) fact = fact * j; end endfunction
 reg [7:0] v; integer q;
 initial begin
  v = 8'b1100_0001; $display("%b %b", v, rev(v));
  for (q = 0; q < 8; q = q + 1) $display("%0d! = %0d", q, fact(q));
 end
endmodule"""
T["arrays_tb"] = """module tb;
 reg [7:0] vec [0:7]; reg [7:0] sum; integer i;
 initial begin
  for (i = 0; i < 8; i = i + 1) vec[i] = i * i + 1;
  sum = 0;
  for (i = 0; i < 8; i = i + 1) sum = sum + vec[i];
  $display("sum=%0d vec3=%0d", sum, vec[3]);
  vec[2] <= 8'hAA; $display("before %h", vec[2]); #1; $display("after %h", vec[2]);
 end
endmodule"""
T["nonblocking_order"] = """module tb;
 reg a, b, c; reg [3:0] x, y;
 initial begin
  a = 0; b = 1; x = 3; y = 9;
  a <= b; b <= a; $display("%b %b", a, b); #1; $display("%b %b", a, b);
  x <= y; y <= x; #1 $display("%0d %0d", x, y);
  c = 0; c <= #5 1; $display("c=%b", c); #4 $display("c=%b", c); #1 $display("c=%b", c);
 end
endmodule"""
T["wait_events"] = """module tb;
 reg go; reg [3:0] n; reg clk; integer cnt;
 initial begin clk = 0; go = 0; n = 0; cnt = 0; end
 always #2 clk = ~clk;
 always @(posedge clk) if (go) begin n <= n + 1; end
 initial begin #7 go = 1; wait (n == 5); $display("n reached 5 at %0t", $time); go = 0; #10 $display("n stays %0d", n); $finish; end
 always @(n) cnt = cnt + 1;
 initial begin #50 $display("changes %0d", cnt); end
endmodule"""
T["monitor_strobe"] = """module tb;
 reg [3:0] a, b; wire [4:0] s; assign s = a + b;
 initial begin
  $monitor("%0t a=%d b=%d s=%d", $time, a, b, s);
  a = 1; b = 2; #3 a = 5; #3 b = 9; #3 a = 5; #1 $strobe("strobe %0d", s); b = 0; #5 $finish;
 end
endmodule"""
T["casez_tb"] = """module tb; reg [3:0] v; integer i;
 initial for (i = 0; i < 16; i = i + 1) begin v = i;
   casez (v) 4'b1???: $write("A"); 4'b01??: $write("B"); 4'b001?: $write("C"); default: $write("D"); endcase
   if (i == 15) $write("\\n");
 end endmodule"""
T["fsm_tb"] = """module seq(input clk, rst, x, output reg y);
 reg [1:0] s;
 always @(posedge clk) if (rst) begin s <= 0; y <= 0; end
  else begin y <= 0; case (s) 0: s <= x ? 1 : 0; 1: s <= x ? 1 : 2; 2: begin s <= x ? 3 : 0; end 3: begin s <= x ? 1 : 2; y <= 1; end endcase end
endmodule
module tb; reg clk = 0, rst = 1, x = 0; wire y; reg [15:0] pat; integer i;
 seq u(clk, rst, x, y);
 always #5 clk = ~clk;
 initial begin pat = 16'b1011_0110_1101_1011; #12 rst = 0;
  for (i = 15; i >= 0; i = i - 1) begin x = pat[i]; @(negedge clk); $write("%b", y); end
  $write("\\n"); $finish; end
endmodule"""
T["wide_tb"] = """module tb; reg [63:0] a; reg [39:0] b; reg signed [15:0] s; initial begin
  a = 64'hDEAD_BEEF_0123_4567; b = a[39:0] * 3; s = -16'sd1234;
  $display("%h %h %0d %d", a, b, s, s);
  $display("%0d %b", a % 1000, b[7:0]); $display("%h", a >> 12);
  a = {a[31:0], a[63:32]}; $display("%h", a); end endmodule"""
T["ram_tb"] = """module ram(input clk, we, input [3:0] a, input [7:0] d, output [7:0] q);
 reg [7:0] mem [0:15];
 always @(posedge clk) if (we) mem[a] <= d;
 assign q = mem[a];
endmodule
module tb; reg clk = 0, we = 0; reg [3:0] a; reg [7:0] d; wire [7:0] q; integer i;
 ram u(clk, we, a, d, q);
 always #5 clk = ~clk;
 initial begin
  for (i = 0; i < 16; i = i + 1) begin @(negedge clk); we = 1; a = i; d = i * 17; end
  @(negedge clk); we = 0;
  for (i = 15; i >= 0; i = i - 3) begin a = i; #1 $display("mem[%0d] = %h", i, q); end
  $finish;
 end
endmodule"""
T["repeat_forever"] = """module tb; reg clk = 0; integer n = 0;
 initial forever begin #3 clk = ~clk; if (clk) n = n + 1; if (n == 4) begin $display("n=%0d at %0t", n, $time); $finish; end end
 initial repeat (3) begin @(posedge clk); $display("edge at %0t", $time); end
endmodule"""
T["negatives"] = """module tb; reg signed [7:0] a; reg signed [15:0] b; integer i; initial begin
  a = -8'sd100; b = a * 3; $display("%0d %0d %d %h %b", a, b, a, b, a);
  a = a >>> 2; $display("%0d", a); b = {{8{a[7]}}, a}; $display("%0d %h", b, b);
  i = -12345; $display("%0d %h %o", i, i, i); $display("%0d", i / 100); $display("%0d", i % 100);
  $display("%0d", -7 / 2); $display("%0d", $signed(8'hF0) / 3);
 end endmodule"""
T["shiftreg_wires"] = """module sr(input clk, d, output [3:0] q); reg [3:0] s; initial s = 0; assign q = s; always @(posedge clk) s <= {s[2:0], d}; endmodule
module tb; reg clk = 0, d = 0; wire [3:0] q; sr u(clk, d, q); always #4 clk = ~clk;
 initial begin $monitor("%0t d=%b q=%b", $time, d, q); #1 d = 1; #8 d = 0; #8 d = 1; #8 d = 1; #20 $finish; end
endmodule"""
T["disable_and_loops"] = """module tb; integer i, j, c;
 initial begin
  c = 0;
  for (i = 0; i < 5; i = i + 1) for (j = 0; j < i; j = j + 1) c = c + j * i;
  $display("c=%0d", c);
  begin : blk
   for (i = 0; i < 100; i = i + 1) if (i * i > 200) begin $display("first %0d", i); disable blk; end
  end
  while (c > 3) c = c / 2; $display("c=%0d", c);
 end endmodule"""
T["gate_tb"] = """module tb; reg a, b, c; wire y, z; nand g1(y, a, b); xor g2(z, y, c);
 integer k;
 initial begin for (k = 0; k < 8; k = k + 1) begin {a, b, c} = k; #1 $display("%b%b%b -> %b %b", a, b, c, y, z); end end
endmodule"""
only = sys.argv[1:]
bad = 0
for name, src in T.items():
    if only and name not in only: continue
    d = tempfile.mkdtemp(); open(d + "/t.v", "w").write(src)
    top = "tb" if "module tb" in src else "t"
    p = subprocess.run(["iverilog", "-g2005", "-s", top, "-o", d + "/x", d + "/t.v"], capture_output=True, text=True)
    if p.returncode: print("IVERILOG ERR", name, p.stderr[:300]); bad += 1; continue
    exp = [l for l in subprocess.run(["vvp", d + "/x"], capture_output=True, text=True).stdout.splitlines() if "$finish called" not in l]
    r = run_testbench(src)
    if r.error: print("FAIL", name, "error:", r.error, "line", getattr(r.error, "line", "")); bad += 1; continue
    got = r.lines
    if got == exp: print("ok  ", name, f"({len(exp)} lines)")
    else:
        bad += 1; print("BAD ", name)
        for i in range(max(len(got), len(exp))):
            a = got[i] if i < len(got) else "<none>"; b = exp[i] if i < len(exp) else "<none>"
            if a != b: print(f"   line {i}: ours {a!r}\n            iverilog {b!r}"); break
print("failures:", bad)
