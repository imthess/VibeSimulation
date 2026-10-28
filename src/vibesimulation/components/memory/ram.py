"""RAM (Logisim: Memory > RAM), the common configuration: one address, separate data-in and data-out pins, one word per access.

Pins (as in Logisim): A address, Din data in, Dout data out, WE write enable, OE output enable, Clk clock (not there for the
level-triggered 'high'/'low' trigger), Clr clear (only when "Clear pin" is on). Contents start at 0 and live in the simulation
(Reset simulation empties the RAM); double-click the part to read or change them while the circuit runs.
Not supported: the bidirectional data bus, line enables, byte enables, several data lines.
"""
from ...core.bits import mask
from ...core.model import Attr, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins
from .seq_base import LEVEL, Sequential


@register
class Ram(Sequential):
    type_name = "RAM"
    logisim_name = "RAM"
    summary = "RAM: stores Din at address A when WE is 1 on the clock edge; Dout shows the word at A. Double-click to see or edit the contents."
    attrs_spec = (Attr("addr", "int", 8, "Address bits", 1, 24), Attr("width", "int", 8, "Data bits", 1, 64),
                  Attr("trigger", "choice", "rising", "Trigger", choices=LEVEL),
                  Attr("asyncread", "bool", False, "Asynchronous read"),
                  Attr("readbehav", "choice", "afterwrite", "Read after / before write", choices=("afterwrite", "beforewrite")),
                  Attr("clearpin", "bool", False, "Clear pin"))
    lkeys = {"addr": "addrWidth", "width": "dataWidth"}
    state_outs = ("Dout",)

    def level(self): return self.attrs["trigger"] in ("high", "low")
    def head(self): return 80 if self.level() else 90
    def body(self): return (0, 0, 240, self.head() + 64)

    def all_ports(self):
        a, w, b, h = self.attrs["addr"], self.attrs["width"], self.body(), self.head()
        ps = [make_port("A", "in", a, 0, 10, b, "A"), make_port("Din", "in", w, 0, h, b, "D", optional=True, default=0),
              make_port("Dout", "out", w, 240, h, b, "D"),
              make_port("OE", "in", 1, 0, 60, b, "OE", optional=True, default=1), make_port("WE", "in", 1, 0, 50, b, "WE", optional=True, default=0)]
        if not self.level(): ps.append(make_port("Clk", "in", 1, 0, 70, b, "", optional=True, default=0))
        if self.attrs["clearpin"]: ps.append(make_port("Clr", "in", 1, 40, 0, b, "clr", optional=True, default=0))
        return ps

    def evolution_ports(self):
        d = {p.name: (p.dx, p.dy) for p in self.all_ports()}
        if self.attrs["width"] == 1:
            d["Din"] = (0, d["Din"][1] + 10); d["Dout"] = (240, d["Dout"][1] + 10)
        return d

    def check(self):
        if self.attrs["asyncread"] and self.level(): return []
        return []

    def init_state(self): return {"mem": {}, "dout": 0 if (self.attrs["asyncread"] or self.level()) else None, "clk": None}      # (before its first clock edge a synchronous RAM shows an error value, like Logisim)

    def outputs(self, st, args): return {"Dout": st["dout"]}

    def step(self, st, a, tick):
        at = self.attrs; wmask = mask(at["width"])
        if at["clearpin"] and a.get("Clr") == 1:
            st["mem"] = {}; st["dout"] = 0; return st
        addr = a.get("A")
        good = addr is not None
        mem = st["mem"]
        if self.level(): edge = False
        else: edge = self.clocked(st, a)
        we = a.get("WE")
        if self.level(): write = (we == 1) if at["trigger"] == "high" else (we == 0)
        else: write = edge and we == 1
        old = mem.get(addr, 0) if good else 0
        new = old
        if good and write and a.get("Din") is not None:
            new = a["Din"] & wmask
            st["mem"] = mem = dict(mem)
            if new: mem[addr] = new
            else: mem.pop(addr, None)
        if a.get("OE") == 0: return st                      # output not enabled: Dout keeps what it had
        if not good: st["dout"] = None; return st           # an error address gives an error value
        if at["asyncread"] or self.level(): st["dout"] = new
        elif edge: st["dout"] = new if at["readbehav"] == "afterwrite" else old
        return st

    def draw(self, r, ax, ay, ctx):
        r.rect(ax, ay, ax + 240, ay + self.body()[3], FILL, OUTLINE, 2, ctx.body_tags)
        r.text(ax + 120, ay + 14, f"RAM {1 << self.attrs['addr']} x {self.attrs['width']}", 11, OUTLINE, True, "c", ctx.body_tags)
        a = ctx.val(self.ins.get("A"), None); d = ctx.val(self.outs.get("Dout"), None)
        if a is not None and d is not None: r.text(ax + 120, ay + 50, f"[{a:X}] = {d:X}", 12, OUTLINE, True, "c", ctx.body_tags)
        for p in self.active_ports():
            if p.direction == "in" and p.label and p.name != "A": r.text(ax + 4, ay + p.dy, p.label, 9, OUTLINE, True, "w", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)

    def logisim_attrs(self):
        at = self.attrs
        d = {"appearance": "classic", "addrWidth": at["addr"], "dataWidth": at["width"]}
        if at["trigger"] != "rising": d["trigger"] = at["trigger"]
        if at["asyncread"]: d["asyncread"] = "true"
        if at["readbehav"] != "afterwrite": d["readbehav"] = "war"
        if at["clearpin"]: d["clearpin"] = "true"
        return d
