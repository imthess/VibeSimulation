"""Verilog snippets the explorer can insert (plain data, no UI)."""

TEMPLATES = (
    ("Module", "module name (\n  input  a,\n  input  b,\n  output y\n);\n  assign y = a & b;\nendmodule\n"),
    ("Wire and assign", "  wire [3:0] w;\n  assign w = a + b;\n"),
    ("Combinational block", "  always @* begin\n    y = 1'b0;\n    if (a) y = b;\n  end\n"),
    ("Case statement", "  always @* begin\n    case (sel)\n      2'd0: y = a;\n      2'd1: y = b;\n      default: y = 1'b0;\n    endcase\n  end\n"),
    ("Register (clock)", "  always @(posedge clk) begin\n    q <= d;\n  end\n"),
    ("Register with enable and reset", "  always @(posedge clk or posedge rst) begin\n    if (rst) q <= 4'd0;\n    else if (en) q <= q + 4'd1;\n  end\n"),
    ("State machine", "  reg [1:0] s, ns;\n  always @(posedge clk) if (rst) s <= 2'd0; else s <= ns;\n  always @* begin\n    ns = s;\n    case (s)\n      2'd0: if (x) ns = 2'd1;\n      2'd1: ns = 2'd0;\n      default: ns = 2'd0;\n    endcase\n  end\n"),
    ("Gate primitive", "  and g1 (y, a, b);\n"),
    ("Use another module", "  name u1 (.a(a), .b(b), .y(y));\n"),
)
