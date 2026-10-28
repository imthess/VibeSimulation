"""A circuit placed inside another circuit (Logisim: a subcircuit). Its pins are the input and output pins of the circuit it stands for."""
from ...core import project
from ...core.model import Attr, Component, make_port
from ...core.render import FILL, OUTLINE, MUTED
from ..registry import register
from ..shapes import draw_pins


@register
class SubCircuit(Component):
    type_name = "Circuit"
    logisim_name = ""
    library, category = "", "Circuits"
    hidden = True                      # listed in the palette's "Circuits" folder, not among the parts
    is_sub = True
    show_optional = True
    summary = "Another circuit of this project, used as a part."
    attrs_spec = (Attr("circuit", "str", "", "Circuit name"),)

    def inner(self):
        return project.lookup(self.attrs["circuit"])

    def pins(self):
        c = self.inner()
        return (c.inputs, c.outputs) if c else ([], [])

    def body(self):
        i, o = self.pins()
        return project.classic_geometry(len(i), len(o))[2]

    def all_ports(self):
        ins, outs = self.pins()
        gi, go, b = project.classic_geometry(len(ins), len(outs))
        return ([make_port(p.name, "in", p.width, x, y, b, p.name, optional=True) for p, (x, y) in zip(ins, gi)] +
                [make_port(p.name, "out", p.width, x, y, b, p.name) for p, (x, y) in zip(outs, go)])

    def check(self):
        n = self.attrs["circuit"]
        if not n: return ['"circuit" must name another circuit of this project']
        if self.inner() is None: return [f"there is no circuit called '{n}' in this project (or its JSON is broken)"]
        if n == project.CURRENT or project.CURRENT in project.uses(n): return [f"circuit '{n}' contains this circuit: a circuit cannot contain itself"]
        return []

    def has_memory(self):
        c = self.inner()
        return bool(c) and c.has_seq()

    def seeds(self):
        return [s for s in self.outs.values() if s] if self.has_memory() else []

    def needs(self):
        return [] if self.has_memory() else [p.name for p in self.in_ports()]

    def evaluate(self, v):             # never used: the simulator works on the flattened circuit
        return {}

    def draw(self, r, ax, ay, ctx):
        x0, y0, x1, y1 = self.body()
        r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
        r.line([((x0 + x1) / 2 - 4 + ax, y0 + 1 + ay), ((x0 + x1) / 2 + ax, y0 + 6 + ay), ((x0 + x1) / 2 + 4 + ax, y0 + 1 + ay)], 1.5, MUTED, ctx.body_tags)
        n = self.attrs["circuit"]
        if len(n) <= 4: r.text(ax + (x0 + x1) / 2, ay + (y0 + y1) / 2 + 3, n, 9, OUTLINE, True, "c", ctx.body_tags)
        else: r.text(ax + (x0 + x1) / 2, ay + y1 + 4, n, 9, OUTLINE, True, "n", ctx.body_tags)
        draw_pins(r, ax, ay, self, ctx)
