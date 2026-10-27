"""Time, events and the circuit: runs a split testbench.

One time step works like a Verilog simulator's:
  1. every process that is due runs until it waits (blocking assignments take effect at once);
  2. the non-blocking assignments are applied;
  3. the circuit part settles on the new pin values and its outputs are read back;
  4. processes whose event happened wake up; repeat from 1 until nothing is left to do at this time.
Then $strobe / $monitor print, the waveforms are sampled, and time moves to the next delay.
"""
import heapq
from collections import deque

from ...core import project, serializer, sim as CORE
from ...core.bits import mask
from ..astutil import walk
from ..elab import elaborate_ast, Ctx
from ..lexer import VError
from ..parser import N
from .format import Arg, format_args
from .interp import Finish, Interp, StepLimit
from .result import TBResult
from .rng import Random
from .runtime import Runtime
from .split import split

MAX_DELTAS = 5000


class Proc:
    def __init__(self, gen, name): self.gen, self.name = gen, name


class Simulation:
    def __init__(self, mods, top_name, max_time=100000, max_steps=2000000):
        self.max_time, self.max_steps = max_time, max_steps
        self.top = top_name; self.time = 0; self.steps = 0
        orig = next(m for m in mods if m.name == top_name)
        self.design = split(orig)
        others = [m for m in mods if m.name != top_name]
        order, _, ctx = elaborate_ast([self.design.module] + others, top_name)
        self.circuits = dict(order); self.circ = self.circuits[top_name]; self.ctx = ctx
        self.warnings = list(ctx.warnings)
        saved = (dict(project.DEFS), project.CURRENT)
        self._saved_project = saved
        project.set_project({n: serializer.dumps(c) for n, c in order}, top_name)
        self.state = CORE.fresh(self.circ); self.tick = 0
        self.values = {}; self.arrays = {}; self.rng = Random()
        self.rt_ctx = Ctx([orig], None)
        self.rt = Runtime(self.rt_ctx, orig, self.values, self.arrays, lambda: self.time, self.rng)
        for nm, m in self.rt.mems.items(): self.arrays[nm] = {}
        for nm, n in self.rt.nets.items(): self.values[nm] = 0
        for it in orig.items:                                       # start values of reg declarations
            if it.kind == "net" and it.netkind in ("reg", "integer", "time"):
                for nm, init, ln in it.names:
                    if init is not None and nm not in it.arrays: self.values[nm] = self.rt.value_in(init, self.rt.nets[nm].w)
        self.interp = Interp(self)
        self.ready = deque(); self.heap = []; self.seq = 0; self.zero = []; self.nba = []; self.timed = []
        self.waiters = []; self.strobes = []; self.monitor = None; self.monitor_last = None
        self.lines = []; self.finished = False; self.partial = ""
        self.pin_last = None
        self.sig_order = [nm for nm, n in self.rt.nets.items() if nm not in self.rt.mems]
        self.waves = {nm: [] for nm in self.sig_order}; self.last_rec = {}

    # ------------------------------------------------------------------ small services
    def tick_step(self):
        self.steps += 1
        if self.steps > self.max_steps: raise StepLimit()

    def emit(self, text, newline):
        self.partial += text + ("\n" if newline else "")
        while "\n" in self.partial:
            line, self.partial = self.partial.split("\n", 1); self.lines.append(line)

    def schedule_at(self, t, fn):
        self.seq += 1; heapq.heappush(self.heap, (t, self.seq, fn))

    def event_spec(self, st):
        rt = self.rt; evs = []
        if st.star:
            names = sorted({n.name for n in walk(st.body) if n.kind == "id" and n.name in rt.nets}) if st.body is not None else []
            evs = [(None, N("id", st.line, name=n)) for n in names]
        else: evs = list(st.events)
        out = []
        for edge, e in evs:
            out.append([edge, e, rt.value(e)[0]])
        return out

    # ------------------------------------------------------------------ the circuit
    def settle(self):
        """Apply the pin values to the circuit; read the circuit's outputs back. Returns True if anything was read back."""
        pins = {n: self.values.get(n, 0) for n in self.design.pins_in}
        if pins == self.pin_last and self.pin_last is not None: return False
        self.pin_last = dict(pins); self.tick += 1
        vals, osc = CORE.settle(self.circ, pins, self.state, self.tick)
        for n in self.design.pins_out:
            v = vals.get(n)
            self.values[n] = 0 if v is None else v
        return True

    # ------------------------------------------------------------------ events
    def check_waiters(self):
        woke = []
        for w in self.waiters:
            p, kind, spec = w
            if kind == "wait":
                if self.rt.truth(spec): woke.append(w)
                continue
            hit = False
            for item in spec:
                edge, e, last = item; new = self.rt.value(e)[0]
                if edge == "posedge": hit |= (last & 1) == 0 and (new & 1) == 1
                elif edge == "negedge": hit |= (last & 1) == 1 and (new & 1) == 0
                else: hit |= new != last
                item[2] = new
            if hit: woke.append(w)
        for w in woke:
            self.waiters.remove(w); self.ready.append(w[0])

    def advance(self, p):
        try: req = next(p.gen)
        except StopIteration: return
        kind = req[0]
        if kind == "delay":
            if req[1] <= 0: self.zero.append(p)
            else: self.schedule_at(self.time + req[1], lambda p=p: self.ready.append(p))
        elif kind == "event": self.waiters.append((p, "event", req[1]))
        elif kind == "wait": self.waiters.append((p, "wait", req[1]))

    def time_step(self):
        deltas = 0
        while True:
            deltas += 1
            if deltas > MAX_DELTAS: raise VError("the testbench keeps changing values without time passing (a zero-delay loop?)")
            while self.ready:
                self.advance(self.ready.popleft())
                self.check_waiters()
            if self.zero: self.ready.extend(self.zero); self.zero = []; continue
            if self.nba:
                batch, self.nba = self.nba, []
                for fn in batch: fn()
            self.settle(); self.check_waiters()
            if not self.ready and not self.nba and not self.zero: break
        self.end_of_step()

    def end_of_step(self):
        for fn in self.strobes: fn()
        self.strobes = []
        if self.monitor is not None:
            args = self.interp.args_of(self.monitor)
            key = tuple((a.val, a.text) for a, node in zip(args, self.monitor) if not (node.kind == "sysfn" and node.fn in ("$time", "$stime", "$realtime")))
            if key != self.monitor_last: self.monitor_last = key; self.emit(format_args(args, self.top), True)
        for nm in self.sig_order:
            v = self.values.get(nm, 0)
            if self.last_rec.get(nm) != v or not self.waves[nm]:
                self.waves[nm].append((self.time, v)); self.last_rec[nm] = v

    # ------------------------------------------------------------------ run
    def run(self):
        res = TBResult(); res.order = list(self.sig_order)
        res.widths = {nm: self.rt.nets[nm].w for nm in self.sig_order}
        res.kinds = {nm: ("input" if nm in self.design.pins_in else "output" if nm in self.design.pins_out else "variable") for nm in self.sig_order}
        try:
            self.settle()
            for i, it in enumerate(self.design.processes):
                self.ready.append(Proc(self.process(it), f"p{i}"))
            while True:
                self.time_step()
                if self.finished: break
                if not self.heap: break
                t = self.heap[0][0]
                if t > self.max_time: res.truncated = f"the time limit of {self.max_time} units was reached"; break
                self.time = t
                while self.heap and self.heap[0][0] == t: heapq.heappop(self.heap)[2]()
        except Finish: res.finished = True; self.finished = True; self.end_of_step()
        except StepLimit: res.truncated = f"the step limit of {self.max_steps} was reached (an endless loop?)"
        except VError as e: res.error = e
        finally:
            project.set_project(*self._saved_project)
        if self.partial: self.lines.append(self.partial); self.partial = ""
        res.lines = self.lines; res.waves = self.waves; res.end_time = self.time; res.warnings = self.warnings
        return res

    def process(self, it):
        """A generator for an initial or always block."""
        if it.kind == "initial":
            yield from self.interp.exec(it.body)
            return
        body = it.body
        if it.events is not None and (it.events or it.star):
            while True:
                yield ("event", self.event_spec(N("event", it.line, events=it.events, star=it.star, body=body)))
                yield from self.interp.exec(body)
        else:
            while True:
                before = self.steps
                yield from self.interp.exec(body)
                if self.steps == before: raise VError("an always block without any delay or event would run forever", it.line)
