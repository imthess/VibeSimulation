"""Verilog AST -> Circuit.  Follows IEEE 1364 width/sign rules; every operator becomes a Logisim component.

Values are V(kind 'c' constant | 's' signal, value-or-name, width).  Components whose inputs are all constants are
evaluated right away (so constants fold), everything else becomes a real component.
"""
from ..components.registry import ComponentRegistry as R
from ..core.bits import mask
from ..core.model import Circuit, IOPin
from .lexer import VError
from .parser import N, parse_modules
from .genblocks import GenerateMixin
from .lintchecks import LintMixin
from .loops import LoopMixin
from .memories import MemoryMixin
from .subprograms import SubprogramMixin
from .tristate import TriStateMixin

MAXW = 64
CLOSED = {"+", "-", "*", "&", "|", "^", "~^"}          # operators whose low N bits only depend on the low N bits of the operands


def clog2(n): return max(0, (n - 1).bit_length())


class V:
    __slots__ = ("k", "x", "w")
    def __init__(self, k, x, w): self.k, self.x, self.w = k, x, w
    def __repr__(self): return f"V({self.k},{self.x},{self.w})"


def sext(val, fw, tw, signed):
    val &= mask(fw)
    if signed and fw < tw and val >> (fw - 1) & 1: val |= mask(tw) & ~mask(fw)
    return val & mask(tw)


class Net:
    def __init__(self, name, w, signed, kind, line, lsb=0):
        self.name, self.w, self.signed, self.kind, self.line, self.lsb = name, w, signed, kind, line, lsb
        self.dir = None; self.drivers = []; self.parts = {}; self.state = 0; self.val = None; self.pre = None; self.read = False; self.tri = {}


class Driver:
    def __init__(self, run, targets, line):
        self.run, self.targets, self.line, self.state = run, targets, line, 0     # targets: [(net, lo, hi)]


class Builder:
    """Collects components for one circuit."""
    def __init__(self):
        self.comps = []; self.cn = 0; self.sw = {}; self.consts = {}; self.cache = {}

    def new_sig(self, w):
        if not 1 <= w <= MAXW: raise VError(f"a {w}-bit value is not possible: widths go from 1 to {MAXW} bits")
        self.cn += 1; s = f"_{self.cn}"; self.sw[s] = w; return s

    def const(self, val, w):
        if not 1 <= w <= MAXW: raise VError(f"a {w}-bit value is not possible: widths go from 1 to {MAXW} bits")
        return V("c", val & mask(w), w)

    def sig(self, v):
        if v.k == "s": return v.x
        key = (v.w, v.x)
        if key not in self.consts:
            s = self.new_sig(v.w); c = R.create("Constant", "", {"width": v.w, "value": v.x}, outs={"Out": s}); self.comps.append(c); self.consts[key] = s
        return self.consts[key]

    def comp(self, ty, attrs, ins, outs, hint=None, raw=False):
        """ins: port -> V.  Returns port -> V for the requested outs."""
        proto = R.create(ty, "", attrs)
        for p, v in ins.items():
            pp = proto.port(p)
            if pp is None: raise VError(f"{ty} has no pin '{p}'")
            if pp.width != v.w: raise VError(f"internal: {ty}.{p} is {pp.width} bits but gets {v.w}")
        if not raw and not proto.sequential and all(v.k == "c" for v in ins.values()):
            args = {p.name: (ins[p.name].x if p.name in ins else p.default) for p in proto.in_ports()}
            res = proto.evaluate(args)
            return {o: self.const((res.get(o) or 0), proto.port(o).width) for o in outs}
        key = None
        if not proto.sequential and not raw:
            key = (ty, tuple(sorted((k, str(v)) for k, v in proto.attrs.items())), tuple(sorted((p, v.k, v.x) for p, v in ins.items())), tuple(outs))
            if key in self.cache: return self.cache[key]
        c = proto
        c.ins = {p: self.sig(v) for p, v in ins.items()}
        res = {}
        for o in outs:
            s = self.new_sig(c.port(o).width); c.outs[o] = s; res[o] = V("s", s, c.port(o).width)
        c._hint = hint
        self.comps.append(c)
        if key: self.cache[key] = res
        return res

    # ---- width helpers
    def ext(self, v, w, signed):
        if v.w == w: return v
        if v.w > w: return self.slice(v, 0, w - 1)
        if v.k == "c": return self.const(sext(v.x, v.w, w, signed), w)
        return self.comp("BitExtender", {"in_width": v.w, "out_width": w, "fill": "sign" if signed else "zero"}, {"In": v}, ["Out"])["Out"]

    def slice(self, v, lo, hi):
        w = hi - lo + 1
        if lo == 0 and w == v.w: return v
        if v.k == "c": return self.const(v.x >> lo, w)
        widths = ([lo] if lo else []) + [w] + ([v.w - hi - 1] if hi < v.w - 1 else [])
        return self.comp("Splitter", {"widths": widths}, {"In": v}, [f"Out{1 if lo else 0}"])[f"Out{1 if lo else 0}"]

    def concat(self, parts):
        """parts: list of V, most significant first."""
        parts = list(reversed(parts))
        if len(parts) == 1: return parts[0]
        w = sum(p.w for p in parts)
        if not 1 <= w <= MAXW: raise VError(f"a {w}-bit value is not possible: widths go from 1 to {MAXW} bits")
        if len(parts) > 32:                                   # a Logisim combiner has at most 32 inputs: join in groups, then join the groups
            groups = [parts[i:i + 32] for i in range(0, len(parts), 32)]
            return self.concat([self.concat(list(reversed(g))) for g in reversed(groups)])
        return self.comp("Combiner", {"widths": [p.w for p in parts]}, {f"In{i}": p for i, p in enumerate(parts)}, ["Out"])["Out"]

    def gate(self, ty, vs, hint=None):
        w = vs[0].w
        if ty in ("NOT", "BUFFER"): return self.comp(ty, {"width": w}, {"In1": vs[0]}, ["Out"], hint)["Out"]
        return self.comp(ty, {"width": w, "inputs": len(vs)}, {f"In{i + 1}": v for i, v in enumerate(vs)}, ["Out"], hint)["Out"]

    def mux(self, c, a, b):
        """c ? a : b"""
        if c.k == "c": return a if c.x else b
        if a.k == b.k and a.x == b.x: return a
        return self.comp("MUX", {"select": 1, "width": a.w}, {"In0": b, "In1": a, "Sel": c}, ["Out"])["Out"]

    def cmp(self, a, b, signed, out):
        return self.comp("Comparator", {"width": a.w, "mode": "signed" if signed else "unsigned"}, {"A": a, "B": b}, [out])[out]

    def bits(self, v):
        return [self.slice(v, i, i) for i in range(v.w)]

    def truth(self, v):          # v != 0
        return v if v.w == 1 else self.cmp(v, self.const(0, v.w), False, "GT")

    def inv(self, v): return self.gate("NOT", [v])


class Mod(LoopMixin, SubprogramMixin, GenerateMixin, MemoryMixin, TriStateMixin, LintMixin):
    """One module instantiated with fixed parameter values."""
    def __init__(self, ctx, ast, overrides, cname):
        self.ctx, self.ast, self.cname = ctx, ast, cname
        self.b = Builder(); self.nets = {}; self.order = []; self.params = {}; self.line = ast.line; self.inputs = []; self.outputs = []
        self.hints = {}; self.env = None; self.all_drivers = []; self.seq_vars = {}
        self.subs = []     # circuit names used
        self.funcs = {}; self.tasks = {}; self.mems = {}; self.fstack = []; self.loop_vars = set(); self.allow_xz = set(); self.items = []

    def err(self, msg, line=None): raise VError(msg, line or self.line)

    # ---------------------------------------------------------------- constants and types
    def ci(self, e):
        """Whole-number constant expression."""
        k = e.kind
        if k == "num":
            n = e.num
            if n.xmask or n.zmask: self.err("x/z is not allowed here", e.line)
            return sext(n.bits, n.width or 32, 64, n.signed) if False else (n.bits - (1 << n.width) if n.signed and n.width and n.bits >> (n.width - 1) & 1 else n.bits)
        if k == "paren": return self.ci(e.x)
        if k == "id": return self.ci_name(e)
        if k == "un":
            x = self.ci(e.x)
            return {"+": x, "-": -x, "~": ~x, "!": int(not x)}.get(e.op) if e.op in "+-~!" and len(e.op) == 1 else self.err("this operator is not supported in a constant", e.line)
        if k == "bin":
            a, b = self.ci(e.a), self.ci(e.b); o = e.op
            try:
                return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: int(a / b) if b else self.err("division by zero", e.line), "%": lambda: (abs(a) % abs(b)) * (1 if a >= 0 else -1) if b else self.err("division by zero", e.line),
                        "**": lambda: a ** b, "<<": lambda: a << b, "<<<": lambda: a << b, ">>": lambda: a >> b, ">>>": lambda: a >> b, "&": lambda: a & b, "|": lambda: a | b, "^": lambda: a ^ b,
                        "~^": lambda: ~(a ^ b), "==": lambda: int(a == b), "!=": lambda: int(a != b), "===": lambda: int(a == b), "!==": lambda: int(a != b), "<": lambda: int(a < b), "<=": lambda: int(a <= b),
                        ">": lambda: int(a > b), ">=": lambda: int(a >= b), "&&": lambda: int(bool(a) and bool(b)), "||": lambda: int(bool(a) or bool(b))}[o]()
            except OverflowError: self.err("this number is too big", e.line)
        if k == "cond": return self.ci(e.a) if self.ci(e.c) else self.ci(e.b)
        if k == "call":
            x = self.ci(e.arg)
            if e.fn == "$clog2": return clog2(x)
            return x
        if k == "fcall":
            v = self.call_function(e)
            if v.k != "c": self.err("a constant is needed here, but this function call does not give one", e.line)
            f = self.funcs[e.name]; w, sg = self.ret_info(f)
            return v.x - (1 << w) if sg and v.x >> (w - 1) & 1 else v.x
        self.err("a constant (number or parameter) is needed here", e.line)

    def ci_name(self, e):
        """Value of a name in a constant expression: a parameter, or a variable that holds a known value right now (loop counters)."""
        if e.name in self.params: return self.params[e.name][0]
        ev = self.env.rd.get(e.name) if self.env is not None else None
        if isinstance(ev, V) and ev.k == "c":
            n = self.nets.get(e.name)
            return ev.x - (1 << ev.w) if n is not None and n.signed and ev.x >> (ev.w - 1) & 1 else ev.x
        self.err(f"'{e.name}' is not a constant here (only numbers and parameters may be used)", e.line)

    def sysfn_info(self, e): self.err(f"{e.fn} is not supported in a circuit (only testbenches use it)", e.line)

    def sysfn_value(self, e): self.err(f"{e.fn} is not supported in a circuit (only testbenches use it)", e.line)

    def is_const(self, e):
        try: self.ci(e); return True
        except VError: return False

    def rng(self, r):
        if r is None: return 1, 0
        msb, lsb = self.ci(r[0]), self.ci(r[1])
        if msb < lsb: self.err(f"the range [{msb}:{lsb}] must count down (msb first)", r[0].line)
        if lsb < 0: self.err("a range cannot start below 0", r[0].line)
        w = msb - lsb + 1
        if w > MAXW: self.err(f"a {w}-bit signal is too wide: Logisim values go up to {MAXW} bits", r[0].line)
        return w, lsb

    # ---------------------------------------------------------------- types of expressions: (width, signed, context-free)
    def info(self, e):
        k = e.kind
        if k == "num":
            n = e.num; return (n.width or 32, n.signed, True)
        if k == "str": self.err("a text string cannot be used in a circuit", e.line)
        if k == "paren": return self.info(e.x)
        if k == "id":
            if e.name in self.params:
                _, w, s = self.params[e.name]; return (w, s, True)
            n = self.net(e.name, e.line); return (n.w, n.signed, True)
        if k == "index":
            if self.is_mem_ref(e): m = self.mems[e.base.name]; return (m.w, m.signed, True)
            self.info(e.base); return (1, False, True)
        if k == "fcall": return self.fn_info(e)
        if k == "sysfn": return self.sysfn_info(e)
        if k == "slice":
            a, b = self.ci(e.msb), self.ci(e.lsb)
            if a < b: self.err(f"the part select [{a}:{b}] must count down (msb first)", e.line)
            return (a - b + 1, False, True)
        if k == "islice":
            w = self.ci(e.width)
            if w < 1: self.err("the width of a part select must be at least 1", e.line)
            return (w, False, True)
        if k == "concat":
            w = sum(self.info(p)[0] for p in e.parts); return (w, False, True)
        if k == "repl":
            c = self.ci(e.count)
            if c < 1: self.err("a replication count must be at least 1", e.line)
            return (c * sum(self.info(p)[0] for p in e.parts), False, True)
        if k == "un":
            w, s, f = self.info(e.x)
            if e.op in ("+", "-", "~"): return (w, s, False)
            return (1, False, True)
        if k == "bin":
            o = e.op
            if o == "**":
                self.ci(e); return (32, True, True)
            a, b = self.info(e.a), self.info(e.b)
            if o in ("==", "!=", "===", "!==", "<", "<=", ">", ">=", "&&", "||"): return (1, False, True)
            if o in ("<<", ">>", "<<<", ">>>"): return (a[0], a[1], False)
            return (max(a[0], b[0]), a[1] and b[1], False)
        if k == "cond":
            self.info(e.c); a, b = self.info(e.a), self.info(e.b)
            return (max(a[0], b[0]), a[1] and b[1], False)
        if k == "call":
            if e.fn == "$clog2": return (32, True, True)
            w, s, f = self.info(e.arg); return (w, e.fn == "$signed", f)
        self.err("this kind of expression is not supported", e.line)

    # ---------------------------------------------------------------- nets
    def net(self, name, line=None):
        n = self.nets.get(name)
        if n is None: self.err(f"'{name}' is not declared", line)
        return n

    def readnet(self, name, line=None):
        n = self.net(name, line); n.used = True
        if self.env is not None and name in self.env.rd:
            return self.mat_var(n, self.env.rd[name])
        n.read = True
        return self.resolve(n)

    def resolve(self, n):
        if n.state == 2: return n.val
        if n.pre is not None: n.state = 2; n.val = n.pre; return n.val
        if n.state == 1: self.err(f"'{n.name}' depends on itself (a combinational loop)", n.line)
        n.state = 1
        saved, self.env = self.env, None
        try:
            for d in n.drivers: self.run_driver(d)
        finally: self.env = saved
        b = self.b
        if n.kind == "input": n.state = 2; n.val = V("s", n.name, n.w); return n.val
        if n.kind == "supply0" and not n.parts: n.parts[(0, n.w - 1)] = b.const(0, n.w)
        if n.kind == "supply1" and not n.parts: n.parts[(0, n.w - 1)] = b.const(mask(n.w), n.w)
        if n.tri: self.merge_tri(n)
        if not n.parts: self.err(f"'{n.name}' is never driven (no assign, gate, instance or always block sets it)", n.line)
        spans = sorted(n.parts); pos = 0; parts = []
        for (lo, hi) in spans:
            if lo < pos: self.err(f"'{n.name}' is driven more than once (bits {lo}..{min(hi, pos - 1)})", n.line)
            if lo > pos: self.err(f"bits [{pos + n.lsb}:{lo - 1 + n.lsb}] of '{n.name}' are never driven", n.line)
            parts.append(n.parts[(lo, hi)]); pos = hi + 1
        if pos < n.w: self.err(f"bits [{n.w - 1 + n.lsb}:{pos + n.lsb}] of '{n.name}' are never driven", n.line)
        n.val = b.concat(list(reversed(parts))); n.state = 2
        return n.val

    def run_driver(self, d):
        if d.state == 2: return
        if d.state == 1: self.err("a combinational loop: this statement depends on its own result", d.line)
        d.state = 1; self.line = d.line
        first = len(self.b.comps)
        d.run()
        for c in self.b.comps[first:]:
            if getattr(c, "_line", None) is None: c._line = d.line          # which statement made this part (for "show me this part in the Verilog")
        d.state = 2

    def add_part(self, n, lo, hi, v, hint=None):
        if n.kind == "integer" and (n.parts or n.tri): return                 # an integer used as a scratch variable by several blocks
        if (lo, hi) in n.parts or any(not (hi < l2 or lo > h2) for (l2, h2) in n.parts): self.err(f"'{n.name}' is driven more than once", self.line)
        n.parts[(lo, hi)] = v

    # ---------------------------------------------------------------- expression building
    def ev_self(self, e):
        w, s, _ = self.info(e); return self.ev(e, w, s, w), w, s

    def ev(self, e, W, S, Nn):
        """Value of expression e evaluated in a W-bit context of signedness S, keeping the low Nn bits."""
        b = self.b; k = e.kind; self.line = e.line or self.line
        if k == "paren": return self.ev(e.x, W, S, Nn)
        if k == "num":
            n = e.num
            if n.xmask or n.zmask:
                if id(e) not in self.allow_xz: self.err("x and z values cannot be used in a calculation in a circuit; use 0 or 1 (x/z is only accepted as a whole assigned value, meaning don't care)", e.line)
                self.warn("an x/z value is treated as 0 (don't care)", e.line)
                return b.const(0, Nn)
            w = n.width or 32
            return b.const(sext(n.bits, w, Nn, S) if Nn > w else n.bits & mask(Nn), Nn)
        if k == "id" and e.name in self.params:
            val, w, sg = self.params[e.name]
            return b.const(sext(val, w, Nn, S) if Nn > w else val & mask(Nn), Nn)
        if k in ("id", "index", "slice", "islice", "concat", "repl", "fcall", "sysfn") or (k == "call" and e.fn in ("$signed", "$unsigned", "$clog2")):
            v = self.leaf(e)
            return b.ext(v, Nn, S)
        if k == "un":
            op = e.op
            if op == "+": return self.ev(e.x, W, S, Nn)
            if op == "-":
                x = self.ev(e.x, W, S, Nn); return b.comp("Negator", {"width": Nn}, {"In": x}, ["Out"])["Out"]
            if op == "~": return b.gate("NOT", [self.ev(e.x, W, S, Nn)])
            x, wx, sx = self.ev_self(e.x)
            return b.ext(self.reduce(op, x), Nn, False)
        if k == "bin":
            return self.binop(e, W, S, Nn)
        if k == "cond":
            c, _, _ = self.ev_self(e.c); c = b.truth(c)
            if c.k == "c": return self.ev(e.a if c.x else e.b, W, S, Nn)
            return b.mux(c, self.ev(e.a, W, S, Nn), self.ev(e.b, W, S, Nn))
        self.err("this kind of expression is not supported", e.line)

    def leaf(self, e):
        """Self-determined value of a context-free node at its own width."""
        b = self.b; k = e.kind
        if k == "paren": return self.leaf(e.x)
        if k == "id":
            if e.name in self.params:
                val, w, sg = self.params[e.name]; return b.const(val, w)
            return self.readnet(e.name, e.line)
        if k == "num": return self.ev(e, *((self.info(e)[0], self.info(e)[1], self.info(e)[0])))
        if k == "fcall": return self.call_function(e)
        if k == "sysfn": return self.sysfn_value(e)
        if k == "index" and self.is_mem_ref(e): return self.mem_read(e)
        if k in ("index", "slice", "islice"):
            bn = self.nets.get(e.base.name) if e.base.kind == "id" and e.base.name not in self.params else None
            if bn is not None and bn.kind != "input" and bn.pre is None and not (self.env is not None and bn.name in self.env.rd):
                rb = self.const_bits(e, bn)
                if rb is not None: return self.read_bits(bn, rb[0], rb[1], e)          # only the drivers of those bits are needed
            base = self.leaf_or_expr(e.base); off = 0
            if e.base.kind == "id" and e.base.name in self.nets: off = self.nets[e.base.name].lsb
            if k == "index":
                if self.is_const(e.idx):
                    i = self.ci(e.idx) - off
                    if not 0 <= i < base.w: self.err(f"bit {i + off} is outside '{self.name_of(e.base)}' (it has {base.w} bit(s))", e.line)
                    return b.slice(base, i, i)
                iv, wi, _ = self.ev_self(e.idx)
                if base.w == 1: self.err("a 1-bit signal cannot be indexed by a variable", e.line)
                if off: self.err("a variable index needs a range that starts at 0", e.line)
                sw = max(1, clog2(base.w))
                if wi > sw: iv = b.slice(iv, 0, sw - 1)
                else: iv = b.ext(iv, sw, False)
                return b.comp("BITSELECTOR", {"width": base.w, "group": 1}, {"In": base, "Sel": iv}, ["Out"])["Out"]
            if k == "slice":
                hi, lo = self.ci(e.msb) - off, self.ci(e.lsb) - off
            else:
                if not self.is_const(e.start): self.err("a variable part select [i +: w] is not supported; the start must be a constant", e.line)
                st = self.ci(e.start) - off; w = self.ci(e.width)
                lo, hi = (st, st + w - 1) if e.dir == "+:" else (st - w + 1, st)
            if lo < 0 or hi >= base.w: self.err(f"the part select [{hi + off}:{lo + off}] is outside '{self.name_of(e.base)}' (it has {base.w} bit(s))", e.line)
            return b.slice(base, lo, hi)
        if k == "concat":
            vs = []
            for p in e.parts:
                v, w, s = self.ev_self(p); vs.append(v)
            return b.concat(vs)
        if k == "repl":
            cnt = self.ci(e.count)
            inner = b.concat([self.ev_self(p)[0] for p in e.parts])
            if cnt * inner.w > MAXW: self.err(f"the repeated value is {cnt * inner.w} bits wide; the most is {MAXW}", e.line)
            return b.concat([inner] * cnt)
        if k == "call":
            if e.fn == "$clog2": return b.const(clog2(self.ci(e.arg)), 32)
            return self.ev_self(e.arg)[0]
        self.err("this kind of expression is not supported", e.line)

    def const_bits(self, e, n):
        """(lo, hi) of a select with constant bounds of net n (0 = its lowest bit), or None."""
        off = n.lsb
        try:
            if e.kind == "index": lo = hi = self.ci(e.idx) - off
            elif e.kind == "slice": hi, lo = self.ci(e.msb) - off, self.ci(e.lsb) - off
            else:
                st = self.ci(e.start) - off; w = self.ci(e.width); lo, hi = (st, st + w - 1) if e.dir == "+:" else (st - w + 1, st)
        except VError: return None
        if lo < 0 or hi >= n.w or lo > hi: return None
        return lo, hi

    def read_bits(self, n, lo, hi, e):
        """Bits lo..hi of net n. Only the statements that drive those bits are run, so a vector may be built bit by bit
        from values that depend on its other bits (a ripple-carry chain c[i+1] = f(c[i]))."""
        b = self.b; n.read = True
        if n.state == 2: return b.slice(n.val, lo, hi)
        saved, self.env = self.env, None
        try:
            for d in n.drivers:
                if any(t[0] is n and not (t[2] < lo or t[1] > hi) for t in d.targets): self.run_driver(d)
        finally: self.env = saved
        if n.tri: self.merge_tri(n)
        if n.kind == "supply0" and not n.parts: n.parts[(0, n.w - 1)] = b.const(0, n.w)
        if n.kind == "supply1" and not n.parts: n.parts[(0, n.w - 1)] = b.const(mask(n.w), n.w)
        pieces = []; pos = lo
        for (l, h) in sorted(n.parts):
            if h < pos or l > hi: continue
            if l > pos: self.err(f"bit {pos + n.lsb} of '{n.name}' is never driven", e.line)
            top = min(h, hi); pieces.append(b.slice(n.parts[(l, h)], pos - l, top - l)); pos = top + 1
            if pos > hi: break
        if pos <= hi: self.err(f"bit {pos + n.lsb} of '{n.name}' is never driven (no assign, gate, instance or always block sets it)", e.line)
        return b.concat(list(reversed(pieces)))

    def leaf_or_expr(self, e):
        if e.kind in ("id", "index", "slice", "islice", "paren", "concat", "repl", "fcall", "sysfn"): return self.leaf(e)
        return self.ev_self(e)[0]

    def name_of(self, e):
        return e.name if e.kind == "id" else "the value"

    def reduce(self, op, x):
        b = self.b; w = x.w
        if op == "!": return b.cmp(x, b.const(0, w), False, "EQ")
        if op in ("&", "~&"):
            r = x if w == 1 else b.cmp(x, b.const(mask(w), w), False, "EQ")
            return b.inv(r) if op == "~&" else r
        if op in ("|", "~|"):
            r = b.truth(x); return b.inv(r) if op == "~|" else r
        if w == 1: return b.inv(x) if op == "~^" else x
        return b.comp("ODDPARITY" if op == "^" else "EVENPARITY", {"inputs": w, "width": 1}, {f"In{i + 1}": v for i, v in enumerate(b.bits(x))}, ["Out"])["Out"]

    def binop(self, e, W, S, Nn):
        b = self.b; o = e.op
        if o == "**":
            return b.const(self.ci(e), Nn)
        if o in CLOSED:
            x, y = self.ev(e.a, W, S, Nn), self.ev(e.b, W, S, Nn)
            if o == "+": return b.comp("Adder", {"width": Nn}, {"A": x, "B": y}, ["Sum"])["Sum"]
            if o == "-": return b.comp("Subtractor", {"width": Nn}, {"A": x, "B": y}, ["Diff"])["Diff"]
            if o == "*": return b.comp("Multiplier", {"width": Nn}, {"A": x, "B": y}, ["Prod"])["Prod"]
            return b.gate({"&": "AND", "|": "OR", "^": "XOR", "~^": "XNOR"}[o], [x, y])
        if o in ("/", "%"):
            if S: return self.signed_divide(e, W, Nn)
            Wd = self.shrink([e.a, e.b], W, S)
            x, y = self.ev(e.a, W, S, Wd), self.ev(e.b, W, S, Wd)
            r = b.comp("Divider", {"width": Wd}, {"A": x, "B": y}, ["Quot" if o == "/" else "Rem"])["Quot" if o == "/" else "Rem"]
            return b.ext(r, Nn, False)
        if o in ("==", "!=", "===", "!==", "<", "<=", ">", ">="):
            wa, sa, _ = self.info(e.a); wb, sb, _ = self.info(e.b); Wc, Sc = max(wa, wb), sa and sb
            self.check_compare(e, wa, wb)
            Wd = self.shrink([e.a, e.b], Wc, Sc)
            x, y = self.ev(e.a, Wc, Sc, Wd), self.ev(e.b, Wc, Sc, Wd)
            if Wd < Wc and not Sc: pass
            out, neg = {"==": ("EQ", 0), "===": ("EQ", 0), "!=": ("EQ", 1), "!==": ("EQ", 1), "<": ("LT", 0), "<=": ("GT", 1), ">": ("GT", 0), ">=": ("LT", 1)}[o]
            r = b.cmp(x, y, Sc, out)
            if neg: r = b.inv(r)
            return b.ext(r, Nn, False)
        if o in ("&&", "||"):
            x = b.truth(self.ev_self(e.a)[0]); y = b.truth(self.ev_self(e.b)[0])
            if x.k == "c" or y.k == "c":
                r = b.const(int(bool(x.x) and bool(y.x) if o == "&&" else bool(x.x) or bool(y.x)), 1) if x.k == y.k == "c" else (
                    (y if x.x else x) if o == "&&" else (x if x.x else y)) if x.k == "c" else ((x if y.x else y) if o == "&&" else (y if y.x else x))
            else: r = b.gate("AND" if o == "&&" else "OR", [x, y])
            return b.ext(r, Nn, False)
        if o in ("<<", ">>", "<<<", ">>>"):
            left = o in ("<<", "<<<")
            arith = o == ">>>" and S
            wa = self.info(e.a)[0]
            if left: Wr, x = Nn, self.ev(e.a, W, S, Nn)
            elif not S and self.info(e.a)[2]:
                Wr = wa; x = self.ev(e.a, wa, False, wa)
            else: Wr = W; x = self.ev(e.a, W, S, W)
            amt, wb, _ = self.ev_self(e.b)
            r = self.shift(x, amt, Wr, "ll" if left else ("ar" if arith else "lr"))
            return b.ext(r, Nn, False)
        self.err(f"the operator '{o}' is not supported", e.line)

    def signed_divide(self, e, W, Nn):
        """Signed / and %: divide the magnitudes with the (unsigned) Divider, then fix the sign.
        The quotient is negative when the signs differ; the remainder takes the sign of the dividend."""
        b = self.b
        x, y = self.ev(e.a, W, True, W), self.ev(e.b, W, True, W)
        neg = lambda v: b.comp("Negator", {"width": W}, {"In": v}, ["Out"])["Out"]
        sx, sy = b.slice(x, W - 1, W - 1), b.slice(y, W - 1, W - 1)
        ax, ay = b.mux(sx, neg(x), x), b.mux(sy, neg(y), y)
        out = "Quot" if e.op == "/" else "Rem"
        r = b.comp("Divider", {"width": W}, {"A": ax, "B": ay}, [out])[out]
        flip = b.gate("XOR", [sx, sy]) if e.op == "/" else sx
        return b.ext(b.mux(flip, neg(r), r), Nn, False)

    def shrink(self, ops, W, S):
        """Width at which an operation on `ops` (evaluated in context W/S) can be done without changing the result."""
        if S: return W
        m = 1
        for e in ops:
            w, s, free = self.info(e)
            if not free: return W
            if self.is_const(e):
                v = self.ci(e)
                if v < 0: return W
                m = max(m, v.bit_length() or 1)
            else: m = max(m, w)
        return min(W, m)

    def shift(self, x, amt, W, kind):
        b = self.b
        if amt.k == "c":
            n = amt.x
            if n >= W:
                return b.slice(x, W - 1, W - 1) if False else (b.ext(b.slice(x, W - 1, W - 1), W, True) if kind == "ar" else b.const(0, W))
            if n == 0: return x
            sw = max(1, clog2(W))
            return b.comp("Shifter", {"width": W, "shift": kind}, {"In": x, "Shift": b.const(n, sw)}, ["Out"])["Out"]
        sw = max(1, clog2(W))
        if (1 << amt.w) <= W:
            return b.comp("Shifter", {"width": W, "shift": kind}, {"In": x, "Shift": b.ext(amt, sw, False)}, ["Out"])["Out"]
        low = b.slice(amt, 0, sw - 1) if amt.w > sw else b.ext(amt, sw, False)
        r = b.comp("Shifter", {"width": W, "shift": kind}, {"In": x, "Shift": low}, ["Out"])["Out"]
        big = b.cmp(amt, b.const(W, amt.w), False, "LT") if W < (1 << amt.w) else None
        fill = b.ext(b.slice(x, W - 1, W - 1), W, True) if kind == "ar" else b.const(0, W)
        return b.mux(big, r, fill) if False else b.mux(big, r, fill)         # big = amt < W  -> shifted value, else fill

    # ---------------------------------------------------------------- statements: symbolic execution
    def mat_var(self, n, val):
        return self.mat(val, n.w, n)

    def mat(self, val, w, n, memo=None):
        """Turn a symbolic value (V | None | ('mux', c, a, b)) into a real signal."""
        memo = {} if memo is None else memo
        if isinstance(val, V): return val
        if val is None:
            if n is not None and n.pre is not None: return n.pre
            self.err(f"'{n.name if n else 'a variable'}' is not assigned in every case, which would need a latch; give it a value first (e.g. a default at the top)", self.line)
        if id(val) in memo: return memo[id(val)]
        _, c, a, bb = val
        r = self.b.mux(c, self.mat(a, w, n, memo), self.mat(bb, w, n, memo)); memo[id(val)] = r
        return r

    def assigned(self, st, out, nb=None):
        """Names assigned in a statement. nb: when a set is given it collects the names assigned with '<='."""
        k = st.kind
        if k == "block":
            for s in st.stmts: self.assigned(s, out, nb)
        elif k == "if":
            self.assigned(st.then, out, nb)
            if st.els: self.assigned(st.els, out, nb)
        elif k == "case":
            for _, s in st.items: self.assigned(s, out, nb)
            if st.default: self.assigned(st.default, out, nb)
        elif k == "assign":
            self.lv_names(st.lhs, out)
            if nb is not None and not st.blocking: self.lv_names(st.lhs, nb)
        elif k in ("for", "while", "repeat"): self.loop_assigned(st, out, nb)
        elif k == "taskcall":
            t = self.tasks.get(st.name)
            if t is not None:
                for (nm, d, _, _), a in zip(t.args, st.args):
                    if d != "input": self.lv_names(a, out)
        elif k in ("delay", "event", "wait") and st.body is not None: self.assigned(st.body, out, nb)
        elif k == "forever": self.assigned(st.body, out, nb)
        return out

    def lv_names(self, lv, out):
        if lv.kind == "concat":
            for p in lv.parts: self.lv_names(p, out)
        elif lv.kind == "id": out.add(lv.name)
        else: self.lv_names(lv.base, out)

    class Env:
        def __init__(self, rd=None, wr=None, mw=None, cov=None):
            self.rd, self.wr, self.mw, self.cov = rd if rd is not None else {}, wr if wr is not None else {}, mw if mw is not None else [], cov if cov is not None else {}
        def copy(self): return Mod.Env(dict(self.rd), dict(self.wr), list(self.mw), dict(self.cov))

    def exec(self, st, env, seq):
        k = st.kind; self.line = st.line
        if k == "block":
            for s in st.stmts: self.exec(s, env, seq)
        elif k == "assign":
            self.exec_assign(st, env, seq)
        elif k == "if":
            self.env = env
            c = self.b.truth(self.ev_self(st.cond)[0])
            if c.k == "c":
                br = st.then if c.x else st.els
                if br: self.exec(br, env, seq)
                return
            a = env.copy(); self.exec(st.then, a, seq)
            bb = env.copy()
            if st.els: self.exec(st.els, bb, seq)
            self.merge(env, c, a, bb)
        elif k == "case":
            self.exec_case(st, env, seq)
        elif k in ("for", "while", "repeat"): self.exec_loop(st, env, seq)
        elif k == "taskcall": self.exec_taskcall(st, env, seq)
        elif k == "delay": self.err("delays (#) are not supported in a circuit: they only mean something in a testbench", st.line)
        elif k == "event": self.err("an event control (@) inside a block cannot be built as a circuit (testbench only)", st.line)
        elif k == "wait": self.err("'wait' cannot be built as a circuit (testbench only)", st.line)
        elif k == "forever": self.err("'forever' cannot be built as a circuit (testbench only)", st.line)
        elif k == "systask": self.err(f"{st.name} is not supported in a circuit (only testbenches use it)", st.line)
        elif k == "disable": self.err("'disable' is not supported in a circuit", st.line)
        else: self.err("this statement is not supported in a circuit", st.line)

    def merge(self, env, c, a, bb):
        for attr in ("rd", "wr"):
            tgt = getattr(env, attr); A, B = getattr(a, attr), getattr(bb, attr)
            for key in set(A) | set(B):
                x, y = A.get(key, tgt.get(key)), B.get(key, tgt.get(key))
                if x is y: tgt[key] = x
                else: tgt[key] = ("mux", c, x, y)
        for key in set(a.cov) | set(bb.cov):                          # bits assigned on both branches
            env.cov[key] = a.cov.get(key, env.cov.get(key, 0)) & bb.cov.get(key, env.cov.get(key, 0))
        L = len(env.mw); nc = None
        for (m, a_, d_, e_) in a.mw[L:]: env.mw.append((m, a_, d_, self.and_en(c, e_)))
        for (m, a_, d_, e_) in bb.mw[L:]:
            nc = nc if nc is not None else self.b.inv(c); env.mw.append((m, a_, d_, self.and_en(nc, e_)))

    def exec_case(self, st, env, seq):
        self.env = env
        ew, es, _ = self.info(st.expr); ev = self.ev(st.expr, ew, es, ew)
        conds = []
        for labels, body in st.items:
            c = None
            for lab in labels:
                m = self.case_match(st, ev, ew, es, lab)
                c = m if c is None else (self.b.gate("OR", [c, m]) if not (c.k == "c" or m.k == "c") else (c if c.x else m))
            conds.append((c, body))
        def chain(i):
            env2 = env.copy()
            if i == len(conds):
                if st.default: self.exec(st.default, env2, seq)
                return env2
            c, body = conds[i]
            if c.k == "c":
                if c.x: self.exec(body, env2, seq); return env2
                return chain(i + 1)
            a = env.copy(); self.exec(body, a, seq); bb = chain(i + 1)
            self.merge(env2, c, a, bb); return env2
        res = chain(0)
        env.rd, env.wr, env.mw, env.cov = res.rd, res.wr, res.mw, res.cov

    def case_match(self, st, ev, ew, es, lab):
        b = self.b
        while lab.kind == "paren": lab = lab.x
        if lab.kind == "num" and (lab.num.xmask or lab.num.zmask):
            n = lab.num; ck = st.casekind
            wild = n.zmask | (n.xmask if ck == "casex" else 0)
            if ck == "case" or (n.xmask | n.zmask) & ~wild: self.err("x/z in a case label is only allowed in casez (z, ?) or casex (x, z, ?)", lab.line)
            wl = n.width or 32; Wc = max(ew, wl); care = mask(Wc) & ~wild
            x = b.ext(ev, Wc, False)
            return b.cmp(b.gate("AND", [x, b.const(care, Wc)]), b.const(n.bits & care, Wc), False, "EQ")
        return self.ev(N("bin", lab.line, op="==", a=st.expr, b=lab), 1, False, 1)

    def lv_parts(self, lv):
        """-> [(net, lo, hi)] from the least significant part, plus total width; for an lvalue expression."""
        if lv.kind == "concat":
            out = []
            for p in reversed(lv.parts): out += self.lv_parts(p)
            return out
        if lv.kind == "id":
            n = self.net(lv.name, lv.line); return [(n, 0, n.w - 1)]
        base = lv.base
        if base.kind != "id": self.err("only a name, a bit/part select of a name, or a {concatenation} can be assigned", lv.line)
        n = self.net(base.name, lv.line)
        if lv.kind == "index":
            if not self.is_const(lv.idx): self.err("assigning to a bit chosen by a variable index is not supported; use a case statement or a decoder", lv.line)
            i = self.ci(lv.idx) - n.lsb; lo = hi = i
        elif lv.kind == "slice": hi, lo = self.ci(lv.msb) - n.lsb, self.ci(lv.lsb) - n.lsb
        else:
            st = self.ci(lv.start) - n.lsb; w = self.ci(lv.width); lo, hi = (st, st + w - 1) if lv.dir == "+:" else (st - w + 1, st)
        if lo < 0 or hi >= n.w or lo > hi: self.err(f"the select [{hi + n.lsb}:{lo + n.lsb}] is outside '{n.name}'", lv.line)
        return [(n, lo, hi)]

    def exec_assign(self, st, env, seq):
        if seq is False and not st.blocking: self.err("use '=' (not '<=') in a combinational always block", st.line)
        if st.delay is not None: self.err("delays (#) are not supported in a circuit: they only mean something in a testbench", st.line)
        self.env = env
        if st.lhs.kind == "index" and st.lhs.base.kind == "id" and st.lhs.base.name in self.mems: return self.mem_write(st, env, seq)
        parts = self.lv_parts(st.lhs); L = sum(hi - lo + 1 for _, lo, hi in parts)
        w, s, _ = self.info(st.rhs); W = max(L, w)
        self.check_assign_width(st.rhs, L, parts[0][0].name if len(parts) == 1 else "the target", st.line)
        self.allow_xz = self.dont_care_nodes(st.rhs)
        try: val = self.ev(st.rhs, W, s, L)
        finally: self.allow_xz = set()
        self.store(parts, val, env, st.blocking)

    def store(self, parts, val, env, blocking):
        """Put val (as wide as all the parts together, least significant part first) into the variables."""
        pos = 0
        for n, lo, hi in parts:
            pw = hi - lo + 1; piece = self.b.slice(val, pos, pos + pw - 1); pos += pw
            if n.kind == "input": self.err(f"'{n.name}' is an input and cannot be assigned", self.line)
            if lo == 0 and hi == n.w - 1: new = piece
            else:
                old = env.wr.get(n.name) if not blocking else env.rd.get(n.name)
                if old is None and n.name in env.wr and blocking is False: old = env.wr.get(n.name)
                cur = old if old is not None else env.rd.get(n.name)
                if cur is None and n.pre is None: cur = self.b.const(0, n.w)      # not written yet: the end of the block checks that every bit gets a value
                old = self.mat(cur, n.w, n)
                ps = ([self.b.slice(old, hi + 1, n.w - 1)] if hi < n.w - 1 else []) + [piece] + ([self.b.slice(old, 0, lo - 1)] if lo else [])
                new = self.b.concat(ps)
            env.wr[n.name] = new
            env.cov[n.name] = env.cov.get(n.name, 0) | (mask(hi - lo + 1) << lo)
            if blocking: env.rd[n.name] = new

    # ---------------------------------------------------------------- module setup
    def eval_params(self, overrides):
        a = self.ast; self.defaults = {}
        plist = list(a.params) + [it for it in a.items if it.kind == "param"]
        for p in plist:
            self.line = p.line
            if p.name in overrides and any(p is q for q in a.params) or (p.name in overrides and p not in a.params):
                val = overrides[p.name]; if_over = True
            else:
                val = self.ci(p.value); if_over = False
            if p.rng is not None:
                w, _ = self.rng(p.rng); sg = p.signed
            elif p.value.kind == "num" and p.value.num.width: w, sg = p.value.num.width, p.value.num.signed or p.signed
            else: w, sg = 32, True
            self.params[p.name] = (val, w, sg)
            if not if_over: self.defaults[p.name] = val
            else:
                saved = self.params[p.name]; self.params[p.name] = (self.ci(p.value), w, sg); self.defaults[p.name] = self.params[p.name][0]; self.params[p.name] = saved
        for k in overrides:
            if k not in self.params: self.err(f"module '{a.name}' has no parameter '{k}'", a.line)

    def declare(self):
        a = self.ast; info = {}; order = []
        def put(name, line, **kw):
            d = info.setdefault(name, {"line": line}); order.append(name) if name not in order else None
            for k, v in kw.items():
                if v is not None: d[k] = v
        for p in a.ports: put(p.name, p.line, dir=p.dir, kind=p.netkind, signed=p.signed, rng=p.rng)
        header = list(a.header)
        for it in self.items:
            if it.kind == "portdecl":
                for p in it.ports: put(p.name, p.line, dir=p.dir, kind=p.netkind, signed=p.signed or None, rng=p.rng)
            elif it.kind == "net":
                for nm, init, ln in it.names:
                    if nm in it.arrays: self.declare_mem(it, nm, ln); continue
                    if nm in info and info[nm].get("dir"):
                        put(nm, ln, kind=it.netkind, signed=it.signed or None, rng=it.rng)
                    else: put(nm, ln, kind=it.netkind, signed=it.signed, rng=it.rng)
        for nm in header:
            if nm not in info or "dir" not in info[nm]: self.err(f"port '{nm}' has no input/output declaration", a.line)
        ports = a.ports and [p.name for p in a.ports] or header
        self.port_names = ports
        for nm in order:
            d = info[nm]; kind = d.get("kind", "wire")
            if d.get("dir") == "inout": self.err(f"'{nm}' is an inout port: bidirectional signals are not supported", d["line"])
            if kind in ("wand", "wor"): self.err(f"'{nm}': {kind} nets are not supported", d["line"])
            if kind == "time": w, lsb, sg = 64, 0, False
            elif kind == "integer": w, lsb, sg = 32, 0, True
            else: (w, lsb), sg = self.rng(d.get("rng")), bool(d.get("signed"))
            n = Net(nm, w, sg, "input" if d.get("dir") == "input" else ("reg" if kind == "time" else kind), d["line"], lsb); n.dir = d.get("dir"); n.is_reg = kind in ("reg", "integer", "time")
            if kind == "supply0" or kind == "supply1": n.kind = kind
            self.nets[nm] = n
        for nm in ports:
            n = self.nets[nm]
            if n.dir == "input": self.inputs.append(n)
            else: self.outputs.append(n)
        self.net_order = order

    def fit(self, e, pw):
        """Expression e assigned to a pw-bit target (Verilog assignment sizing)."""
        w, s, _ = self.info(e); return self.ev(e, max(pw, w), s, pw)

    def hint_last(self, first, hint):
        if hint and len(self.b.comps) > first: self.b.comps[-1]._hint = hint

    def build(self):
        a = self.ast
        self.items = self.expand_items(a.items); self.register_subprograms(self.items)
        self.declare()
        # registers written by clocked always blocks get their output signal now (so feedback works)
        for it in self.items:
            if it.kind == "always" and self.is_clocked(it):
                for v in self.reg_names(it):
                    n = self.net(v, it.line)
                    if n.pre is not None: self.err(f"'{v}' is assigned in two clocked always blocks", it.line)
                    if n.kind == "input": self.err(f"'{v}' is an input and cannot be assigned", it.line)
                    n.pre = V("s", self.b.new_sig(n.w), n.w)
        for it in self.items:
            self.line = it.line
            if it.kind == "net":
                for nm, init, ln in it.names:
                    if init is None or nm in it.arrays: continue
                    n = self.nets[nm]
                    if it.netkind == "reg": 
                        if not (init.kind == "num" and init.num.bits == 0 and not init.num.xmask and not init.num.zmask): self.err(f"'{nm}': a start value other than 0 is not possible (Logisim parts start at 0)", ln)
                    else: self.add_driver(N("assign", ln, lhs=N("id", ln, name=nm), rhs=init, hint=None))
            elif it.kind == "assign": self.add_driver(it)
            elif it.kind == "gate": self.add_gate(it)
            elif it.kind == "inst": self.add_inst(it)
            elif it.kind == "always": self.add_always(it)
            elif it.kind == "initial": self.run_initial(it)
        for n in self.nets.values():
            if n.pre is not None and n.drivers: self.err(f"'{n.name}' is driven by a clocked always block and by something else", n.line)

    def is_clocked(self, it): return bool(it.events) and any(ed for ed, _ in it.events)

    def reg_names(self, it):
        """Variables a clocked always block turns into registers (memories and scratch integers are not)."""
        names, nb = set(), set(); self.assigned(it.body, names, nb)
        return sorted(v for v in names if v not in self.mems and not (self.nets.get(v) is not None and self.nets[v].kind == "integer" and v not in nb))

    def run_initial(self, it):
        """An initial block may only start memories with constants and registers with 0 (Logisim parts start at 0)."""
        env = Mod.Env(); self.env = env
        try: self.exec(it.body, env, "init")
        except VError as ex:
            if "not supported in a circuit" in ex.msg or "cannot be built" in ex.msg or "testbench" in ex.msg:
                raise VError("an initial block can only fill memories with constants and set values to 0 (Logisim parts start at 0); everything else is for testbenches", ex.line)
            raise
        finally: self.env = None
        for nm, v in env.wr.items():
            n = self.nets.get(nm)
            if n is None or n.kind == "integer": continue
            if not (isinstance(v, V) and v.k == "c" and v.x == 0): self.err(f"'{nm}': a start value other than 0 is not possible (Logisim parts start at 0)", it.line)

    def new_driver(self, fn, targets, line):
        d = Driver(fn, targets, line)
        for n, lo, hi in targets: n.drivers.append(d)
        self.all_drivers.append(d); return d

    # ---- continuous assign
    def add_driver(self, st):
        parts = self.lv_parts(st.lhs)
        for n, lo, hi in parts:
            if n.kind == "input": self.err(f"'{n.name}' is an input and cannot be assigned", st.line)
        tri = self.tri_split(st.rhs)
        def run():
            first = len(self.b.comps); self.env = None
            L = sum(hi - lo + 1 for _, lo, hi in parts)
            if tri is not None:
                cond, data, inv = tri
                c = self.b.truth(self.ev_self(cond)[0])
                if inv: c = self.b.inv(c)
                val = self.b.mux(c, self.fit(data, L), self.b.const(0, L))
                self.warn("a tri-state driver: when it is off the net reads 0 (no high-impedance value); drivers of one bus are OR-ed", st.line)
            else:
                self.check_assign_width(st.rhs, L, parts[0][0].name if len(parts) == 1 else "the target", st.line)
                self.allow_xz = self.dont_care_nodes(st.rhs)
                try: val = self.fit(st.rhs, L)
                finally: self.allow_xz = set()
            pos = 0
            for n, lo, hi in parts:
                pw = hi - lo + 1; piece = self.b.slice(val, pos, pos + pw - 1); pos += pw
                if tri is not None: self.add_tri(n, lo, hi, piece)
                else: self.add_part(n, lo, hi, piece)
            self.hint_last(first, getattr(st, "hint", None))
        self.new_driver(run, parts, st.line)

    # ---- primitive gates
    def add_gate(self, g):
        kind = g.gate; conns = g.conns
        if kind in ("not", "buf"):
            if len(conns) < 2: self.err(f"'{kind}' needs at least one output and one input", g.line)
            outs, ins = conns[:-1], [conns[-1]]
        else:
            if len(conns) < 3: self.err(f"'{kind}' needs an output and at least two inputs", g.line)
            outs, ins = conns[:1], conns[1:]
        outparts = [self.lv_parts(o) for o in outs]
        for ps in outparts:
            if sum(h - l + 1 for _, l, h in ps) != 1: self.err(f"the output of a '{kind}' gate must be 1 bit", g.line)
        def run():
            first = len(self.b.comps); self.env = None; vs = []
            for e in ins:
                v, w, s = self.ev_self(e)
                if w != 1: self.err(f"the inputs of a '{kind}' gate must be 1 bit (use an assign for vectors)", e.line)
                vs.append(v)
            ty = {"and": "AND", "or": "OR", "nand": "NAND", "nor": "NOR", "xor": "XOR", "xnor": "XNOR", "not": "NOT", "buf": "BUFFER"}[kind]
            r = self.b.gate(ty, vs, g.hint or g.name)
            for ps in outparts:
                for n, lo, hi in ps: self.add_part(n, lo, hi, r)
            self.hint_last(first, g.hint or g.name)
        self.new_driver(run, [t for ps in outparts for t in ps], g.line)

    # ---- instances: library cells and other modules
    def add_inst(self, it):
        if it.module.startswith("vs_"): return self.add_cell(it)
        ast = self.ctx.modules.get(it.module)
        if ast is None and it.module in self.ctx.external: return self.add_ext_inst(it)
        if ast is None: self.err(f"module '{it.module}' is not defined (the file has: {', '.join(self.ctx.modules) or 'no modules'}; library parts are called vs_<Type>)", it.line)
        ov = {}
        pnames = [p.name for p in ast.params]
        for i, (nm, e) in enumerate(it.params):
            if nm is None:
                if i >= len(pnames): self.err(f"'{it.module}' has only {len(pnames)} parameter(s)", it.line)
                nm = pnames[i]
            ov[nm] = self.ci(e)
        cname, cin, cout = self.ctx.get(it.module, ov, it.line)
        self.subs.append(cname)
        order = [n for n in self.ctx.port_order(it.module)]
        pins = {}
        for i, (nm, e) in enumerate(it.conns):
            if nm is None:
                if i >= len(order): self.err(f"'{it.module}' has only {len(order)} port(s)", it.line)
                nm = order[i]
            if nm not in cin and nm not in cout: self.err(f"module '{it.module}' has no port '{nm}' (ports: {', '.join(order)})", it.line)
            if nm in pins: self.err(f"port '{nm}' is connected twice", it.line)
            pins[nm] = e
        for nm in cin:
            if pins.get(nm) is None: self.err(f"input '{nm}' of '{it.name}' is not connected", it.line)
            else: self.check_port_width(it, nm, self.info(pins[nm])[0], cin[nm], "in")
        outparts = {}
        for nm in cout:
            e = pins.get(nm)
            if e is not None:
                outparts[nm] = self.lv_parts(e); self.check_port_width(it, nm, sum(h - l + 1 for _, l, h in outparts[nm]), cout[nm], "out")
            else: self.lint(f"output '{nm}' of '{it.name}' is not connected", it.line)
        def run():
            self.env = None
            ins = {nm: self.fit(pins[nm], cin[nm]) for nm in cin}
            c = R.create("Circuit", "", {"circuit": cname}); c._hint = it.hint or it.name
            c.ins = {k: self.b.sig(v) for k, v in ins.items()}; c.outs = {}
            for nm, ps in outparts.items():
                s = self.b.new_sig(cout[nm]); c.outs[nm] = s
                self.connect_out(ps, V("s", s, cout[nm]))
            self.b.comps.append(c)
        self.new_driver(run, [t for ps in outparts.values() for t in ps], it.line)

    def add_ext_inst(self, it):
        cin, cout, order = self.ctx.external[it.module]
        if it.params: self.err(f"'{it.module}' has no parameters", it.line)
        self.subs.append(it.module)
        pins = {}
        for i, (nm, e) in enumerate(it.conns):
            if nm is None:
                if i >= len(order): self.err(f"'{it.module}' has only {len(order)} port(s)", it.line)
                nm = order[i]
            if nm not in cin and nm not in cout: self.err(f"module '{it.module}' has no port '{nm}' (ports: {', '.join(order)})", it.line)
            if nm in pins: self.err(f"port '{nm}' is connected twice", it.line)
            pins[nm] = e
        for nm in cin:
            if pins.get(nm) is None: self.err(f"input '{nm}' of '{it.name}' is not connected", it.line)
            else: self.check_port_width(it, nm, self.info(pins[nm])[0], cin[nm], "in")
        outparts = {nm: self.lv_parts(pins[nm]) for nm in cout if pins.get(nm) is not None}
        for nm in cout:
            if pins.get(nm) is None: self.lint(f"output '{nm}' of '{it.name}' is not connected", it.line)
        def run():
            self.env = None
            ins = {nm: self.fit(pins[nm], cin[nm]) for nm in cin}
            c = R.create("Circuit", "", {"circuit": it.module}); c._hint = it.hint or it.name
            c.ins = {k: self.b.sig(v) for k, v in ins.items()}; c.outs = {}
            for nm, ps in outparts.items():
                s = self.b.new_sig(cout[nm]); c.outs[nm] = s
                self.connect_out(ps, V("s", s, cout[nm]))
            self.b.comps.append(c)
        self.new_driver(run, [t for ps in outparts.values() for t in ps], it.line)

    def connect_out(self, parts, v):
        L = sum(h - l + 1 for _, l, h in parts); v = self.b.ext(v, L, False); pos = 0
        for n, lo, hi in parts:
            pw = hi - lo + 1; self.add_part(n, lo, hi, self.b.slice(v, pos, pos + pw - 1)); pos += pw

    def add_cell(self, it):
        tname = it.module[3:]; cls = R.lookup(tname)
        if cls is None: self.err(f"'{it.module}' is not a library part. Known: " + ", ".join("vs_" + "".join(ch if ch.isalnum() else "_" for ch in n) for n in R.known()), it.line)
        attrs = {}
        for nm, e in it.params:
            if nm is None: self.err("give library part settings by name: #(.width(8))", it.line)
            spec = next((a for a in cls.attrs_spec if a.name.lower() == nm.lower()), None)
            if spec is None: self.err(f"{cls.type_name} has no setting '{nm}' (settings: {', '.join(a.name for a in cls.attrs_spec) or 'none'})", it.line)
            attrs[spec.name] = self.cell_attr(cls, spec, e)
        try: proto = R.create(cls.type_name, it.name, attrs)
        except ValueError as ex: self.err(str(ex), it.line)
        ports = {p.name: p for p in proto.all_ports()}; lower = {k.lower(): k for k in ports}
        pins = {}
        for nm, e in it.conns:
            if nm is None: self.err("connect library part pins by name, e.g. .A(x), .Sum(s)", it.line)
            k = nm if nm in ports else lower.get(nm.lower())
            if k is None: self.err(f"{cls.type_name} has no pin '{nm}' (pins: {', '.join(ports)})", it.line)
            if k in pins: self.err(f"pin '{k}' is connected twice", it.line)
            pins[k] = e
        for k, p in ports.items():
            if p.direction == "in" and not p.optional and pins.get(k) is None: self.err(f"input pin {k} of {it.name} is not connected", it.line)
        outparts = {k: self.lv_parts(e) for k, e in pins.items() if e is not None and ports[k].direction == "out"}
        def run():
            self.env = None
            ins = {k: self.fit(e, ports[k].width) for k, e in pins.items() if e is not None and ports[k].direction == "in"}
            r = self.b.comp(cls.type_name, attrs, ins, list(outparts), hint=it.hint or it.name, raw=True)
            for k, ps in outparts.items(): self.connect_out(ps, r[k])
        self.new_driver(run, [t for ps in outparts.values() for t in ps], it.line)

    def cell_attr(self, cls, spec, e):
        if e.kind == "str":
            s = e.val
            if spec.kind == "list": return [int(x) for x in s.replace(" ", "").split(",") if x]
            if spec.kind == "map":
                out = {}
                for part in s.replace(" ", "").split(","):
                    if part: k, v = part.split(":"); out[int(k, 0)] = int(v, 0)
                return out
            return s
        v = self.ci(e)
        if spec.kind == "list": return [v]
        return v

    # ---- always blocks
    def add_always(self, it):
        if it.events is None: self.err("an always block without '@(...)' (for example 'always #5 ...') cannot be built as a circuit: it is for testbenches", it.line)
        allnames = set(); nb = set(); self.assigned(it.body, allnames, nb)
        if not it.events or not self.is_clocked(it):
            for v in allnames:
                if v in self.mems: self.err(f"memory '{v}' can only be written in a clocked always block (@(posedge clk))", it.line)
            names = sorted(allnames)
            nets = [self.net(v, it.line) for v in names]
            for n in nets:
                if n.kind == "input": self.err(f"'{n.name}' is an input and cannot be assigned", it.line)
            def run():
                first = len(self.b.comps); env = Mod.Env(); self.env = env
                self.exec(it.body, env, False); self.env = None
                for n in nets:
                    if n.name not in env.wr or env.cov.get(n.name, 0) != mask(n.w): self.err(f"'{n.name}' is not assigned in every case, which would need a latch; give it a value first (e.g. a default at the top)", it.line)
                    self.line = it.line; v = self.mat(env.wr[n.name], n.w, n)
                    self.add_part(n, 0, n.w - 1, v)
                self.hint_last(first, it.hint)
            self.new_driver(run, [(n, 0, n.w - 1) for n in nets], it.line)
            return
        if not all(ed for ed, _ in it.events): self.err("an always block must use either only edges (posedge/negedge) or none (@*)", it.line)
        self.seq_driver(it, self.reg_names(it))

    def seq_driver(self, it, names):
        evs = it.events
        for ed, e in evs:
            if e.kind != "id": self.err("a clock or reset in an always block must be a plain signal name", it.line)
        if len(evs) > 2: self.err("an always block can have a clock and at most one asynchronous reset", it.line)
        body = it.body
        while body.kind == "block" and len(body.stmts) == 1: body = body.stmts[0]
        asy = None; clk = evs[0]
        if len(evs) == 2:
            cond = body.cond if body.kind == "if" else None
            cn = None
            if cond is not None:
                c = cond
                while c.kind == "paren": c = c.x
                if c.kind == "id": cn, neg = c.name, False
                elif c.kind == "un" and c.op in ("!", "~") and c.x.kind == "id": cn, neg = c.x.name, True
            hit = [ev for ev in evs if cn is not None and ev[1].name == cn]
            if not hit: self.err("with two events, the first statement must be 'if (reset) ...' using one of them as the reset", it.line)
            asy = hit[0]; clk = evs[1] if evs[0] is asy else evs[0]
            if (asy[0] == "posedge") == neg: self.err(f"the reset '{cn}' is triggered on {asy[0]} but the 'if' tests the opposite level", it.line)
        nets = [self.net(v, it.line) for v in names]
        def run():
            first = len(self.b.comps); b = self.b
            clock = self.readnet(clk[1].name, it.line); trig = "rising" if clk[0] == "posedge" else "falling"
            if clock.w != 1: self.err("the clock must be 1 bit", it.line)
            active = None; resets = {}
            if asy is not None:
                rv = self.readnet(asy[1].name, it.line)
                if rv.w != 1: self.err("the reset must be 1 bit", it.line)
                active = rv if asy[0] == "posedge" else b.inv(rv)
                renv = Mod.Env(); self.env = renv; self.exec(body.then, renv, True); self.env = None
                for n in nets:
                    if n.name in renv.wr:
                        val = renv.wr[n.name]
                        if not isinstance(val, V) or val.k != "c": self.err(f"the reset value of '{n.name}' must be a constant", it.line)
                        resets[n.name] = val.x
                    else: self.err(f"'{n.name}' is assigned in the clocked part but has no reset value", it.line)
                stmt = body.els
            else: stmt = body
            env = Mod.Env(); self.env = env
            if stmt is not None: self.exec(stmt, env, True)
            self.env = None
            if asy is not None and renv.mw: self.err("a memory cannot be written in the reset branch", it.line)
            if env.mw: self.emit_mem_writes(env, clock, trig, it.line)
            for n in nets:
                val = env.wr.get(n.name)
                rv = resets.get(n.name, 0)
                en = None; pre = rv != 0
                if pre and n.w > 1: self.err(f"'{n.name}' resets to {rv}: only a 1-bit reg can reset to 1 (registers reset to 0)", it.line)
                if pre and rv != 1 and n.w == 1: self.err("the reset value must be 0 or 1", it.line)
                if not pre:
                    while isinstance(val, tuple) and (val[2] is None or val[3] is None):
                        c, hold_side = val[1], val[2] is None
                        en = (b.inv(c) if hold_side else c) if en is None else b.gate("AND", [en, b.inv(c) if hold_side else c])
                        val = val[3] if hold_side else val[2]
                    if val is None: val = None
                    if en is not None and n.w == 1 and active is not None and False: pass
                self.line = it.line
                d = self.mat(val, n.w, n) if val is not None or n.pre is not None else None
                if val is None: d = n.pre
                cell_en = en
                if n.w == 1 and cell_en is None:
                    ty, attrs = "D Flip-Flop", {"trigger": trig}; ins = {"D": d, "Clk": clock}
                    if active is not None: ins["Pre" if pre else "Clr"] = active
                else:
                    ty, attrs = "Register", {"width": n.w, "trigger": trig}; ins = {"D": d, "Clk": clock}
                    if cell_en is not None: ins["En"] = cell_en
                    if active is not None: ins["Clr"] = active
                c = R.create(ty, "", attrs); c._hint = n.name if False else None
                c.ins = {k: b.sig(v) for k, v in ins.items()}; c.outs = {"Q": n.pre.x}; b.comps.append(c)
            self.hint_last(first, it.hint)
        self.new_driver(run, [], it.line)

    # ---------------------------------------------------------------- finish
    def finish(self):
        b = self.b
        for d in list(self.all_drivers): self.run_driver(d)
        for n in self.outputs: self.resolve(n)
        for n in self.nets.values():
            if n.read: self.resolve(n)
        self.finish_mems(); self.report_unused()
        used = {n.name for n in self.inputs}; final = {n.name: n.name for n in self.inputs}
        for n in self.outputs:
            v = n.val
            if v.k == "c":
                s = b.new_sig(v.w); b.comps.append(R.create("Constant", "", {"width": v.w, "value": v.x}, outs={"Out": s})); sg = s
            else: sg = v.x
            if sg in final or sg in used:
                s2 = b.new_sig(v.w); c = R.create("BUFFER", "", {"width": v.w}, ins={"In1": sg}, outs={"Out": s2}); b.comps.append(c); sg = s2
            final[sg] = n.name; used.add(n.name)
        for name in self.net_order:
            n = self.nets[name]
            v = n.val if n.state == 2 else None
            if v is None or v.k != "s" or v.x in final or name in used: continue
            if n.kind == "input": continue
            final[v.x] = name; used.add(name)
        k = 0
        def fname(sg):
            nonlocal k
            if sg in final: return final[sg]
            while True:
                k += 1; nm = f"n{k}"
                if nm not in used: break
            used.add(nm); final[sg] = nm; return nm
        for c in b.comps:
            c.outs = {p: fname(s) for p, s in c.outs.items()}
        for c in b.comps:
            c.ins = {p: (final[s] if s in final else fname(s)) for p, s in c.ins.items()}
        ids = set(); n = 0
        for c in b.comps:
            h = getattr(c, "_hint", None)
            if h and h not in ids: c.id = h; ids.add(h)
            else: c.id = ""
        for c in b.comps:
            if not c.id:
                while True:
                    n += 1
                    if f"g{n}" not in ids: break
                c.id = f"g{n}"; ids.add(c.id)
        circ = Circuit([IOPin(x.name, x.w) for x in self.inputs], [IOPin(x.name, x.w) for x in self.outputs], b.comps)
        circ.sync()
        self.ctx.partlines[self.cname] = {c.id: getattr(c, "_line", None) or self.line for c in b.comps}
        return circ


class Ctx:
    def __init__(self, mods, external=None):
        self.external = external or {}
        self.modules = {m.name: m for m in mods}; self.memo = {}; self.stack = []; self.results = {}; self.dflt = {}; self._po = {}; self.warnings = []; self.warning_set = set(); self.partlines = {}

    def port_order(self, name):
        m = self.modules[name]
        return [p.name for p in m.ports] or list(m.header)

    def get(self, name, overrides, line=0):
        """-> (circuit name, {input: width}, {output: width}); elaborates on first use."""
        ast = self.modules[name]
        if name in self.stack: raise VError(f"module '{name}' contains itself", line)
        probe = Mod(self, ast, {}, name); probe.eval_params({})
        dflt = {k: v for k, v in probe.defaults.items()}
        m = Mod(self, ast, overrides, name); m.eval_params(overrides)
        vals = {k: m.params[k][0] for k in m.params}
        over = {k: v for k, v in vals.items() if dflt.get(k) != v}
        key = (name, tuple(sorted(over.items())))
        if key not in self.memo:
            cname = name if not over else name + "_" + "_".join(f"{k}{v}" for k, v in sorted(over.items()))
            m.cname = cname; self.stack.append(name)
            try:
                try: m.build(); circ = m.finish()
                except VError: raise
                except (ValueError, KeyError, TypeError) as ex:
                    msg = str(ex)
                    if "must be 1 to" in msg: msg = f"a value in this module is wider than {MAXW} bits (including the hidden 32-bit width of plain numbers); Logisim goes up to {MAXW}"
                    raise VError(msg, m.line)
            finally: self.stack.pop()
            self.memo[key] = (cname, {p.name: p.width for p in circ.inputs}, {p.name: p.width for p in circ.outputs})
            self.results[cname] = circ
        return self.memo[key]


def elaborate(text, top=None, external=None):
    """Verilog text -> ([(circuit name, Circuit)] with parts before the circuits that use them, name of the top circuit)."""
    mods, comments = parse_modules(text)
    return elaborate_ast(mods, top, external)


def elaborate_ast(mods, top=None, external=None):
    """The same for modules that are already parsed."""
    if not mods: raise VError("the text has no module", 1)
    seen = set()
    for m in mods:
        if m.name in seen: raise VError(f"module '{m.name}' is defined twice", m.line)
        seen.add(m.name)
    for m in mods:                                  # hint comments: attach to the node lines
        pass
    ctx = Ctx(mods, external)
    used = set()
    def scan(items):
        for it in items:
            if it.kind == "inst": used.add(it.module)
            elif it.kind == "genblock": scan(it.items)
            elif it.kind == "genfor": scan(it.body.items)
            elif it.kind == "genif": scan(it.then.items); scan(it.els.items if it.els else [])
            elif it.kind == "gencase":
                for _, body in it.items: scan(body.items)
                if it.default: scan(it.default.items)
    for m in mods: scan(m.items)
    tops = [m.name for m in mods if m.name not in used] or [mods[-1].name]
    if top is not None and top not in ctx.modules: raise VError(f"there is no module '{top}'", 1)
    order = []
    for m in mods:
        cname, _, _ = ctx.get(m.name, {}, m.line)
    for cname, circ in ctx.results.items(): order.append((cname, circ))
    return order, (top or tops[-1]), ctx
