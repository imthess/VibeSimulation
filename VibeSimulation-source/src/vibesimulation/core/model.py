"""The circuit model: ports, components and the circuit that connects them.

Design notes
- ``Component`` is an abstract base class (Template Method): each component type in
  ``vibesimulation.components`` fills in its ports, behaviour, symbol and Logisim attributes.
- ``Circuit`` only knows components through this interface, so a new component never needs
  changes here.
"""
import copy
import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .bits import mask
from .orient import wrap_body, wrap_draw, wrap_ports


# ----------------------------------------------------------------------------- attributes / ports
@dataclass(frozen=True)
class Attr:
    """One setting of a component (like Logisim's attribute table)."""
    name: str
    kind: str            # "int", "choice", "bool" or "list" (of whole numbers)
    default: object
    label: str = ""
    lo: int = 1
    hi: int = 32
    choices: tuple = ()

    def coerce(self, value):
        if self.kind == "int":
            v = int(value)
            if not self.lo <= v <= self.hi:
                raise ValueError(f"{self.label or self.name} must be {self.lo} to {self.hi}")
            return v
        if self.kind == "list":
            if not isinstance(value, (list, tuple)) or not value or not all(isinstance(x, int) and x >= 1 for x in value):
                raise ValueError(f"{self.label or self.name} must be a list of positive whole numbers")
            return [int(x) for x in value]
        if self.kind == "map":            # memory contents: {address: value}; a plain list means addresses 0, 1, 2 ...
            items = enumerate(value) if isinstance(value, (list, tuple)) else (value.items() if isinstance(value, dict) else None)
            if items is None: raise ValueError(f"{self.label or self.name} must be an object like {{\"0\": 5, \"1\": 255}} (address: value) or a list")
            out = {}
            for k, v in items:
                try: a = int(str(k), 0); x = int(v) if not isinstance(v, str) else int(v, 0)
                except (TypeError, ValueError): raise ValueError(f"{self.label or self.name}: '{k}': {v} is not an address and a whole number")
                if a < 0 or x < 0: raise ValueError(f"{self.label or self.name}: negative numbers are not allowed")
                if x: out[a] = x
            return out
        if self.kind == "str":
            return str(value)
        if self.kind == "choice":
            if value not in self.choices:
                raise ValueError(f"{self.label or self.name} must be one of {', '.join(map(str, self.choices))}")
            return value
        return bool(value)


@dataclass(frozen=True)
class Port:
    """A connection point. dx/dy are relative to the component's Logisim location."""
    name: str
    direction: str       # "in" or "out"
    width: int
    dx: int
    dy: int
    side: str            # which way a wire leaves the pin: left / right / top / bottom
    label: str = ""
    optional: bool = False
    default: object = 0  # value used when an optional input is left unconnected


def side_of(dx, dy, body, direction):
    """Edge of the body rectangle a pin sits on (decides the wire's approach direction)."""
    x0, y0, x1, y1 = body
    d = {"left": abs(dx - x0), "right": abs(x1 - dx), "top": abs(dy - y0), "bottom": abs(y1 - dy)}
    pref = ("left", "top", "bottom", "right") if direction == "in" else ("right", "top", "bottom", "left")
    return min(pref, key=lambda s: (d[s], pref.index(s)))


def make_port(name, direction, width, dx, dy, body, label="", optional=False, default=0):
    return Port(name, direction, width, dx, dy, side_of(dx, dy, body, direction), label or name, optional, default)


class IOPin:
    """A circuit input or output pin (Logisim 'Pin')."""
    def __init__(self, name, width=1):
        self.name, self.width = name, width
        self.pos = None        # (x, y) where the user dragged this pin to; None = automatic


# ----------------------------------------------------------------------------- component
class Component(ABC):
    type_name = ""        # the "type" written in the JSON
    logisim_name = ""     # the name Logisim knows it by
    library = ""          # Logisim library: Wiring, Gates, Plexers, Arithmetic, Memory, I/O
    category = ""         # palette group
    summary = ""
    attrs_spec = ()       # tuple of Attr
    handles_error = False  # True if the component copes with error ('E') inputs itself

    def __init__(self, cid, attrs=None, ins=None, outs=None):
        self.id = cid
        self.attrs = {a.name: copy.copy(a.default) for a in self.attrs_spec}
        for k, v in (attrs or {}).items():
            self.set_attr(k, v)
        self.ins = dict(ins or {})     # port name -> signal name
        self.outs = dict(outs or {})
        self.pos = None                # (x, y) where the user dragged the part to; None = placed automatically
        self.facing = "east"           # orientation (layout state, never written to the JSON)

    # ---- settings
    def spec(self, name):
        return next((a for a in self.attrs_spec if a.name == name), None)

    def set_attr(self, name, value):
        a = self.spec(name)
        if a is None:
            raise ValueError(f"{self.type_name} has no setting '{name}'")
        self.attrs[name] = a.coerce(value)

    # ---- sequential parts (flip-flops, registers, counters, the clock): they remember something between clock edges
    sequential = False
    show_optional = False              # draw optional input pins even when unconnected (so they can be wired up)
    state_outs = ()                    # output pins that only show the remembered state (they start every calculation)
    comb_in = ()                       # input pins that change outputs at once (e.g. the counter's Up/Down -> Carry)

    def init_state(self):
        return {}

    def seeds(self):
        """Signals that are known before anything is calculated (remembered values), for ordering."""
        return [self.outs[n] for n in self.state_outs if self.outs.get(n)] if self.sequential else []

    def needs(self):
        """Input pins whose signals must be calculated before this part."""
        return [p.name for p in self.in_ports() if not self.sequential or p.name in self.comb_in]

    def outputs(self, st, args):
        """Output pins from the remembered state st (and the comb_in inputs in args)."""
        return {}

    def step(self, st, args, tick):
        """The state after the inputs args (and clock tick number) are applied to state st."""
        return st

    def sim_signature(self):
        return (self.type_name, tuple(sorted((k, str(v)) for k, v in self.attrs.items())))

    _raw = 0                           # >0 while a method runs in its east-facing form (see core/orient.py)

    def __init_subclass__(cls, **kw):
        """Orientation for free: every component is written facing east; these wrappers turn it (see core/orient.py)."""
        super().__init_subclass__(**kw)
        for name, wrap in (("all_ports", wrap_ports), ("body", wrap_body), ("draw", wrap_draw)):
            fn = cls.__dict__.get(name)
            if fn is not None and not getattr(fn, "__isabstractmethod__", False): setattr(cls, name, wrap(fn))

    # ---- things each component type provides
    @abstractmethod
    def all_ports(self):
        """Every pin the component can have (list of Port)."""

    @abstractmethod
    def body(self):
        """Rectangle (x0, y0, x1, y1) of the drawn body, relative to the Logisim location."""

    @abstractmethod
    def evaluate(self, v):
        """v: input port -> int (or None for error). Returns output port -> int (or None)."""

    @abstractmethod
    def draw(self, r, ax, ay, ctx):
        """Draw the symbol with its Logisim location at (ax, ay) using Renderer r."""

    def logisim_attrs(self):
        return {}

    def bounds(self):
        """Overall rectangle including pin stubs (used to keep components apart)."""
        x0, y0, x1, y1 = self.body()
        for p in self.active_ports():
            x0, y0, x1, y1 = min(x0, p.dx), min(y0, p.dy), max(x1, p.dx), max(y1, p.dy)
        return x0, y0, x1, y1

    def check(self):
        """Extra validation specific to this component (list of messages)."""
        return []

    # ---- ports in use
    def active_ports(self):
        out = []
        for p in self.all_ports():
            if p.optional and not self.show_optional and (self.ins if p.direction == "in" else self.outs).get(p.name) is None:
                continue
            out.append(p)
        return out

    def in_ports(self):
        return [p for p in self.all_ports() if p.direction == "in"]

    def out_ports(self):
        return [p for p in self.all_ports() if p.direction == "out"]

    def port(self, name):
        return next((p for p in self.all_ports() if p.name == name), None)

    # ---- JSON
    def to_dict(self):
        d = {"id": self.id, "type": self.type_name}
        for a in self.attrs_spec:
            if self.attrs[a.name] != a.default:
                d[a.name] = ({str(k): v for k, v in sorted(self.attrs[a.name].items())} if a.kind == "map" else self.attrs[a.name])
        if self.ins: d["in"] = dict(self.ins)
        if self.outs: d["out"] = dict(self.outs)
        return self.add_pos(d)

    def add_pos(self, d):
        if self.pos: d["pos"] = [int(self.pos[0]), int(self.pos[1])]
        return d

    def load_pos(self, d):
        v = d.get("pos")
        if v is None: self.pos = None; return
        if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in v)):
            raise ValueError(f'{self.id}: "pos" must be two numbers, e.g. [300, 120]')
        self.pos = (int(round(v[0] / 10.0)) * 10, int(round(v[1] / 10.0)) * 10)

    def load_dict(self, d):
        """Fill pin connections from a parsed JSON dict (settings were applied by the factory)."""
        self.load_pos(d)
        for key, target, ports in (("in", self.ins, self.in_ports), ("out", self.outs, self.out_ports)):
            val = d.get(key, {})
            if isinstance(val, str): val = [val]
            if isinstance(val, list):      # positional: the pins in their usual order
                names = [p.name for p in ports()]
                if len(val) > len(names):
                    raise ValueError(f'{self.id}: "{key}" lists {len(val)} signals but {self.type_name} has only {len(names)} pins ({", ".join(names)})')
                val = {n: s for n, s in zip(names, val) if s is not None}
            if not isinstance(val, dict):
                raise ValueError(f'"{key}" of {self.id} must be an object such as {{"pin": "signal"}}')
            target.update({str(k): str(s) for k, s in val.items()})

    def clone(self):
        return copy.deepcopy(self)


# ----------------------------------------------------------------------------- circuit
class Circuit:
    def __init__(self, inputs=None, outputs=None, components=None):
        self.inputs = list(inputs or [])          # IOPin
        self.outputs = list(outputs or [])        # IOPin (width follows the driving signal)
        self.components = list(components or [])
        self.wires = {}                           # signal -> [[x1, y1, x2, y2], ...]: routes the user drew by hand
        self._flat = None

    def copy(self):
        c = copy.deepcopy(self); c._flat = None
        return c

    # ---- subcircuits: simulation works on the "flat" circuit, where every subcircuit part is replaced by its contents
    def has_subs(self):
        return any(getattr(c, "is_sub", False) for c in self.components)

    def flat(self, depth=0):
        if not self.has_subs(): return self
        if self._flat is None:
            if depth > 24: raise ValueError("circuits contain each other too deeply (or themselves)")
            out = Circuit(self.inputs, self.outputs, [])
            for c in self.components:
                out.components += self._expand(c, depth) if getattr(c, "is_sub", False) else [c]
            self._flat = out
        return self._flat

    def _expand(self, c, depth):
        from . import project
        from ..components.registry import ComponentRegistry as R
        inner = project.lookup(c.attrs["circuit"])
        if inner is None: raise ValueError(f"{c.id}: there is no circuit called '{c.attrs['circuit']}'")
        inner, pre, rn, res = inner.flat(depth + 1), c.id + "/", {}, []
        for p in inner.inputs:
            s = c.ins.get(p.name)
            if s is None:           # nothing connected: Logisim would leave it floating; here it reads as 0
                rn[p.name] = pre + p.name
                res.append(R.create("Constant", pre + "const_" + p.name, {"width": p.width, "value": 0}, outs={"Out": pre + p.name}))
            else: rn[p.name] = s
        for p in inner.outputs:
            rn[p.name] = c.outs.get(p.name) or pre + p.name
        for ic in inner.components:
            n = ic.clone(); n.id = pre + ic.id
            n.ins = {k: rn.get(v, pre + v) for k, v in ic.ins.items()}
            n.outs = {k: rn.get(v, pre + v) for k, v in ic.outs.items()}
            res.append(n)
        return res

    def has_seq(self):
        return any(c.sequential for c in self.flat().components)

    def sync(self):
        """Make each output pin as wide as the signal that drives it."""
        w = self.signals()
        for o in self.outputs:
            o.width = w.get(o.name, o.width)
        return self

    # ---- lookups
    def input_names(self): return [p.name for p in self.inputs]
    def output_names(self): return [p.name for p in self.outputs]
    def component(self, cid): return next((c for c in self.components if c.id == cid), None)

    def signals(self):
        """signal name -> width for everything that is driven (inputs and component outputs)."""
        w = {p.name: p.width for p in self.inputs}
        for c in self.components:
            for p in c.out_ports():
                s = c.outs.get(p.name)
                if s is not None and s not in w:
                    w[s] = p.width
        return w

    def all_signal_names(self):
        return list(self.signals())

    def driver_of(self, signal):
        for p in self.inputs:
            if p.name == signal: return ("input", p.name)
        for c in self.components:
            for p in c.out_ports():
                if c.outs.get(p.name) == signal: return (c.id, p.name)
        return None

    # ---- checking
    def validate(self, loose=False):
        """loose=True: a half-built circuit (no inputs or outputs yet) is fine, like in Logisim while you are still drawing."""
        errs, seen_ids, driven = [], set(), {p.name: "input" for p in self.inputs}
        if not loose and not self.inputs: errs.append("No inputs defined")
        if not loose and not self.outputs: errs.append("No outputs defined")
        for c in self.components:
            if c.id in seen_ids: errs.append(f"Two components share the id '{c.id}'")
            seen_ids.add(c.id)
            errs += [f"{c.id}: {m}" for m in c.check()]
            known = {p.name for p in c.all_ports()}
            for name in list(c.ins) + list(c.outs):
                if name not in known:
                    errs.append(f"{c.id}: {c.type_name} has no pin '{name}' (pins: {', '.join(sorted(known))})")
            for p in c.in_ports():
                if not loose and not p.optional and c.ins.get(p.name) is None:      # loose (editing): a floating input is allowed, like Logisim
                    errs.append(f"{c.id}: input pin {p.name} is not connected")
            for p in c.out_ports():
                s = c.outs.get(p.name)
                if s is None: continue
                if s in driven: errs.append(f"Signal '{s}' is driven more than once")
                else: driven[s] = c.id
        widths = self.signals()
        for c in self.components:
            for p in c.in_ports():
                s = c.ins.get(p.name)
                if s is None: continue
                if s not in driven: errs.append(f"{c.id}: input {p.name} uses '{s}', which nothing drives")
                elif widths.get(s) != p.width:
                    errs.append(f"{c.id}: pin {p.name} is {p.width} bit(s) but '{s}' is {widths.get(s)} bit(s)")
        for o in self.outputs:
            if o.name not in driven: errs.append(f"Output '{o.name}' is not driven by anything")
        if not errs:
            try:
                if self.flat().order() is None: errs.append("Circuit contains a loop")
            except ValueError as e: errs.append(str(e))
        return errs

    def order(self):
        """Components in a calculation order (None if there is a loop)."""
        have = {p.name for p in self.inputs}
        for c in self.components: have |= set(c.seeds())     # remembered values are there from the start (this is what lets feedback loops through flip-flops work)
        need = {id(c): [c.ins[n] for n in c.needs() if c.ins.get(n) is not None] for c in self.components}      # ports are looked up once per part
        todo, done = list(self.components), []
        while todo:
            ready = [c for c in todo if all(s in have for s in need[id(c)])]
            if not ready: return None
            rs = {id(c) for c in ready}
            for c in ready:
                done.append(c); have |= {s for s in c.outs.values()}
            todo = [c for c in todo if id(c) not in rs]
        return done

    # ---- running
    def simulate(self, invals, state=None):
        """Value of every signal for the given input values (ints; None = error).
        state: remembered values of the sequential parts {id: dict} (see core/sim.py); None = every part freshly reset."""
        f = self.flat()
        if f is not self: return f.simulate(invals, state)
        v = {p.name: (invals.get(p.name, 0) & mask(p.width)) for p in self.inputs}
        state = state if state is not None else {}
        for c in self.components:
            if c.sequential:
                st = state.get(c.id) or c.init_state()
                for n, x in c.outputs(st, {}).items():
                    if n in c.state_outs and c.outs.get(n) is not None: v[c.outs[n]] = x
        for c in self.order() or []:
            if c.sequential:
                st = state.get(c.id) or c.init_state()
                args = {p.name: v.get(c.ins.get(p.name)) for p in c.in_ports() if p.name in c.comb_in}
                for n, x in c.outputs(st, args).items():
                    if c.outs.get(n) is not None: v[c.outs[n]] = x
                continue
            args = {}
            for p in c.in_ports():
                s = c.ins.get(p.name)
                if s is not None: args[p.name] = v.get(s)
                elif not p.optional: args[p.name] = None
                else: args[p.name] = p.default
            if not c.handles_error and any(x is None for x in args.values()):
                res = {}
            else:
                res = c.evaluate(args)
            for p in c.out_ports():
                s = c.outs.get(p.name)
                if s is None: continue
                x = res.get(p.name) if (res or c.handles_error) else None
                v[s] = None if x is None else x & mask(p.width)
        return v

    def table(self, max_bits=12):
        """(input names, hidden names, output names, rows) or None when there are too many input bits."""
        if sum(p.width for p in self.inputs) > max_bits or self.has_seq():
            return None
        outs = list(dict.fromkeys(self.output_names()))
        mids = [s for c in (self.order() or []) for s in c.outs.values() if s not in outs]
        mids = list(dict.fromkeys(mids))
        names = self.input_names()
        rows = []
        for combo in itertools.product(*[range(1 << p.width) for p in self.inputs]):
            v = self.simulate(dict(zip(names, combo)))
            rows.append([v[n] for n in names + mids + outs])
        return names, mids, outs, rows

    # ---- JSON in/out
    def to_dict(self, layout=False):
        """layout=False (the default) leaves out positions, wire routes and orientation: those are layout state."""
        def pin(p, wide):
            if p.width == 1 and not (layout and p.pos): return p.name
            d = {"name": p.name}
            if wide and p.width != 1: d["width"] = p.width
            if layout and p.pos: d["pos"] = [int(p.pos[0]), int(p.pos[1])]
            return d
        gates = [c.to_dict() for c in self.components]
        if not layout:
            for g in gates: g.pop("pos", None)
        d = {"inputs": [pin(p, True) for p in self.inputs],
             "outputs": [pin(p, False) for p in self.outputs],
             "gates": gates}
        if layout and self.wires: d["wires"] = {k: [list(x) for x in v] for k, v in self.wires.items()}
        return d
