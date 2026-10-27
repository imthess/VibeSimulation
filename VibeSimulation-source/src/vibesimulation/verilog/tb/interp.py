"""The program part of a testbench: statements run as generators that hand control back to the scheduler.

A statement generator yields a request when it has to wait:
    ("delay", n)          wait n time units
    ("event", spec)       wait for a change (spec: list of [edge, expression, last value])
    ("wait", expression)  wait until the expression is true
"""
from ...core.bits import mask
from ..astutil import walk
from ..elab import Net
from ..lexer import VError
from ..parser import N
from .format import Arg, format_args


class Finish(Exception):
    """$finish / $stop was reached."""


class Disable(Exception):
    def __init__(self, name): self.name = name


class StepLimit(Exception):
    pass


DISPLAY = {"$display": ("d", True), "$displayb": ("b", True), "$displayo": ("o", True), "$displayh": ("h", True),
           "$write": ("d", False), "$writeb": ("b", False), "$writeo": ("o", False), "$writeh": ("h", False)}
IGNORED = {"$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpall", "$dumpflush", "$dumplimit", "$timeformat", "$fflush",
           "$monitoron", "$monitoroff", "$srandom", "$random", "$urandom", "$time", "$stime"}


class Interp:
    def __init__(self, sim):
        self.sim = sim; self.rt = sim.rt

    # ------------------------------------------------------------------ helpers
    def args_of(self, args):
        out = []
        for a in args:
            if a.kind == "str": out.append(Arg(text=a.val))
            else:
                self.rt.line = a.line; v, w, s = self.rt.value(a); out.append(Arg(v, w, s))
        return out

    def write(self, parts, val):
        """Store val (all the parts' bits, least significant part first) into the variables."""
        pos = 0; vals = self.sim.values
        for n, lo, hi in parts:
            pw = hi - lo + 1; piece = val >> pos & mask(pw); pos += pw
            cur = vals.get(n.name, 0)
            vals[n.name] = (cur & ~(mask(pw) << lo) & mask(n.w)) | (piece << lo)

    def mem_target(self, lv):
        if lv.kind == "index" and lv.base.kind == "id" and lv.base.name in self.rt.mems: return self.rt.mems[lv.base.name]
        return None

    # ------------------------------------------------------------------ statements
    def exec(self, st):
        self.sim.tick_step()
        rt = self.rt; rt.line = st.line; k = st.kind
        if k == "block":
            try:
                for s in st.stmts: yield from self.exec(s)
            except Disable as d:
                if d.name != getattr(st, "label", None): raise
        elif k == "assign": yield from self.assign(st)
        elif k == "if":
            if rt.truth(st.cond): yield from self.exec(st.then)
            elif st.els is not None: yield from self.exec(st.els)
        elif k == "case": yield from self.case(st)
        elif k == "for":
            yield from self.exec(st.init)
            while rt.truth(st.cond):
                yield from self.exec(st.body); yield from self.exec(st.step); self.sim.tick_step()
        elif k == "while":
            while rt.truth(st.cond): yield from self.exec(st.body); self.sim.tick_step()
        elif k == "repeat":
            n = rt.value(st.count)[0]
            for _ in range(max(0, n)): yield from self.exec(st.body); self.sim.tick_step()
        elif k == "forever":
            while True: yield from self.exec(st.body); self.sim.tick_step()
        elif k == "delay":
            d = rt.value(st.amount)[0]
            yield ("delay", d)
            if st.body is not None: yield from self.exec(st.body)
        elif k == "event":
            yield ("event", self.sim.event_spec(st))
            if st.body is not None: yield from self.exec(st.body)
        elif k == "wait":
            if not rt.truth(st.cond): yield ("wait", st.cond)
            if st.body is not None: yield from self.exec(st.body)
        elif k == "systask": self.systask(st)
        elif k == "taskcall": yield from self.call_task(st)
        elif k == "disable": raise Disable(st.name)
        else: raise VError(f"this statement is not supported in a testbench: {k}", st.line)

    def case(self, st):
        rt = self.rt
        ew, es, _ = rt.info(st.expr); ev = rt.ev(st.expr, ew, es, ew)
        for labels, body in st.items:
            if any(rt.case_match(st, ev, ew, es, lab).x for lab in labels):
                yield from self.exec(body); return
        if st.default is not None: yield from self.exec(st.default)

    def assign(self, st):
        rt = self.rt; sim = self.sim
        m = self.mem_target(st.lhs)
        delay = rt.value(st.delay)[0] if st.delay is not None else 0
        if m is not None:
            i = rt.ci(st.lhs.idx); val = rt.value_in(st.rhs, m.w)
            apply = lambda: self.sim.arrays[m.name].__setitem__(i, val) if 0 <= i < m.depth else None
        else:
            parts = rt.lv_parts(st.lhs); L = sum(hi - lo + 1 for _, lo, hi in parts)
            val = rt.value_in(st.rhs, L)
            apply = lambda: self.write(parts, val)
        if st.blocking:
            if delay: yield ("delay", delay)
            apply()
        elif delay: sim.schedule_at(sim.time + delay, lambda: sim.nba.append(apply))
        else: sim.nba.append(apply)

    # ------------------------------------------------------------------ system tasks
    def systask(self, st):
        n = st.name; sim = self.sim
        if n in DISPLAY:
            radix, nl = DISPLAY[n]
            sim.emit(format_args(self.args_of(st.args), sim.top, radix), nl)
        elif n == "$strobe":
            args = st.args; sim.strobes.append(lambda: sim.emit(format_args(self.args_of(args), sim.top), True))
        elif n == "$monitor":
            sim.monitor = st.args; sim.monitor_last = None
        elif n in ("$finish", "$stop"): raise Finish()
        elif n in ("$readmemh", "$readmemb"): raise VError(f"{n} reads a file, and files are not available here; fill the memory with an initial block instead", st.line)
        elif n in ("$error", "$warning", "$info", "$fatal"):
            sim.emit(("ERROR: " if n in ("$error", "$fatal") else "WARNING: " if n == "$warning" else "INFO: ") + format_args(self.args_of(st.args), sim.top), True)
            if n == "$fatal": raise Finish()
        elif n in IGNORED: pass
        else: raise VError(f"{n} is not supported", st.line)

    # ------------------------------------------------------------------ user tasks (may wait)
    def call_task(self, st):
        rt = self.rt; t = rt.tasks.get(st.name)
        if t is None: raise VError(f"task '{st.name}' is not defined", st.line)
        if len(st.args) != len(t.args): raise VError(f"task '{st.name}' takes {len(t.args)} argument(s)", st.line)
        vals = self.sim.values; saved_nets = {}; saved_vals = {}; outs = []
        def decl(nm, w, sg, v=0):
            saved_nets.setdefault(nm, rt.nets.get(nm)); saved_vals.setdefault(nm, vals.get(nm))
            n = Net(nm, w, sg, "reg", st.line); n.is_reg = True; rt.nets[nm] = n; vals[nm] = v & mask(w)
        for (nm, d, rng, sg), a in zip(t.args, st.args):
            w = rt.rng(rng)[0]
            if d == "input": decl(nm, w, sg, rt.value_in(a, w))
            else: decl(nm, w, sg); outs.append((nm, a))
        for d in t.decls:
            if d.kind == "net":
                for nm, init, ln in d.names: decl(nm, 32 if d.netkind == "integer" else rt.rng(d.rng)[0], d.netkind == "integer" or bool(d.signed))
        try:
            yield from self.exec(t.body)
            results = [(vals.get(nm, 0), a) for nm, a in outs]
        finally:
            for nm, old in saved_nets.items():
                if old is None: rt.nets.pop(nm, None)
                else: rt.nets[nm] = old
            for nm, old in saved_vals.items():
                if old is None: vals.pop(nm, None)
                else: vals[nm] = old
        for v, a in results:
            parts = rt.lv_parts(a); L = sum(hi - lo + 1 for _, lo, hi in parts); self.write(parts, v & mask(L))
