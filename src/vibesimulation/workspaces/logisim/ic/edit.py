"""Editing the circuit from the IC view.  A chip unit that stands for exactly one gate of the circuit can be rewired or changed to another gate
type; the change is written to the circuit (so the Gate view, the JSON and the truth table follow at once, and the chips are built again).
Units that do not map to one gate (adders, counters, gates split over several chips ...) are edited in the Gate view or the JSON."""
from vibesimulation.workspaces.logisim.components.registry import ComponentRegistry as R
from vibesimulation.workspaces.logisim.core.serializer import dumps

TYPE_OF = {"AND": "AND", "NAND": "NAND", "OR": "OR", "NOR": "NOR", "XOR": "XOR", "XNOR": "XNOR", "NOT": "NOT", "BUF": "BUFFER"}
SAME_SIZE = {1: ("NOT", "BUF"), 2: ("AND2", "NAND2", "OR2", "NOR2", "XOR2", "XNOR2"), 3: ("AND3", "NAND3", "NOR3"), 4: ("AND4", "NAND4")}


def _func_ok(comp, func):
    """True when circuit part ``comp`` is a single-bit gate that the chip unit function ``func`` (NAND3, NOT ...) is exactly."""
    if comp is None or comp.library != "Gates" or comp.attrs.get("width", 1) != 1: return False
    f = {"BUFFER": "BUF"}.get(comp.type_name, comp.type_name)
    return func == f if comp.single_input else func == f"{f}{comp.n}"


def unit_gate(doc, ch, index):
    """The circuit gate that unit ``index`` of chip ``ch`` stands for, or None."""
    cell = ch.slots[index] if index < len(ch.slots) else None
    if cell is None or not cell.origin or doc.circuit is None: return None
    comp = doc.circuit.component(cell.origin)
    return comp if _func_ok(comp, ch.chip.units[index].func) else None


def pin_source(doc, ch, pin):
    """(gate, port name, 'in'|'out') for a chip pin that is an input / output of one circuit gate, else None."""
    for i, u in enumerate(ch.chip.units):
        d = dict(u.pins); ins, out = d.get("in", ()), d.get("out")
        if pin not in tuple(ins) and pin != out: continue
        g = unit_gate(doc, ch, i)
        if g is None: return None
        if pin == out: return g, "Out", "out"
        k = list(ins).index(pin)
        return (g, f"In{k + 1}", "in") if k < g.n else None
    return None


def signal_choices(doc, gate):
    """Signals the gate's input may be wired to: every single-bit signal of the circuit except the gate's own output."""
    own = gate.outs.get("Out")
    return [n for n, w in doc.circuit.signals().items() if w == 1 and n != own]


def set_input(doc, gate_id, port, signal):
    c = doc.circuit.copy(); g = c.component(gate_id)
    if g is None: return "That gate is gone."
    g.ins[port] = signal
    doc.set_text(dumps(c)); return None


def swap_choices(doc, ch):
    """Functions (NAND2 ...) this chip's gates may be changed to, with the chip each one is built with; [] when the chip is not a plain gate chip."""
    from vibesimulation.workspaces.logisim.ic import mapper
    used = [i for i, s in enumerate(ch.slots) if s is not None]
    if not used or any(unit_gate(doc, ch, i) is None for i in used): return []
    size = len(dict(ch.chip.units[used[0]].pins)["in"]) if "in" in dict(ch.chip.units[used[0]].pins) else 0
    group = SAME_SIZE.get(size, ())
    return [(f, mapper.GATE_PART[f]) for f in group if f in mapper.GATE_PART and f != ch.chip.units[used[0]].func]


def swap_type(doc, ch, func):
    """Change every used gate of the chip to the gate type of ``func`` (a 7400's NANDs become ANDs: the chip becomes a 7408)."""
    c = doc.circuit.copy(); new_t = TYPE_OF[func.rstrip("0123456789")]
    for i, s in enumerate(ch.slots):
        if s is None: continue
        old = c.component(s.origin)
        if old is None: continue
        n = R.create(new_t, old.id, {"width": 1, **({} if old.single_input or new_t in ("NOT", "BUFFER") else {"inputs": old.n})}, dict(old.ins), dict(old.outs))
        n.pos, n.facing = old.pos, old.facing
        c.components[c.components.index(old)] = n
    doc.set_text(dumps(c)); return None
