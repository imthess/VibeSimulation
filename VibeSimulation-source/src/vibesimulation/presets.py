"""Ready-made circuits built from Logisim's own parts (Factory Method per preset).

Each preset returns a complete Circuit: input pins -> the real component -> output pins. Nothing is
built from AND/OR/NOT, so the result looks like what you would drag together in Logisim.
"""
from dataclasses import dataclass
from typing import Callable

from .components.registry import ComponentRegistry as R
from .core.model import Circuit, IOPin


@dataclass
class Preset:
    name: str
    description: str
    param_label: str            # "" = no parameter
    choices: list               # [(label, value)]
    default: int
    build: Callable             # build(value) -> Circuit


def _comp(type_name, cid, attrs, ins, outs):
    c = R.create(type_name, cid, attrs)
    c.ins, c.outs = dict(ins), dict(outs)
    return c


def half_adder(_=None):
    c = _comp("Adder", "ha", {"width": 1}, {"A": "A", "B": "B"}, {"Sum": "Sum", "Cout": "Carry"})
    return Circuit([IOPin("A"), IOPin("B")], [IOPin("Sum"), IOPin("Carry")], [c]).sync()


def full_adder(_=None):
    c = _comp("Adder", "fa", {"width": 1}, {"A": "A", "B": "B", "Cin": "Cin"}, {"Sum": "Sum", "Cout": "Cout"})
    return Circuit([IOPin("A"), IOPin("B"), IOPin("Cin")], [IOPin("Sum"), IOPin("Cout")], [c]).sync()


def parallel_adder(n):
    c = _comp("Adder", "pa", {"width": n}, {"A": "A", "B": "B", "Cin": "Cin"}, {"Sum": "Sum", "Cout": "Cout"})
    return Circuit([IOPin("A", n), IOPin("B", n), IOPin("Cin")], [IOPin("Sum", n), IOPin("Cout")], [c]).sync()


def parallel_subtractor(n):
    c = _comp("Subtractor", "ps", {"width": n}, {"A": "A", "B": "B", "Bin": "Bin"}, {"Diff": "Diff", "Bout": "Bout"})
    return Circuit([IOPin("A", n), IOPin("B", n), IOPin("Bin")], [IOPin("Diff", n), IOPin("Bout")], [c]).sync()


def mux(select_bits):
    n = 1 << select_bits
    ins = {f"In{i}": f"I{i}" for i in range(n)}
    ins["Sel"] = "S"
    c = _comp("MUX", "mux", {"select": select_bits, "width": 1}, ins, {"Out": "Y"})
    return Circuit([IOPin(f"I{i}") for i in range(n)] + [IOPin("S", select_bits)], [IOPin("Y")], [c]).sync()


def demux(select_bits):
    n = 1 << select_bits
    c = _comp("DEMUX", "demux", {"select": select_bits, "width": 1}, {"In": "D", "Sel": "S"}, {f"Out{i}": f"Y{i}" for i in range(n)})
    return Circuit([IOPin("D"), IOPin("S", select_bits)], [IOPin(f"Y{i}") for i in range(n)], [c]).sync()


def decoder(select_bits):
    n = 1 << select_bits
    c = _comp("DECODER", "dec", {"select": select_bits}, {"Sel": "A"}, {f"Out{i}": f"Y{i}" for i in range(n)})
    return Circuit([IOPin("A", select_bits)], [IOPin(f"Y{i}") for i in range(n)], [c]).sync()


def encoder(select_bits):
    n = 1 << select_bits
    c = _comp("ENCODER", "enc", {"select": select_bits}, {f"In{i}": f"I{i}" for i in range(n)}, {"Out": "Y", "GS": "Valid"})
    return Circuit([IOPin(f"I{i}") for i in range(n)], [IOPin("Y", select_bits), IOPin("Valid")], [c]).sync()


def comparator(n):
    c = _comp("Comparator", "cmp", {"width": n}, {"A": "A", "B": "B"}, {"GT": "AgtB", "EQ": "AeqB", "LT": "AltB"})
    return Circuit([IOPin("A", n), IOPin("B", n)], [IOPin("AgtB"), IOPin("AeqB"), IOPin("AltB")], [c]).sync()


BITS = [(f"{n} bits", n) for n in (2, 3, 4, 5, 6, 8)]
SEL = [("2 inputs (1 select bit)", 1), ("4 inputs (2 select bits)", 2), ("8 inputs (3 select bits)", 3), ("16 inputs (4 select bits)", 4)]
SEL_OUT = [("1-to-2", 1), ("1-to-4", 2), ("1-to-8", 3), ("1-to-16", 4)]
DEC = [("2 to 4", 2), ("3 to 8", 3), ("4 to 16", 4)]
ENC = [("4 to 2", 2), ("8 to 3", 3)]

PRESETS = [
    Preset("Half adder", "Adds two bits. Logisim has no half-adder part, so this is its Adder with no carry-in (1 bit).", "", [("", 0)], 0, half_adder),
    Preset("Full adder", "Adds two bits and a carry-in: Logisim's Adder part set to 1 bit.", "", [("", 0)], 0, full_adder),
    Preset("Parallel adder", "Adds two multi-bit numbers (and a carry-in) with one Adder part.", "Width", BITS, 4, parallel_adder),
    Preset("Parallel subtractor", "Subtracts two multi-bit numbers (and a borrow-in) with one Subtractor part.", "Width", BITS, 4, parallel_subtractor),
    Preset("Multiplexer (MUX)", "Passes one of several inputs to the output, chosen by the select bits.", "Size", SEL, 1, mux),
    Preset("Demultiplexer (DEMUX)", "Sends one input to one of several outputs, chosen by the select bits.", "Size", SEL_OUT, 1, demux),
    Preset("Decoder", "Turns a binary number into one active output line (one-hot).", "Size", DEC, 0, decoder),
    Preset("Encoder (priority)", "Gives the number of the highest active input (Logisim's Priority Encoder).", "Size", ENC, 0, encoder),
    Preset("Magnitude comparator", "Tells whether A is greater than, equal to, or less than B.", "Width", BITS, 2, comparator),
]


def merge(base, piece):
    """Add the circuit ``piece`` to ``base``, renaming anything that would clash. Returns base."""
    def unique(name, taken):
        n, k = name, 2
        while n in taken:
            n, k = f"{name}_{k}", k + 1
        return n
    taken = set(base.signals()) | set(base.output_names())
    ren = {}
    for p in piece.inputs:
        ren[p.name] = unique(p.name, taken); taken.add(ren[p.name])
    for comp in piece.components:
        for s in comp.outs.values():
            ren[s] = unique(s, taken); taken.add(ren[s])
    ids = {c.id for c in base.components}
    for comp in piece.components:
        comp.id = unique(comp.id, ids); ids.add(comp.id)
        comp.ins = {k: ren.get(v, v) for k, v in comp.ins.items()}
        comp.outs = {k: ren.get(v, v) for k, v in comp.outs.items()}
    base.inputs += [IOPin(ren[p.name], p.width) for p in piece.inputs]
    base.outputs += [IOPin(ren.get(p.name, p.name), p.width) for p in piece.outputs]
    base.components += piece.components
    return base.sync()
