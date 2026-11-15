"""Analyses on top of the DC solver: sweeping one part's value (Multisim: DC Sweep / Parameter Sweep) and Thevenin / Norton equivalents."""
from . import components as C
from .solver import SolveError, is_ground
from .units import parse_value

SWEEPABLE = (C.Resistor, C.VoltageSource, C.CurrentSource, C.Dependent)


def sweepable_parts(nl):
    return [p for p in nl.parts if isinstance(p, SWEEPABLE)]


def probe_names(nl):
    return [f"V({n})" for n in nl.nets()] + [f"I({p.id})" for p in nl.parts]


def points(a, b, n):
    n = max(2, int(n)); return [a + (b - a) * k / (n - 1) for k in range(n)]


def sweep(nl, part_id, start, stop, n):
    """Solve the circuit for n values of one part between start and stop.
    Returns {"x": [...], "V": {net: [...]}, "I": {part id: [...]}, "errors": {index: message}} (None where a point has no solution)."""
    from . import thermal
    thermal.use(nl); base = nl.copy(); part = base.part(part_id)
    if part is None: raise ValueError(f"There is no part '{part_id}'.")
    if not isinstance(part, SWEEPABLE): raise ValueError(f"{part_id} cannot be swept (sweep a resistor, a source or a controlled source).")
    xs = points(float(start), float(stop), n)
    out = {"x": xs, "unit": part.unit, "part": part_id, "V": {k: [] for k in base.nets()}, "I": {p.id: [] for p in base.parts}, "errors": {}}
    guess = None
    for k, x in enumerate(xs):
        part.value = repr(x)
        try:
            if isinstance(part, C.Resistor) and x <= 0: raise SolveError("a resistor needs a value greater than 0")
            parts = [base._dup(q) for q in base.parts]
            from .solver import solve
            volts, res = solve(parts, guess); guess = volts
            for net in out["V"]: out["V"][net].append(volts.get(net))
            for pid in out["I"]: out["I"][pid].append(res[pid][1])
        except SolveError as e:
            out["errors"][k] = str(e)
            for net in out["V"]: out["V"][net].append(None)
            for pid in out["I"]: out["I"][pid].append(None)
    return out


def sweep_from_settings(nl, cfg=None):
    """Run the sweep saved in nl.analysis (or cfg)."""
    cfg = cfg or (nl.analysis or {}).get("sweep") or {}
    if not cfg.get("part"): raise ValueError("Choose the part to sweep.")
    return sweep(nl, cfg["part"], parse_value(cfg.get("from", 0)), parse_value(cfg.get("to", 1)), int(cfg.get("points", 21)))


def thevenin(nl, load_id):
    """What the rest of the circuit looks like from the two terminals of part `load_id` (which is taken out):
    open-circuit voltage Voc (first terminal relative to second), Thevenin resistance Rth, Norton current Isc = Voc / Rth, and the load that would get maximum power.
    Only for linear circuits (no diodes)."""
    load = nl.part(load_id)
    if load is None: raise ValueError(f"There is no part '{load_id}'.")
    if load.nterm != 2: raise ValueError(f"{load_id} has {load.nterm} terminals: choose a two-terminal part.")
    if any(p.nonlinear for p in nl.parts if p is not load): raise ValueError("Thevenin / Norton equivalents are only defined for linear circuits: this circuit has a diode, transistor or op-amp.")
    if any(p.nterm != 2 for p in nl.parts): raise ValueError("Thevenin / Norton equivalents are only available for circuits made of two-terminal parts (this one has a transformer).")
    a, b = (("0" if is_ground(n) else str(n).strip()) for n in load.nodes)
    rest = nl.copy(); rest.parts = [p for p in rest.parts if p.id != load_id]
    if not rest.parts: raise ValueError("There is nothing else in the circuit.")
    if any(getattr(p, "current_controlled", False) and str(p.extra["control"]).strip() == load_id for p in rest.parts): raise ValueError(f"{load_id} controls another part, so it cannot be removed.")
    volts, _ = _solve(rest, f"with {load_id} removed", validate=False)
    if a not in volts or b not in volts: raise ValueError(f"The other parts do not reach both terminals of {load_id}.")
    voc = volts[a] - volts[b]
    dead = rest.copy()                                               # independent sources switched off: voltage sources become 0 V, current sources 0 A
    for p in dead.parts:
        if isinstance(p, (C.VoltageSource, C.CurrentSource)): p.value = "0"
    dead.parts.append(C.CurrentSource("Itest", [b, a], "1"))         # 1 A pushed into terminal a: the voltage that appears is Rth
    try: v2, _ = _solve(dead, "with the sources off", validate=False)
    except ValueError: raise ValueError("The resistance seen from these terminals cannot be calculated (there is no path back through the circuit, so it is an open circuit).")
    rth = v2[a] - v2[b]
    return {"load": load_id, "a": a, "b": b, "voc": voc, "rth": rth, "isc": (voc / rth if abs(rth) > 1e-12 else None), "pmax": (voc * voc / (4 * rth) if rth > 1e-12 else None)}


def _solve(nl, what, validate=True):
    if validate:
        errs = nl.validate()
        if errs: raise ValueError(f"The circuit {what} is not valid: {errs[0]}")
    try: return nl.solve()
    except SolveError as e: raise ValueError(f"The circuit {what} cannot be solved: {e}")
