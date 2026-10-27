"""Evaluating Verilog expressions on live values.

It reuses the circuit builder (`Mod`): every net reads as a constant, so each operator folds into a number at once and
the width and sign rules are exactly the ones used to build circuits.
"""
from ...core.bits import mask
from ..elab import Mod, V, Net
from ..lexer import VError


class Runtime(Mod):
    """The testbench module seen as values: `values` maps a name to its current number, `arrays` holds memories."""
    def __init__(self, ctx, ast, values, arrays, clock, rng):
        super().__init__(ctx, ast, {}, ast.name)
        self.values, self.arrays, self.clock, self.prng = values, arrays, clock, rng
        self.eval_params({})
        self.items = self.expand_items(ast.items); self.register_subprograms(self.items)
        self.declare()
        self.call_depth = 0

    # ---- names
    def readnet(self, name, line=None):
        n = self.net(name, line)
        if self.env is not None and name in self.env.rd: return self.mat_var(n, self.env.rd[name])      # a local of a function being built
        if n.pre is not None: return n.pre
        return V("c", self.values.get(name, 0) & mask(n.w), n.w)

    def read_bits(self, n, lo, hi, e): return self.b.slice(self.readnet(n.name), lo, hi)

    def ci_name(self, e):
        if e.name in self.params: return self.params[e.name][0]
        n = self.nets.get(e.name)
        if n is None: self.err(f"'{e.name}' is not declared", e.line)
        ev = self.env.rd.get(e.name) if self.env is not None else None
        if isinstance(ev, V) and ev.k == "c": v = ev.x
        elif n.pre is not None and n.pre.k == "c": v = n.pre.x
        else: v = self.values.get(e.name, 0) & mask(n.w)
        return v - (1 << n.w) if n.signed and v >> (n.w - 1) & 1 else v

    # ---- memories
    def mem_read(self, e):
        m = self.mems[e.base.name]; i = self.ci(e.idx)
        return self.b.const(self.arrays[m.name].get(i, 0) if 0 <= i < m.depth else 0, m.w)

    # ---- system functions
    def sysfn_info(self, e):
        f = e.fn
        if f in ("$time", "$realtime"): return (64, False, True)
        if f == "$stime": return (32, False, True)
        if f == "$random": return (32, True, True)
        if f in ("$urandom", "$urandom_range"): return (32, False, True)
        if f == "$bits": return (32, False, True)
        self.err(f"{f} is not supported", e.line)

    def sysfn_value(self, e):
        f = e.fn; b = self.b
        if f in ("$time", "$realtime"): return b.const(self.clock(), 64)
        if f == "$stime": return b.const(self.clock() & 0xFFFFFFFF, 32)
        if f == "$random":
            if e.args:
                seed = self.ci(e.args[0]); v, new = self.prng.random(seed)
                self.store_seed(e.args[0], new)
            else: v, _ = self.prng.random()
            return b.const(v & 0xFFFFFFFF, 32)
        if f == "$urandom": return b.const(self.prng.urandom(), 32)
        if f == "$urandom_range":
            hi = self.ci(e.args[0]); lo = self.ci(e.args[1]) if len(e.args) > 1 else 0
            return b.const(self.prng.urandom_range(hi, lo), 32)
        if f == "$bits": return b.const(self.info(e.args[0])[0], 32)
        self.err(f"{f} is not supported", e.line)

    def store_seed(self, lv, value):
        parts = self.lv_parts(lv)
        for n, lo, hi in parts: self.values[n.name] = value & mask(n.w)

    # ---- evaluating
    def value(self, e):
        """(number, width, signed) of an expression on its own."""
        w, s, _ = self.info(e)
        v = self.ev(e, w, s, w)
        if v.k != "c": self.err("internal: this expression did not reduce to a number", e.line)
        return v.x, w, s

    def value_in(self, e, width):
        """The expression assigned to something `width` bits wide (Verilog assignment rules)."""
        w, s, _ = self.info(e)
        v = self.ev(e, max(width, w), s, width)
        if v.k != "c": self.err("internal: this expression did not reduce to a number", e.line)
        return v.x

    def truth(self, e):
        v, w, s = self.value(e); return v != 0
