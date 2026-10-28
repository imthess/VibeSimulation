"""Snippets the SystemVerilog explorer inserts at the cursor."""

TEMPLATES = (
    ("Module with logic ports", "module name (\n  input  logic clk,\n  input  logic [7:0] a,\n  output logic [7:0] y\n);\n  assign y = a;\nendmodule\n"),
    ("always_ff register", "  always_ff @(posedge clk) begin\n    if (rst) q <= '0;\n    else     q <= d;\n  end\n"),
    ("always_comb with unique case", "  always_comb begin\n    y = '0;\n    unique case (sel)\n      2'd0: y = a;\n      2'd1: y = b;\n      default: y = '0;\n    endcase\n  end\n"),
    ("Enum state machine", "  typedef enum logic [1:0] {IDLE, RUN, DONE} state_t;\n  state_t state, next;\n  always_ff @(posedge clk) state <= rst ? IDLE : next;\n  always_comb begin\n    next = state;\n    case (state)\n      IDLE: if (go) next = RUN;\n      RUN:  next = DONE;\n      DONE: next = IDLE;\n    endcase\n  end\n"),
    ("Packed struct", "  typedef struct packed {\n    logic [3:0] hi;\n    logic [3:0] lo;\n  } pair_t;\n  pair_t p;\n"),
    ("Package", "package my_pkg;\n  localparam int WIDTH = 8;\n  typedef logic [WIDTH-1:0] word_t;\nendpackage\n"),
    ("Import a package", "  import my_pkg::*;\n"),
    ("for loop with an int", "    for (int i = 0; i < 8; i++) begin\n      \n    end\n"),
    ("Function with return", "  function automatic logic [7:0] name(input logic [7:0] a);\n    return a + 1;\n  endfunction\n"),
    ("inside", "  assign hit = (value inside {1, 3, [8:11]});\n"),
    ("Immediate assertion", "    assert (a == b) else $error(\"a and b differ: %0d %0d\", a, b);\n"),
    ("Instance with .name and .*", "  name u1 (.clk, .rst, .*);\n"),
)
