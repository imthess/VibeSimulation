"""Starter texts of the SystemVerilog section."""

SAMPLE = """// A traffic-light controller: an enum state machine written the SystemVerilog way.
typedef enum logic [1:0] {RED, GREEN, YELLOW} light_t;

module traffic (
  input  logic clk,
  input  logic rst,
  input  logic car,          // a car is waiting on the side road
  output logic [2:0] lamps   // {red, yellow, green}
);
  light_t state, next;

  always_ff @(posedge clk) begin
    if (rst) state <= RED;
    else     state <= next;
  end

  always_comb begin
    next = state;
    unique case (state)
      RED:    if (car) next = GREEN;
      GREEN:  next = YELLOW;
      YELLOW: next = RED;
      default: next = RED;
    endcase
  end

  always_comb begin
    lamps = 3'b000;
    case (state)
      RED:    lamps = 3'b100;
      YELLOW: lamps = 3'b010;
      GREEN:  lamps = 3'b001;
      default: lamps = 3'b100;
    endcase
  end
endmodule
"""

BLANK = """module top (
  input  logic a,
  output logic y
);
  assign y = a;
endmodule
"""
