"""Edits as small Command objects (Command pattern).

Every edit made in the circuit view (add a gate, rewire a pin, rename a signal ...) is one of these
classes. ``Document.run(command)`` applies it to a copy of the circuit and stores the resulting JSON as
a new undo step, so the JSON box, the circuit and the undo history always agree.
"""
from abc import ABC, abstractmethod

from .model import IOPin

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def fresh_signal(circuit, prefix="n"):
    used = set(circuit.signals()) | set(circuit.output_names())
    k = 1
    while f"{prefix}{k}" in used:
        k += 1
    return f"{prefix}{k}"


def fresh_id(circuit, prefix="g"):
    k = 1
    while circuit.component(f"{prefix}{k}"):
        k += 1
    return f"{prefix}{k}"


class Command(ABC):
    @abstractmethod
    def apply(self, circuit):
        """Change the circuit in place (it is already a private copy)."""


class AddInput(Command):
    def __init__(self, width=1, pos=None):
        self.width, self.pos = width, pos

    def apply(self, c):
        used = set(c.signals()) | set(c.output_names())
        name = next((ch for ch in LETTERS if ch not in used), None) or f"I{len(c.inputs) + 1}"
        pin = IOPin(name, self.width)
        if self.pos: pin.pos = (int(self.pos[0]), int(self.pos[1]))
        c.inputs.append(pin)


class DeleteInput(Command):
    def __init__(self, name):
        self.name = name

    def apply(self, c):
        c.inputs = [p for p in c.inputs if p.name != self.name]


class SetInputWidth(Command):
    def __init__(self, name, width):
        self.name, self.width = name, width

    def apply(self, c):
        for p in c.inputs:
            if p.name == self.name:
                p.width = self.width


class RenameSignal(Command):
    def __init__(self, old, new):
        self.old, self.new = old, new

    def apply(self, c):
        for p in c.inputs + c.outputs:
            if p.name == self.old:
                p.name = self.new
        for comp in c.components:
            comp.ins = {k: (self.new if v == self.old else v) for k, v in comp.ins.items()}
            comp.outs = {k: (self.new if v == self.old else v) for k, v in comp.outs.items()}


class AddOutput(Command):
    def __init__(self, signal, pos=None):
        self.signal, self.pos = signal, pos

    def apply(self, c):
        pin = IOPin(self.signal, 1)
        if self.pos: pin.pos = (int(self.pos[0]), int(self.pos[1]))
        c.outputs.append(pin)


class RotatePart(Command):
    """Turn a part (Logisim's Facing). steps=1 is a quarter turn clockwise; facing=... sets it directly."""
    def __init__(self, cid, steps=1, facing=None):
        self.cid, self.steps, self.facing = cid, steps, facing

    def apply(self, c):
        from .orient import next_facing
        comp = c.component(self.cid)
        if comp is None: raise ValueError(f"no part '{self.cid}'")
        comp.facing = self.facing or next_facing(comp.facing, self.steps)
        c.wires = {}          # pins moved: let the router draw the wires again (hand-drawn routes would no longer meet the pins)


class ChangeOutput(Command):
    """Show a different signal on an output pin (new=None removes the pin)."""
    def __init__(self, old, new):
        self.old, self.new = old, new

    def apply(self, c):
        c.outputs = [IOPin(self.new, 1) if p.name == self.old else p for p in c.outputs] if self.new else [p for p in c.outputs if p.name != self.old]


class AddComponent(Command):
    """Add a part; its input pins are hooked to existing signals of the right width (or to new circuit inputs)."""
    def __init__(self, type_name, attrs=None, pos=None, facing="east", wired=True):
        self.type_name, self.attrs, self.pos, self.facing, self.wired = type_name, dict(attrs or {}), pos, facing, wired      # wired=False: pins left floating (Logisim: place, then draw the wires)

    def apply(self, c):
        from ..components.registry import ComponentRegistry
        comp = ComponentRegistry.create(self.type_name, fresh_id(c), self.attrs)
        used = []
        for p in comp.in_ports():
            if not self.wired: break
            if p.optional and not getattr(comp, "is_sub", False):
                continue
            cands = [s for s, w in c.signals().items() if w == p.width]
            pick = next((s for s in cands if s not in used), cands[0] if cands else None)
            if pick is None:
                pick = next((ch for ch in LETTERS if ch not in set(c.signals()) | set(c.output_names())), f"I{len(c.inputs) + 1}")
                c.inputs.append(IOPin(pick, p.width))
            comp.ins[p.name] = pick
            used.append(pick)
        outs = [p for p in comp.out_ports() if not p.optional]
        for p in outs:
            comp.outs[p.name] = fresh_signal(c, "n") if len(outs) == 1 else f"{comp.id}_{p.name}"
        if self.pos: comp.pos = (int(self.pos[0]), int(self.pos[1]))
        comp.facing = self.facing
        c.components.append(comp)
        c.sync()
        if not c.outputs and comp.outs:
            c.outputs.append(IOPin(next(iter(comp.outs.values())), 1))


class DeleteComponent(Command):
    def __init__(self, cid):
        self.cid = cid

    def apply(self, c):
        comp = c.component(self.cid)
        if comp is None:
            return
        gone = set(comp.outs.values())
        c.components.remove(comp)
        c.outputs = [o for o in c.outputs if o.name not in gone]
        for other in c.components:                                      # parts that listened to it are left with a floating pin (Logisim)
            for port in [k for k, v in other.ins.items() if v in gone]: other.ins.pop(port)
        for net in gone: c.wires.pop(net, None)


class SetAttrs(Command):
    def __init__(self, cid, attrs):
        self.cid, self.attrs = cid, attrs

    def apply(self, c):
        comp = c.component(self.cid)
        for k, v in self.attrs.items():
            comp.set_attr(k, v)


class Rewire(Command):
    """Connect an input pin of a part to a signal (None disconnects an optional pin)."""
    def __init__(self, cid, port, signal):
        self.cid, self.port, self.signal = cid, port, signal

    def apply(self, c):
        comp = c.component(self.cid)
        if self.signal is None:
            comp.ins.pop(self.port, None)
        else:
            comp.ins[self.port] = self.signal


class SetOutputSignal(Command):
    """Connect/disconnect an optional output pin of a part (names the new signal)."""
    def __init__(self, cid, port, signal):
        self.cid, self.port, self.signal = cid, port, signal

    def apply(self, c):
        comp = c.component(self.cid)
        if self.signal is None:
            gone = comp.outs.pop(self.port, None)
            c.outputs = [o for o in c.outputs if o.name != gone]
        else:
            comp.outs[self.port] = self.signal
        c.sync()


class ChangeGateType(Command):
    def __init__(self, cid, type_name):
        self.cid, self.type_name = cid, type_name

    def apply(self, c):
        from ..components.registry import ComponentRegistry
        old = c.component(self.cid)
        cls = ComponentRegistry.lookup(self.type_name)
        ins = [old.ins.get(f"In{i + 1}") for i in range(old.n)]
        new = cls(old.id, {"width": old.attrs["width"]})
        if not new.single_input:
            new.attrs["inputs"] = max(2, len(ins))
        names = [f"In{i + 1}" for i in range(new.n)]
        pool = [s for s in ins if s] or [next(iter(c.signals()))]
        new.ins = {n: (pool[i] if i < len(pool) else pool[0]) for i, n in enumerate(names)}
        new.outs = dict(old.outs)
        c.components[c.components.index(old)] = new


class MovePart(Command):
    """The user dragged a part: remember where it now sits (Logisim grid units)."""
    def __init__(self, cid, x, y, wires=None):
        self.cid, self.x, self.y, self.wires = cid, x, y, wires      # wires: every signal's route after the move (kept like Logisim does)

    def apply(self, c):
        comp = c.component(self.cid)
        if comp is None: raise ValueError(f"no part '{self.cid}'")
        comp.pos = (int(self.x), int(self.y))
        if self.wires is not None: c.wires = {k: [list(t) for t in v] for k, v in self.wires.items()}


class ClearPositions(Command):
    """Go back to the automatic arrangement (one part, or all of them)."""
    def __init__(self, cid=None):
        self.cid = cid

    def apply(self, c):
        for comp in c.components:
            if self.cid is None or comp.id == self.cid: comp.pos = None
        if self.cid is None:
            c.wires = {}
            for p in c.inputs + c.outputs: p.pos = None


class SetWire(Command):
    """The user dragged a wire: remember the whole hand-made route of that signal (None = automatic again)."""
    def __init__(self, net, segs, others=None):
        self.net, self.segs, self.others = net, segs, others          # others: the routes of all other signals, kept as they are

    def apply(self, c):
        if self.others is not None: c.wires = {k: [list(t) for t in v] for k, v in self.others.items() if k != self.net}
        if self.segs: c.wires[self.net] = [list(s) for s in self.segs]
        else: c.wires.pop(self.net, None)


class MovePin(Command):
    """The user dragged an input or output pin of the circuit."""
    def __init__(self, kind, name, x, y, wires=None):
        self.kind, self.name, self.x, self.y, self.wires = kind, name, x, y, wires

    def apply(self, c):
        pin = next((p for p in (c.inputs if self.kind == "in" else c.outputs) if p.name == self.name), None)
        if pin is None: raise ValueError(f"no pin '{self.name}'")
        pin.pos = (int(self.x), int(self.y))
        if self.wires is not None: c.wires = {k: [list(t) for t in v] for k, v in self.wires.items()}


class DeleteMany(Command):
    """Delete several parts at once (the selection)."""
    def __init__(self, cids):
        self.cids = list(cids)

    def apply(self, c):
        for cid in self.cids: DeleteComponent(cid).apply(c)


class MoveParts(Command):
    """Move a whole selection: new places for several parts. Hand-drawn routes of the signals that touch them are dropped (drawn again automatically)."""
    def __init__(self, places, wires=None):
        self.places, self.wires = dict(places), wires

    def apply(self, c):
        for cid, (x, y) in self.places.items():
            comp = c.component(cid)
            if comp is None: raise ValueError(f"no part '{cid}'")
            comp.pos = (int(x), int(y))
        if self.wires is not None: c.wires = {k: [list(t) for t in v] for k, v in self.wires.items()}


class PasteParts(Command):
    """Paste copied parts. Connections between the copied parts are kept (with new signal names); inputs that came from outside
    stay connected to the same signals (or become new circuit inputs if that signal does not exist here)."""
    def __init__(self, parts, places=None, facings=None, dx=0, dy=0):
        self.parts, self.places, self.facings, self.dx, self.dy = parts, places or {}, facings or {}, dx, dy

    def apply(self, c):
        from ..components.registry import ComponentRegistry
        comps = []
        for d in self.parts:
            comp = ComponentRegistry.from_dict(dict(d, id=d["id"])); comp.pos = None; comps.append(comp)
        inner = {sg for comp in comps for sg in comp.outs.values() if sg}
        rename, used, k = {}, set(c.signals()) | set(c.output_names()), 1
        for sg in sorted(inner):
            while f"n{k}" in used: k += 1
            rename[sg] = f"n{k}"; used.add(rename[sg])
        made = []
        for comp in comps:
            old = comp.id; comp.id = fresh_id(c)
            comp.ins = {pn: rename.get(v, v) for pn, v in comp.ins.items()}
            comp.outs = {pn: rename.get(v, v) for pn, v in comp.outs.items()}
            if old in self.places: comp.pos = (int(self.places[old][0] + self.dx), int(self.places[old][1] + self.dy))
            comp.facing = self.facings.get(old, "east")
            c.components.append(comp); made.append(comp)
        have = set(c.signals())
        for comp in made:
            for p in comp.in_ports():
                s = comp.ins.get(p.name)
                if s is not None and s not in have:
                    c.inputs.append(IOPin(s, p.width)); have.add(s)


class Batch(Command):
    """Several commands as one undo step."""
    def __init__(self, cmds):
        self.cmds = list(cmds)

    def apply(self, c):
        for k in self.cmds: k.apply(c)


class CutWires(Command):
    """Delete pieces of wire (Logisim: select a wire, press Delete): the pins that were only reachable through them are unplugged,
    the pieces of the signal that stay keep their hand-made route (`routes` = {signal: pieces or None for automatic})."""
    def __init__(self, routes, unplug, others=None):
        self.routes, self.unplug, self.others = routes, list(unplug), others

    def apply(self, c):
        if self.others is not None: c.wires = {k: [list(t) for t in v] for k, v in self.others.items() if k not in self.routes}
        for net, segs in self.routes.items():
            if segs: c.wires[net] = [list(s) for s in segs]
            else: c.wires.pop(net, None)
        for cid, port in self.unplug:
            comp = c.component(cid)
            if comp is not None: comp.ins.pop(port, None)
