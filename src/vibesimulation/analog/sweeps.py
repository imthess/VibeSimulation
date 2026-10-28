"""Parameter sweep and temperature sweep: measure the circuit again and again while one thing changes.
(``analysis.sweep`` is the older DC sweep of one source or resistor; these two use any part setting and any measurement from ``measure``.)"""
import math

from . import measure as M
from . import thermal
from .units import parse_value


def values(a, b, n, log=False):
    n = int(n)
    if not 2 <= n <= 2000: raise ValueError("Use between 2 and 2000 points.")
    a, b = float(a), float(b)
    if log:
        if a <= 0 or b <= 0: raise ValueError("A logarithmic sweep needs both ends greater than 0.")
        return [a * (b / a) ** (k / (n - 1)) for k in range(n)]
    return [a + (b - a) * k / (n - 1) for k in range(n)]


def sweepable(nl):
    """[(part id, parameter)] that can be swept: the value of any part that has one, and every numeric setting."""
    out = []
    for p in nl.parts:
        if p.value is not None and p.default is not None: out.append((p.id, "value"))
        for k, v in p.extra.items():
            if k in ("control", "state", "wave", "model"): continue
            try: parse_value(v)
            except (ValueError, TypeError): continue
            out.append((p.id, k))
    return out


def _set(part, param, x):
    if param == "value":
        if part.value is None: raise ValueError(f"{part.id} has no value to sweep.")
        part.value = repr(x)
    elif param in part.extra: part.extra[param] = repr(x)
    else: raise ValueError(f"{part.id} has no setting '{param}'.")


def _run(nl, xs, spec, apply, label):
    M.check_spec(nl, spec)
    series, fails = {}, 0
    for x in xs:
        got = M.evaluate_with(nl, spec, lambda c: apply(c, x))
        for k, v in got.items(): series.setdefault(k, []).append(v)
        fails += all(v is None for v in got.values())
    return {"x": list(xs), "label": label, "series": series, "failed": fails, "spec": spec}


def parameter_sweep(nl, part_id, param, xs, spec):
    """Measure the circuit with `part_id`'s `param` ("value" or a setting such as "pos", "gain", "vz") set to each of xs."""
    if nl.part(part_id) is None: raise ValueError(f"There is no part '{part_id}'.")
    _set(nl.copy().part(part_id), param, xs[0])                      # complains early about a bad part / setting
    def apply(c, x):
        p = c.part(part_id)
        if param == "value" and p.number is not None and x <= 0 and p.positive: raise ValueError(f"{part_id}: value must be greater than 0")
        _set(p, param, x)
    return _run(nl, xs, spec, apply, f"{part_id}.{param}")


def temperature_sweep(nl, temps, spec):
    """Measure the circuit at each temperature (°C)."""
    def apply(c, t): c.analysis = dict(c.analysis or {}); c.analysis["temp"] = t
    try: return _run(nl, temps, spec, apply, "temperature (°C)")
    finally: thermal.use(nl)
