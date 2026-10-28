"""The instruction sent to the AI together with the picture."""
from ..components.gates.gate_base import Gate
from ..components.registry import ComponentRegistry as R


def _parts_help():
    lines = []
    for name in R.known():
        cls = R.lookup(name)
        if issubclass(cls, Gate) or cls.category == "Input/Output" or name in ("Probe", "Power", "Ground", "BitExtender", "Combiner", "Splitter", "Constant"):
            continue
        c = cls("x")
        ins = ", ".join(f"[{p.name}]" if p.optional else p.name for p in c.in_ports())
        outs = ", ".join(f"[{p.name}]" if p.optional else p.name for p in c.out_ports())
        lines.append(f"  {name}: in {ins} -> out {outs}")
    return "\n".join(lines)


ANALOG_HELP = """ANALOG CIRCUIT (resistors, capacitors, inductors, diodes, Zener diodes, LEDs, transistors, op-amps, transformers, switches, meters, batteries / voltage or current sources, controlled sources). Return exactly this format:
{"kind":"analog","title":"Voltage divider","components":[{"id":"V1","type":"VoltageSource","value":"5","nodes":["n1","0"]},{"id":"R1","type":"Resistor","value":"1k","nodes":["n1","n2"]},{"id":"R2","type":"Resistor","value":"2.2k","nodes":["n2","0"]}]}
Rules for analog circuits:
- Part types: Resistor, Capacitor, Inductor, VoltageSource, CurrentSource, Diode, Zener, LED, Switch, Ammeter, Voltmeter, VCVS, VCCS, CCVS, CCCS, NPN, PNP, NMOS, PMOS, NJFET, PJFET, IGBT, OpAmp, Transformer, Potentiometer (nodes A, wiper, B; "pos" 0..1). Use the closest of these for any other symbol.
- AC sources (sine generators, the ~ symbol): a VoltageSource or CurrentSource with "value" = its DC level ("0" if none) plus "ac" = peak amplitude, "freq" in hertz, optionally "phase" in degrees and "wave" ("sine", "square" or "triangle"), e.g. {"id":"V1","type":"VoltageSource","value":"0","ac":"5","freq":"1k","nodes":["in","0"]}. A value written as RMS in the drawing must be converted to peak (multiply by 1.414).
- Transistors and ICs (three or four nodes): NPN and PNP "nodes":["collector","base","emitter"]; NMOS, PMOS, NJFET, PJFET and IGBT "nodes":["drain","gate","source"] (IGBT: collector, gate, emitter); OpAmp "nodes":["in+","in-","out"] (supply pins are not drawn: optional "vpos"/"vneg" output limits, default ±15); Transformer "nodes":["primary+","primary-","secondary+","secondary-"] with "value" the primary inductance and "ratio" = turns secondary/primary. Use the arrow on the emitter / source to tell NPN from PNP and N-channel from P-channel. Every other number (beta, threshold) is optional.
- Zener: nodes [anode, cathode], extra key "vz" for the breakdown voltage (e.g. "5.1"). LED: like a Diode. Switch: extra key "state" is "open" or "closed" (as drawn). Ammeter and Voltmeter take no value.
- Controlled sources (diamond symbol): "value" is the gain. VCVS and VCCS add "control":["na","nb"] (the two nets whose voltage controls them). CCVS and CCCS add "control":"V1" (id of the voltage source or ammeter whose current controls them).
- "nodes" has exactly two node names: the nets the part's two terminals connect to. VoltageSource: [plus, minus]. Diode: [anode, cathode] (the arrow side is the anode). CurrentSource: current flows from the first node through the source to the second.
- Every wire that is electrically the same point gets the same node name (n1, n2, ...). The ground / 0 V node is always named "0". Every circuit needs a "0" node.
- "value" is written like the drawing: "1k", "4.7u", "10m", "5", "100". Units are implied (ohm, farad, henry, volt, ampere). A Diode, Zener, LED, Switch, Ammeter or Voltmeter has no value.
- Use the part labels written in the drawing (R1, C2, V1 ...) as "id"."""


def build_prompt():
    return f"""This image is a circuit: hand-drawn, a photo, or a screenshot. First decide which kind it is.
(A) A LOGIC (digital) circuit made of gates or logic blocks -> use the logic format below and put "kind":"digital" first.
(B) An ANALOG circuit -> use the analog format at the end.
Return ONLY a JSON object, no other text.

LOGIC CIRCUIT, exactly this format:
{{"kind":"digital","inputs":["A","B"],"outputs":["Y"],"gates":[{{"id":"g1","type":"NAND","in":["A","B"],"out":"n1"}},{{"id":"g2","type":"NOT","in":["n1"],"out":"Y"}}]}}
Rules:
- Gate types: AND, OR, NOT, NAND, NOR, XOR, XNOR. All except NOT take 2 to 32 inputs; NOT takes exactly 1. Gates use "in": [list] and "out": "name".
- A small circle (bubble) on a gate's output means NAND, NOR, XNOR or NOT (not AND, OR, XOR).
- If the drawing shows a labelled block (adder, MUX, decoder, comparator ...), use it as ONE component instead of rebuilding it from gates:
  {{"id":"u1","type":"Adder","width":4,"in":{{"A":"a","B":"b","Cin":"c"}},"out":{{"Sum":"s","Cout":"co"}}}}
  Components and their pins ([x] = optional, may be left out):
{_parts_help()}
  Settings: Adder/Subtractor/Multiplier/Comparator use "width" (bits). MUX/DEMUX use "select" (select bits) and "width". DECODER/ENCODER use "select".
  A 1-bit Adder with only A and B is a half adder; with Cin it is a full adder.
- Buses (several bits on one wire): declare an input as {{"name":"a","width":4}}.
- Give every wire a name. All points on the same wire use the same name. Use the labels written in the drawing for inputs and outputs; name other wires n1, n2, ...
- A dot where wires cross means they are connected. A crossing without a dot means NOT connected.
- Every gate or component output name is used once only.
- "outputs" lists the wire names that are the circuit's outputs (the final results).

{ANALOG_HELP}"""
