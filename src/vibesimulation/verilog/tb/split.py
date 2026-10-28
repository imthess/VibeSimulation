"""Splits a testbench module into the part that is a circuit and the part that is a program.

Program (run by the interpreter): `initial` blocks, `always` blocks with delays / event waits / system tasks.
Circuit (built like any module): everything else - assigns, gates, DUT instances, ordinary always blocks.

Pins between the two:
  * a reg the circuit reads and nothing in the circuit drives is an *input pin* (the program drives it, or it stays 0);
  * a net the circuit drives is an *output pin* (so the program, the log and the waveforms can see it).
Variables only the program uses stay in the interpreter.
"""
from dataclasses import dataclass, field
from ..astutil import walk
from ..lexer import VError
from ..parser import N

BEHAVIOURAL = {"delay", "event", "wait", "forever", "systask", "disable"}
REGKINDS = {"reg", "integer", "time"}


def needs_simulator(item):
    """True for a block that only a simulator can run (it waits, or prints)."""
    if item.kind not in ("initial", "always"): return False
    if item.kind == "always" and item.events is None: return True
    return any(n.kind in BEHAVIOURAL for n in walk(item.body))


def has_processes(mod):
    """A module is a testbench when some block in it waits or prints. (An `initial` block that only sets constants
    is not enough: that is how memories of a normal design are filled.)"""
    return any(needs_simulator(it) for it in mod.items)


def is_behavioural(item):
    """In a testbench every initial and always block is run by the interpreter."""
    return item.kind in ("initial", "always")


def names_in(x):
    return {n.name for n in walk(x) if n.kind == "id"}


def lvalue_names(e):
    return {n.name for n in walk(e) if n.kind == "id"}


def assigned_in(x, tasks):
    """Names the statements write (task output arguments included)."""
    out = set()
    for n in walk(x):
        if n.kind == "assign":
            for m in walk(n.lhs):
                if m.kind == "id": out.add(m.name); break
        elif n.kind == "taskcall" and n.name in tasks:
            for (nm, d, _, _), a in zip(tasks[n.name].args, n.args):
                if d != "input":
                    for m in walk(a):
                        if m.kind == "id": out.add(m.name); break
    return out


@dataclass
class Design:
    module: object                                   # the module as a circuit (processes removed, pins added)
    original: object                                 # the module as written
    processes: list = field(default_factory=list)
    pins_in: list = field(default_factory=list)      # variables that drive the circuit
    pins_out: list = field(default_factory=list)     # nets the circuit drives
    local_arrays: set = field(default_factory=set)


def split(mod):
    procs = [it for it in mod.items if is_behavioural(it)]
    rest = [it for it in mod.items if not is_behavioural(it)]
    tasks = {it.name: it for it in mod.items if it.kind == "task"}
    nets = [it for it in mod.items if it.kind == "net"]
    netnames = {nm for it in nets for nm, _, _ in it.names}
    regnames = {nm for it in nets if it.netkind in REGKINDS for nm, _, _ in it.names if nm not in it.arrays}
    arrays = {nm for it in nets for nm in it.arrays}
    written = assigned_in(procs, tasks)
    used_by_procs = names_in(procs)
    circuit_items = [it for it in rest if it.kind not in ("function", "task", "net")]
    used_by_circuit = names_in(circuit_items)
    for a in arrays & used_by_procs:
        if a in used_by_circuit: raise VError(f"the memory '{a}' is used by the program and by the circuit part of the testbench: that is not supported", mod.line)
    # what the circuit part drives
    driven = set()
    for it in nets:
        if it.netkind not in REGKINDS: driven |= {nm for nm, init, _ in it.names if init is not None}
    for it in circuit_items:
        if it.kind == "assign": driven |= lvalue_names(it.lhs)
        elif it.kind == "gate": driven |= lvalue_names(it.conns[0]) if it.gate not in ("not", "buf") else set().union(*[lvalue_names(c) for c in it.conns[:-1]])
        elif it.kind == "inst":
            for _, e in it.conns:
                if e is not None: driven |= lvalue_names(e)
        elif it.kind == "always": driven |= assigned_in(it.body, {})
    circ_regs = {n for it in circuit_items if it.kind == "always" for n in assigned_in(it.body, {})}
    pins_in = sorted(n for n in regnames if n in used_by_circuit and n not in circ_regs and n not in arrays)
    pins_out = sorted(n for n in netnames if n in driven and n not in pins_in and n not in arrays and n not in written)
    cleaned = []
    for it in rest:
        if it.kind == "net":
            names = []; arr = dict(it.arrays)
            for nm, init, ln in it.names:
                if nm in arrays and nm in used_by_procs: arr.pop(nm, None); continue
                names.append((nm, None if nm in written or nm in pins_in else init, ln))
            if names: cleaned.append(N("net", it.line, netkind=it.netkind, signed=it.signed, rng=it.rng, names=names, arrays=arr))
        else: cleaned.append(it)
    new = N("module", mod.line, name=mod.name, ports=list(mod.ports), items=cleaned, header=list(mod.header), params=list(mod.params))
    extra = [N("port", mod.line, name=n, dir="input", netkind="wire", signed=False, rng=None) for n in pins_in] + \
            [N("port", mod.line, name=n, dir="output", netkind="wire", signed=False, rng=None) for n in pins_out]
    if extra:
        if new.ports: new.ports += extra
        else:
            new.header += [p.name for p in extra]; new.items = [N("portdecl", mod.line, ports=extra)] + new.items
    return Design(new, mod, procs, pins_in, pins_out, {a for a in arrays if a in used_by_procs})
