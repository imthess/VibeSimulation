"""Shared behaviour of all gates (AND, OR, XOR ...): n inputs on the left, one output on the right."""
from functools import reduce

from ...core.bits import mask
from ...core.model import Attr, Component, make_port
from ..shapes import draw_gate, draw_pins


def pin_offsets(n):
    """y offset of each input pin of an n-input gate (measured from Logisim 3.8, size 50)."""
    if n == 1: return [0]
    if n == 2: return [-20, 20]
    if n == 3: return [-20, 0, 20]
    if n % 2: return [(i - n // 2) * 10 for i in range(n)]
    return [i * 10 for i in range(-n // 2, 0)] + [i * 10 for i in range(1, n // 2 + 1)]


class Gate(Component):
    """Template: a concrete gate only says its name, shape, width and truth function."""
    library, category = "Gates", "Gates"
    kind = "AND"        # outline family: AND, OR, NOT (triangle) or BOX
    bubble = False
    xor = False
    gate_width = 50     # distance from the input pins to the output pin
    single_input = False
    min_inputs = 2
    symbol = ""
    dominant = None     # AND/NAND: 0 and OR/NOR: 1 decide the output even when another input is unknown (Logisim's Value.and / Value.or)
    attrs_spec = (Attr("inputs", "int", 2, "Number of inputs", 2, 64), Attr("width", "int", 1, "Data bits", 1, 64))

    @classmethod
    def combine(cls, values, width):
        """Result for the given input values (all already masked)."""
        raise NotImplementedError

    def __init__(self, cid, attrs=None, ins=None, outs=None):
        if self.single_input:
            attrs = {k: v for k, v in (attrs or {}).items() if k != "inputs"}
        super().__init__(cid, attrs, ins, outs)

    @property
    def n(self):
        return 1 if self.single_input else self.attrs["inputs"]

    def all_ports(self):
        w, n = self.attrs["width"], self.n
        h = self.height()
        body = self.body()
        ports = [make_port(f"In{i + 1}", "in", w, -self.gate_width, dy, body, "") for i, dy in enumerate(pin_offsets(n))]
        return ports + [make_port("Out", "out", self.out_width(), 0, 0, body, "")]

    def out_width(self):
        return self.attrs["width"]

    def height(self):
        return 20 if self.single_input else (50 if self.n <= 5 else 10 * self.n + 10)

    def body(self):
        h = self.height()
        return (-self.gate_width, -h // 2, 0, h // 2)

    handles_error = True

    def evaluate(self, v):
        w = self.attrs["width"]; m = mask(w)
        raw = [v[f"In{i + 1}"] for i in range(self.n)]
        if any(x is None for x in raw):
            if self.dominant is None: return {"Out": None}
            known = [x & m for x in raw if x is not None]
            if self.dominant == 0:
                decided = ~reduce(lambda a, b: a & b, known, m) & m; fill = m      # bits where some known input is 0
            else:
                decided = reduce(lambda a, b: a | b, known, 0); fill = 0           # bits where some known input is 1
            if decided != m: return {"Out": None}
            raw = [fill if x is None else x for x in raw]
        vals = [x & m for x in raw]
        return {"Out": self.combine(vals, w) & mask(self.out_width())}

    def draw(self, r, ax, ay, ctx):
        draw_gate(r, ax, ay, self, ctx, self.kind, self.gate_width, self.height(), self.bubble, self.xor, self.symbol)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        a = {}
        if not self.single_input:
            a["inputs"] = self.n
            a["size"] = 50
        if self.attrs["width"] != 1:
            a["width"] = self.attrs["width"]
        if self.type_name in ("XOR", "XNOR") and not self.single_input:
            a["xor"] = "odd"
        return a

    # --- compact JSON: {"id": "g1", "type": "AND", "in": ["a", "b"], "out": "x"}
    def to_dict(self):
        d = {"id": self.id, "type": self.type_name}
        if self.attrs["width"] != 1: d["width"] = self.attrs["width"]
        d["in"] = [self.ins.get(f"In{i + 1}") for i in range(self.n)]
        if self.outs.get("Out") is not None: d["out"] = self.outs["Out"]
        return self.add_pos(d)

    def load_dict(self, d):
        self.load_pos(d)
        ins, out = d.get("in", []), d.get("out")
        if isinstance(ins, dict):
            ins = [ins[k] for k in sorted(ins, key=lambda k: int("".join(c for c in k if c.isdigit()) or 0))]
        if not isinstance(ins, list):
            raise ValueError(f'"in" of {self.id} must be a list of signal names')
        if not self.single_input and len(ins) != self.n:
            self.set_attr("inputs", len(ins)) if "inputs" not in d else None
        if len(ins) != self.n:
            raise ValueError(f"{self.id}: {self.type_name} needs {self.n} input(s), got {len(ins)}")
        self.ins = {f"In{i + 1}": str(s) for i, s in enumerate(ins) if s is not None}     # null = pin not connected
        if isinstance(out, dict): out = out.get("Out")
        if isinstance(out, list) and len(out) == 1: out = out[0]
        if out is not None: self.outs = {"Out": str(out)}

    def check(self):
        return []
