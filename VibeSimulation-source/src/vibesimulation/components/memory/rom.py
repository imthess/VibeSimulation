"""ROM (Logisim: Memory > ROM): read-only memory. Contents are part of the circuit, so they are in the JSON ("contents": {"address": value})."""
from ...core.bits import mask
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


def encode_contents(contents, addr_bits, width):
    """Logisim's text form of memory contents: 'addr/data: A D' then hex values, runs written as count*value."""
    n = 1 << addr_bits; toks, i = [], 0
    while i < n:
        v = contents.get(i, 0); j = i
        while j < n and contents.get(j, 0) == v: j += 1
        run = j - i
        toks.append(f"{run}*{v:x}" if run > 3 else " ".join([f"{v:x}"] * run))
        i = j
    lines, cur = [], ""
    for t in toks:
        if len(cur) + len(t) + 1 > 70: lines.append(cur); cur = ""
        cur = (cur + " " + t) if cur else t
    lines.append(cur)
    return f"addr/data: {addr_bits} {width}\n" + "\n".join(lines) + "\n"


def decode_contents(text):
    """Inverse of encode_contents -> (addr_bits, width, {address: value}) or None."""
    head, _, rest = text.partition("\n")
    p = head.split()
    if len(p) != 3 or p[0] != "addr/data:": return None
    try: ab, w = int(p[1]), int(p[2])
    except ValueError: return None
    out, i = {}, 0
    for tok in rest.split():
        try:
            if "*" in tok: n, v = tok.split("*", 1); n, v = int(n), int(v, 16)
            else: n, v = 1, int(tok, 16)
        except ValueError: return None
        if v:
            for k in range(n): out[i + k] = v
        i += n
    return ab, w, out


@register
class Rom(Component):
    type_name = "ROM"
    logisim_name = "ROM"
    library, category = "Memory", "Memory"
    summary = "ROM: D shows the stored value at address A. Fill it in the JSON (\"contents\") or by double-clicking the part."
    attrs_spec = (Attr("addr", "int", 8, "Address bits", 1, 16), Attr("width", "int", 8, "Data bits", 1, 64),
                  Attr("contents", "map", {}, "Contents (address: value)"))
    handles_error = False
    lkeys = {"addr": "addrWidth", "width": "dataWidth"}

    def body(self): return (0, 0, 240, 140)

    def all_ports(self):
        b = self.body()
        return [make_port("A", "in", self.attrs["addr"], 0, 10, b, "A"), make_port("D", "out", self.attrs["width"], 240, 60, b, "D")]

    def check(self):
        a, w, c = self.attrs["addr"], self.attrs["width"], self.attrs["contents"]
        bad = [k for k in c if k >= 1 << a]
        if bad: return [f"contents: address {bad[0]} does not fit in {a} address bits"]
        bad = [k for k, v in c.items() if v > mask(w)]
        if bad: return [f"contents: the value at address {bad[0]} does not fit in {w} bits"]
        return []

    def evaluate(self, v):
        return {"D": self.attrs["contents"].get(v["A"], 0)}

    def draw(self, r, ax, ay, ctx):
        r.rect(ax, ay, ax + 240, ay + 140, FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + 120, ay + 46, "ROM", 16, OUTLINE, True, "c", ctx.body_tags)
        r.text(ax + 120, ay + 70, f"{1 << self.attrs['addr']} x {self.attrs['width']}", 10, MUTED, False, "c", ctx.body_tags)
        a = ctx.val(self.ins.get("A"), None); d = ctx.val(self.outs.get("D"), None)
        if a is not None and d is not None:
            r.text(ax + 120, ay + 92, f"[{a:X}] = {d:X}", 12, OUTLINE, True, "c", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        a, w = self.attrs["addr"], self.attrs["width"]
        return {"appearance": "classic", "addrWidth": a, "dataWidth": w, "contents": ("text", encode_contents(self.attrs["contents"], a, w))}
