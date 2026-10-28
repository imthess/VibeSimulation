"""Built-in examples. Each one has a short tutorial (what to look at, what to try) and the text that is loaded into its section.

Registry pattern: ``EXAMPLES`` lists every example; ``for_section(name)`` filters. Adding an example is adding one entry.
"""
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Example:
    section: str            # "logisim" | "multisim" | "vlsi" | "systemverilog"
    key: str
    title: str
    level: str              # Beginner | Intermediate | Advanced
    summary: str
    steps: tuple            # the tutorial: short lines, in order
    text: str               # the JSON (Logisim, Multisim) or the Verilog design (VLSI)
    testbench: str = ""     # VLSI only


def _j(o): return json.dumps(o, indent=2)


EXAMPLES = []


def add(*a, **k): EXAMPLES.append(Example(*a, **k))


# ------------------------------------------------------------------------------------------------------------ Logisim
add("logisim", "half_adder", "Half adder", "Beginner", "Adds two bits: an XOR gives the sum, an AND gives the carry.",
    ("Open the example. The circuit box shows two gates and the truth table box lists all four input pairs.",
     "Click the inputs A and B in the circuit to toggle them and watch Sum and Carry change.",
     "In the JSON box change the XOR gate's type to OR. The circuit and the table follow at once.",
     "Press Ctrl+Z to undo the change."),
    _j({"inputs": ["A", "B"], "outputs": ["Sum", "Carry"], "gates": [
        {"id": "x1", "type": "XOR", "in": ["A", "B"], "out": "Sum"}, {"id": "a1", "type": "AND", "in": ["A", "B"], "out": "Carry"}]}))
add("logisim", "mux2", "2-to-1 multiplexer from gates", "Beginner", "Y = A when S is 0 and B when S is 1, built from NOT, AND and OR.",
    ("Toggle S and see which data input reaches Y.",
     "Look at the truth table: when S = 0 the rows follow A, when S = 1 they follow B.",
     "Right-click the OR gate and give it a third input to see how parts are edited."),
    _j({"inputs": ["A", "B", "S"], "outputs": ["Y"], "gates": [
        {"id": "n1", "type": "NOT", "in": ["S"], "out": "nS"}, {"id": "a1", "type": "AND", "in": ["A", "nS"], "out": "t1"},
        {"id": "a2", "type": "AND", "in": ["B", "S"], "out": "t2"}, {"id": "o1", "type": "OR", "in": ["t1", "t2"], "out": "Y"}]}))
add("logisim", "full_adder", "Full adder", "Intermediate", "Adds two bits and a carry in: two half adders and an OR.",
    ("Set A, B and Cin to 1: both Sum and Cout become 1.",
     "Use Project > Get circuit statistics to count the gates.",
     "Download the circuit as .circ (File > Export) and open it in Logisim-evolution."),
    _j({"inputs": ["A", "B", "Cin"], "outputs": ["Sum", "Cout"], "gates": [
        {"id": "x1", "type": "XOR", "in": ["A", "B"], "out": "p"}, {"id": "x2", "type": "XOR", "in": ["p", "Cin"], "out": "Sum"},
        {"id": "a1", "type": "AND", "in": ["A", "B"], "out": "g"}, {"id": "a2", "type": "AND", "in": ["p", "Cin"], "out": "pc"},
        {"id": "o1", "type": "OR", "in": ["g", "pc"], "out": "Cout"}]}))
add("logisim", "sr_ff", "SR flip-flop and a counter", "Intermediate", "A clocked SR flip-flop remembers a bit; a 4-bit counter counts clock edges.",
    ("Set S to 1, tick a full cycle (Ctrl+Shift+T): Q becomes 1 and stays 1 after S goes back to 0.",
     "Set R to 1 and tick: Q goes back to 0.",
     "The counter's Q output is a 4-bit bus: it counts up with every full cycle. Ctrl+R resets everything."),
    _j({"inputs": ["S", "R", "clk"], "outputs": ["Q", "Qn", "Count"], "gates": [
        {"id": "ff", "type": "S-R Flip-Flop", "in": {"S": "S", "R": "R", "Clk": "clk"}, "out": {"Q": "Q", "Qn": "Qn"}},
        {"id": "cnt", "type": "Counter", "attrs": {"width": 4}, "in": {"Clk": "clk"}, "out": {"Q": "Count"}}]}))
add("logisim", "divide_by_2", "Divide-by-two (toggle flip-flop)", "Intermediate", "A D flip-flop whose input is its own inverted output halves the clock frequency.",
    ("Use Simulate > Tick full cycle (Ctrl+Shift+T) a few times and watch Q toggle once per cycle.",
     "Turn on Ticks enabled (Ctrl+K) to let the clock run by itself.",
     "Reset the simulation with Ctrl+R."),
    _j({"inputs": ["clk"], "outputs": ["Q"], "gates": [
        {"id": "n1", "type": "NOT", "in": ["Q"], "out": "nq"},
        {"id": "ff", "type": "D Flip-Flop", "in": {"D": "nq", "Clk": "clk"}, "out": {"Q": "Q"}}]}))

# ------------------------------------------------------------------------------------------------------------ Multisim
add("multisim", "pot_divider", "Voltage divider with a potentiometer", "Beginner", "A 10 kΩ potentiometer between 10 V and ground: the wiper voltage follows its position.",
    ("Look at the DC operating point: node w is at about 7 V because the wiper is 30 % from the top.",
     "In the JSON change \"pos\" to 0.8 and read the new wiper voltage.",
     "Open Analysis > DC sweep to plot the wiper voltage while the source changes."),
    _j({"title": "Potentiometer divider", "components": [
        {"id": "V1", "type": "VoltageSource", "value": "10", "nodes": ["a", "0"]},
        {"id": "RV1", "type": "Potentiometer", "value": "10k", "pos": "0.3", "nodes": ["a", "w", "0"]},
        {"id": "RL", "type": "Resistor", "value": "100k", "nodes": ["w", "0"]}]}))
add("multisim", "rc_lowpass", "RC low-pass filter", "Beginner", "A 1 kΩ resistor and a 100 nF capacitor: the corner frequency is 1.59 kHz.",
    ("Choose AC: frequency response (Bode) in the results box and press Run: the gain falls 20 dB per decade above 1.6 kHz.",
     "Choose Transient (time): the 100 Hz square wave is smoothed into charging curves.",
     "Change C1 to 10n and run the Bode plot again: the corner moves up by a factor of ten."),
    _j({"title": "RC low-pass", "components": [
        {"id": "V1", "type": "VoltageSource", "value": "0", "ac": "1", "freq": "100", "wave": "square", "nodes": ["in", "0"]},
        {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["in", "out"]},
        {"id": "C1", "type": "Capacitor", "value": "100n", "nodes": ["out", "0"]}]}))
add("multisim", "rectifier", "Half-wave rectifier with a real diode", "Intermediate", "A 1N4007 diode rectifies a 5 V, 50 Hz sine; a capacitor smooths it.",
    ("Run Transient (time) for 60 ms: the output follows the positive peaks minus about 0.7 V.",
     "Change the diode's \"model\" to 1N5819 (Schottky): the output peak rises because its forward drop is lower.",
     "Remove the capacitor (delete C1 in the JSON) to see the unsmoothed half waves."),
    _j({"title": "Half-wave rectifier", "components": [
        {"id": "V1", "type": "VoltageSource", "value": "0", "ac": "5", "freq": "50", "nodes": ["in", "0"]},
        {"id": "D1", "type": "Diode", "model": "1N4007", "nodes": ["in", "out"]},
        {"id": "C1", "type": "Capacitor", "value": "100u", "nodes": ["out", "0"]},
        {"id": "RL", "type": "Resistor", "value": "1k", "nodes": ["out", "0"]}]}))
add("multisim", "inverting_amp", "Inverting op-amp amplifier", "Intermediate", "Gain = -Rf / Rin = -10, so 0.2 V in gives -2 V out.",
    ("Read the DC operating point: out is about -2 V.",
     "Run the Bode plot: the gain is flat at 20 dB until the gain-bandwidth limit of the op-amp.",
     "Raise the input to 2 V: the output is limited by the supply rails (vpos / vneg)."),
    _j({"title": "Inverting amplifier", "components": [
        {"id": "V1", "type": "VoltageSource", "value": "0.2", "ac": "0.1", "freq": "1k", "nodes": ["in", "0"]},
        {"id": "Rin", "type": "Resistor", "value": "1k", "nodes": ["in", "inv"]},
        {"id": "Rf", "type": "Resistor", "value": "10k", "nodes": ["inv", "out"]},
        {"id": "U1", "type": "OpAmp", "nodes": ["0", "inv", "out"]}]}))
add("multisim", "ce_amp", "NPN common-emitter amplifier", "Advanced", "A voltage-divider biased transistor stage: read the bias point, then the gain.",
    ("Read the operating point of Q1: the Results box shows the region (forward active), Vbe and Ic.",
     "Run the Bode plot to see the mid-band gain and the low-frequency roll-off from the input capacitor.",
     "Change RE to 2.2k and watch the bias current and the gain change."),
    _j({"title": "Common-emitter amplifier", "components": [
        {"id": "Vcc", "type": "VoltageSource", "value": "12", "nodes": ["vcc", "0"]},
        {"id": "Vin", "type": "VoltageSource", "value": "0", "ac": "0.01", "freq": "1k", "nodes": ["src", "0"]},
        {"id": "Cin", "type": "Capacitor", "value": "10u", "nodes": ["src", "b"]},
        {"id": "R1", "type": "Resistor", "value": "47k", "nodes": ["vcc", "b"]}, {"id": "R2", "type": "Resistor", "value": "10k", "nodes": ["b", "0"]},
        {"id": "RC", "type": "Resistor", "value": "4.7k", "nodes": ["vcc", "c"]}, {"id": "RE", "type": "Resistor", "value": "1k", "nodes": ["e", "0"]},
        {"id": "CE", "type": "Capacitor", "value": "100u", "nodes": ["e", "0"]},
        {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "e"]}]}))

# ------------------------------------------------------------------------------------------------------------ VLSI
add("vlsi", "adder4", "4-bit adder", "Beginner", "One line of Verilog becomes a ripple of full adders.",
    ("The Verilog box holds the design; the circuit and the truth table are built from it.",
     "Change + to - and watch the circuit turn into a subtractor.",
     "Open the Problems tab: warnings appear when a signal is unused or a width does not match."),
    "module adder4 (\n  input  [3:0] a,\n  input  [3:0] b,\n  output [3:0] sum,\n  output       carry\n);\n  assign {carry, sum} = a + b;\nendmodule\n")
add("vlsi", "counter", "Counter with a testbench", "Intermediate", "A 4-bit counter with a synchronous reset, and a testbench that prints and draws it.",
    ("Press Run in the bottom panel: the Waveform tab draws clk, rst and q.",
     "Open the Test tab in the Verilog box to read the testbench: #delays, a clock with always, $display and $finish.",
     "Click a line of the design: the part it made is selected in the circuit (and the other way round)."),
    "module counter (\n  input clk,\n  input rst,\n  output reg [3:0] q\n);\n  always @(posedge clk)\n    if (rst) q <= 4'd0;\n    else     q <= q + 4'd1;\nendmodule\n",
    "module counter_tb;\n  reg clk = 0, rst = 1;\n  wire [3:0] q;\n  counter dut (.clk(clk), .rst(rst), .q(q));\n  always #5 clk = ~clk;\n  initial begin\n    #12 rst = 0;\n    #200 $display(\"q after 200 time units = %d\", q);\n    $finish;\n  end\nendmodule\n")
add("vlsi", "mux4", "4-to-1 multiplexer with case", "Beginner", "A case statement becomes a multiplexer.",
    ("Look at the circuit: one Multiplexer part with a 2-bit select.",
     "Add a default branch or remove one choice: the warning list tells you what became a latch or a don't-care.",
     "Play the truth table with the play button."),
    "module mux4 (\n  input  [1:0] s,\n  input  a, b, c, d,\n  output reg y\n);\n  always @(*)\n    case (s)\n      2'd0: y = a;\n      2'd1: y = b;\n      2'd2: y = c;\n      default: y = d;\n    endcase\nendmodule\n")
add("vlsi", "parity_generate", "Parity with for and generate", "Advanced", "A loop and a generate block unrolled into XOR gates.",
    ("Change WIDTH to 12: the XOR chain grows (the parameter is read when the design is compiled).",
     "The for loop in the always block and the generate loop give the same circuit.",
     "Use Export > Verilog to save the text for another tool."),
    "module parity #(parameter WIDTH = 8) (\n  input  [WIDTH-1:0] d,\n  output p,\n  output q\n);\n  reg r;\n  integer i;\n  always @(*) begin\n    r = 1'b0;\n    for (i = 0; i < WIDTH; i = i + 1) r = r ^ d[i];\n  end\n  assign p = r;\n  wire [WIDTH:0] chain;\n  assign chain[0] = 1'b0;\n  genvar g;\n  generate\n    for (g = 0; g < WIDTH; g = g + 1) begin : x\n      assign chain[g+1] = chain[g] ^ d[g];\n    end\n  endgenerate\n  assign q = chain[WIDTH];\nendmodule\n")
add("vlsi", "rom", "A small ROM", "Intermediate", "A case-based lookup table is recognised as a ROM.",
    ("Play the truth table: the address counts and the data follows the table.",
     "Edit one of the values and see the memory contents change.",
     "Larger tables are kept as a ROM part instead of gates."),
    "module rom4 (\n  input  [1:0] addr,\n  output reg [7:0] data\n);\n  always @(*)\n    case (addr)\n      2'd0: data = 8'h3F;\n      2'd1: data = 8'h06;\n      2'd2: data = 8'h5B;\n      default: data = 8'h4F;\n    endcase\nendmodule\n")


def for_section(name): return [e for e in EXAMPLES if e.section == name]


def find(section, key):
    for e in EXAMPLES:
        if e.section == section and e.key == key: return e
    raise KeyError(f"{section}/{key}")


from . import examples_sv  # noqa: E402,F401  (registers the SystemVerilog examples)
