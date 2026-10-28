"""Built-in SystemVerilog examples (registered in the same list as the others)."""
from ..systemverilog.samples import SAMPLE
from .examples import add

add("systemverilog", "traffic", "Traffic light with an enum", "Beginner", "A state machine whose states are named with an enum.",
    ("The enum members become constants and the state register is only 2 bits wide.",
     "Two always_comb blocks: one picks the next state, one drives the lamps.",
     "Play the truth table: step the clock and watch the state change when `car` is 1."),
    SAMPLE)
add("systemverilog", "alu", "ALU with unique case", "Intermediate", "logic ports, a parameter with a type and the '0 / '1 fill literals.",
    ("'1 and '0 take the width of the signal they are assigned to.",
     "`unique case` is accepted: the case behaves as written (a note appears in Problems).",
     "Change the parameter W and the whole circuit changes width."),
    "module alu #(parameter int W = 8) (\n  input  logic [W-1:0] a, b,\n  input  logic [2:0] op,\n  output logic [W-1:0] y,\n  output logic zero\n);\n"
    "  always_comb begin\n    unique case (op)\n      3'd0: y = a + b;\n      3'd1: y = a - b;\n      3'd2: y = a & b;\n      3'd3: y = a | b;\n      3'd4: y = a ^ b;\n"
    "      3'd5: y = a << 1;\n      3'd6: y = '1;\n      default: y = '0;\n    endcase\n  end\n  assign zero = (y == '0);\nendmodule\n")
add("systemverilog", "pack", "Package and packed struct", "Advanced", "A package with a type, a constant and a function, and a struct that is one vector.",
    ("The package is copied into the module that imports it.",
     "`p.hi` and `p.lo` become bit slices of one 8-bit vector.",
     "The function's `return` becomes an assignment to its name."),
    "package util;\n  localparam int N = 4;\n  typedef struct packed {\n    logic [N-1:0] hi;\n    logic [N-1:0] lo;\n  } pair_t;\n"
    "  function automatic logic [N-1:0] inc(input logic [N-1:0] v);\n    return v + 1;\n  endfunction\nendpackage\n\n"
    "module swap_inc import util::*; (\n  input  pair_t p,\n  output pair_t q\n);\n  assign q.hi = inc(p.lo);\n  assign q.lo = p.hi;\nendmodule\n")
add("systemverilog", "counter_tb", "Counter with an assertion testbench", "Intermediate", "always_ff, ++ and a testbench that checks itself with assert.",
    ("Press Run: the testbench counts, then asserts the value; a failure would print an ERROR line.",
     "Open the Test tab to see assert (...) else $error(...).",
     "Change `q + 1'b1` to `q + 2'd2` and run again: the assertion fails and says so."),
    "module counter (\n  input  logic clk,\n  input  logic rst,\n  output logic [3:0] q\n);\n  always_ff @(posedge clk) begin\n    if (rst) q <= '0;\n    else     q <= q + 1'b1;\n  end\nendmodule\n",
    "module counter_tb;\n  logic clk = 0, rst = 1;\n  logic [3:0] q;\n  counter dut (.*);\n  always #5 clk = ~clk;\n  initial begin\n    #12 rst = 0;\n    #100;\n    assert (q == 4'd10) else $error(\"q is %0d, expected 10\", q);\n    $display(\"done, q = %0d\", q);\n    $finish;\n  end\nendmodule\n")
