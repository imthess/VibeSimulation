"""Verilog text -> circuits that fit the project (no state, no UI): the compile step of the VLSI section."""
from dataclasses import dataclass, field

from ..core import project as PRJ
from ..core.serializer import dumps
from ..verilog.elab import elaborate_ast
from ..verilog.lexer import VError
from ..verilog.lint import lint_modules
from ..verilog.parser import parse_modules
from ..verilog.tb.split import has_processes


@dataclass
class Compiled:
    circuits: dict                 # module name -> Circuit
    names: list                    # module names in the order of the text
    top: str                       # the module that no other module uses
    newcur: str                    # the circuit that becomes the one being shown
    rename_from: str = None        # the current circuit is renamed to the (only) module's name
    slices: dict = field(default_factory=dict)       # module name -> its own piece of the text
    errors: list = field(default_factory=list)       # [(line, message)]
    warnings: list = field(default_factory=list)     # [(line, message)]  legal but suspicious
    testbenches: dict = field(default_factory=dict)  # module name -> its piece of the text (kept apart: they are run, not built)
    partlines: dict = field(default_factory=dict)    # module name -> {part id: line of the statement that made it}


def pins_of(name):
    """External view of a circuit of the project, as the elaborator needs it for instances."""
    inner = PRJ.lookup(name)
    if inner is None: return None
    return ({p.name: p.width for p in inner.inputs}, {p.name: p.width for p in inner.outputs}, [p.name for p in inner.inputs] + [p.name for p in inner.outputs])


def compile_text(text, circuits, cur):
    """circuits: {name: json text} of the project; cur: the circuit being edited. Never changes anything."""
    try:
        allmods, _ = parse_modules(text)
        tbs = [m for m in allmods if has_processes(m)]
        mods = [m for m in allmods if m not in tbs]
        names = [m.name for m in mods]
        if not mods:
            return Compiled({}, [], "", cur, testbenches=_slices(text, allmods, tbs), errors=[] if tbs else [(1, "the text has no module")])
        rename = len(names) == 1 and names[0] != cur
        if rename and names[0] in circuits:
            return Compiled({}, names, "", cur, errors=[(mods[0].line, f"there is already another circuit called '{names[0]}'; give this module a different name")])
        ext = {}
        for n in circuits:
            if n in names or (rename and n == cur): continue
            pin = pins_of(n)
            if pin is not None: ext[n] = pin
        order, top, ctx = elaborate_ast(mods, None, ext)
        warnings = sorted(set(ctx.warnings) | set(lint_modules(mods)))
    except VError as e:
        return Compiled({}, [], "", cur, errors=[(e.line or 1, e.msg)])
    made = dict(order)
    newcur = names[0] if rename else (cur if cur in names else top)
    # the parts must make sense inside the whole project before anything is changed
    defs = {n: t for n, t in circuits.items() if not (rename and n == cur)}
    for n, c in made.items(): defs[n] = dumps(c)
    PRJ.set_project(defs, newcur)
    errs = []
    for n, c in made.items():
        for m in c.validate(loose=True): errs.append((next((mm.line for mm in mods if mm.name == n), 1), f"module '{n}': {m}"))
        if n in PRJ.uses(n): errs.append((1, f"module '{n}' contains itself"))
    slices = _slices(text, allmods, mods)
    if len(allmods) == 1: slices[mods[0].name] = text if text.endswith("\n") else text + "\n"
    return Compiled(made, names, top, newcur, cur if rename else None, slices, errs, warnings, _slices(text, allmods, tbs), ctx.partlines)


def _slices(text, allmods, wanted):
    """Each wanted module's own piece of the text (from its first line up to the next module)."""
    lines = text.split("\n"); starts = sorted(m.line for m in allmods) + [len(lines) + 1]
    out = {}
    for m in wanted:
        i = starts.index(m.line)
        out[m.name] = "\n".join(lines[m.line - 1:starts[i + 1] - 1]).rstrip() + "\n"
    return out
