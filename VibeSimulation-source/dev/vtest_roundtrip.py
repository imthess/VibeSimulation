"""Every part type: circuit -> Verilog -> circuit must behave the same (readable form and exact cell form)."""
import itertools, sys, random
sys.path.insert(0, "src")
import vibesimulation.components
from vibesimulation.components.registry import ComponentRegistry as R
from vibesimulation.core.model import Circuit, IOPin
from vibesimulation.verilog.elab import elaborate
from vibesimulation.verilog.emit import Writer, equivalent, circuit_to_verilog
from vibesimulation.verilog.lexer import VError

VARIANTS = {
    "AND": [{}, {"inputs": 3, "width": 4}, {"width": 8}], "OR": [{}, {"inputs": 4}, {"width": 3}], "NAND": [{}, {"width": 4}, {"inputs": 3}], "NOR": [{}, {"inputs": 3, "width": 2}],
    "XOR": [{}, {"inputs": 3}, {"width": 4, "inputs": 3}], "XNOR": [{}, {"inputs": 3}, {"width": 4}], "NOT": [{}, {"width": 5}], "BUFFER": [{}, {"width": 3}],
    "ODDPARITY": [{"inputs": 3}, {"width": 4}], "EVENPARITY": [{"inputs": 3}, {"width": 4}],
    "Constant": [{"width": 4, "value": 9}, {}], "Power": [{}, {"width": 3}], "Ground": [{}, {"width": 3}],
    "Splitter": [{"widths": [1, 3, 4]}, {}], "Combiner": [{"widths": [2, 2, 3]}, {}], "BitExtender": [{"in_width": 3, "out_width": 7, "fill": f} for f in ("zero", "one", "sign")] + [{"in_width": 6, "out_width": 3}],
    "MUX": [{}, {"select": 2, "width": 4}, {"select": 1, "width": 5}], "DECODER": [{}, {"select": 3}], "DEMUX": [{"select": 2, "width": 3}], "ENCODER": [{"select": 2}, {"select": 3}], "BITSELECTOR": [{"width": 8, "group": 2}, {"width": 5}],
    "Adder": [{"width": 6}], "Subtractor": [{"width": 6}], "Multiplier": [{"width": 5}], "Divider": [{"width": 5}], "Negator": [{"width": 5}],
    "Comparator": [{"width": 4, "mode": "signed"}, {"width": 5}], "Shifter": [{"width": 8, "shift": s} for s in ("ll", "lr", "ar", "rl", "rr")] + [{"width": 5, "shift": "lr"}],
    "BitAdder": [{"width": 6, "inputs": 3}], "BitFinder": [{"width": 6, "find": f} for f in ("low1", "high1", "low0", "high0")],
    "D Flip-Flop": [{}, {"trigger": "falling"}, {"trigger": "high"}], "T Flip-Flop": [{}], "J-K Flip-Flop": [{}], "S-R Flip-Flop": [{"trigger": "falling"}],
    "Register": [{"width": 4}, {"width": 3, "trigger": "falling"}], "Counter": [{"width": 4, "max": 9}, {"width": 3, "ongoal": "stay"}], "Shift Register": [{"width": 1, "length": 4}, {"width": 2, "length": 3, "parallel": False}],
    "RAM": [{"addr": 3, "width": 4}, {"addr": 2, "width": 3, "asyncread": True}], "ROM": [{"addr": 3, "width": 4, "contents": {"1": 5, "5": 9}}], "Clock": [{}],
    "Probe": [{"width": 3}], "LED": [{}], "SEVENSEG": [{}], "HEXDISPLAY": [{}],
}
SKIP_PIN = {"Clock"}


def build(ty, attrs, optional_mode):
    proto = R.create(ty, "x", attrs)
    ins, outs, pins_in, pins_out = {}, {}, [], []
    for p in proto.all_ports():
        if p.direction == "in":
            if p.optional and optional_mode == "none": continue
            if p.optional and optional_mode == "some" and hash(p.name) % 2: continue
            pins_in.append(IOPin("i_" + p.name, p.width)); ins[p.name] = "i_" + p.name
        else:
            if p.optional and optional_mode == "none": continue
            outs[p.name] = "o_" + p.name
    c = R.create(ty, "u1", attrs, ins, outs)
    circ = Circuit(pins_in, [IOPin(s, 1) for s in outs.values()], [c]); circ.sync()
    return circ


bad = 0; n = 0
for ty, vs in VARIANTS.items():
    for attrs in vs:
        for mode in ("all", "none", "some"):
            circ = build(ty, attrs, mode)
            if circ.validate(loose=True): continue
            n += 1
            for readable in (True, False):
                text = Writer("t", circ, readable).text()
                try:
                    circs, _, _ = elaborate(text, "t")
                    new = dict(circs)["t"]
                    errs = new.validate(loose=True)
                    ok = not errs and equivalent(circ, new, n=300)
                    why = errs
                except VError as e:
                    ok, why = False, f"{e.msg} (line {e.line})"
                if not ok:
                    bad += 1; print("FAIL", ty, attrs, mode, "readable" if readable else "cells", why); print(text)
print("cases", n, "failures", bad)
