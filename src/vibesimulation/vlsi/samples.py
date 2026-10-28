"""The design a new VLSI project starts with."""

SAMPLE = """// A 4-bit adder with a carry out. Edit the Verilog: the circuit and the truth table follow.
module adder4 (
  input  [3:0] a,
  input  [3:0] b,
  output [3:0] sum,
  output       carry
);
  assign {carry, sum} = a + b;
endmodule
"""

BLANK = """module top (
  input  a,
  input  b,
  output y
);
  assign y = a & b;
endmodule
"""
