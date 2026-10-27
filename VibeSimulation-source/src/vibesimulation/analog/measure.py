"""One measurement of a circuit: the building block of parameter sweeps, temperature sweeps and Monte Carlo.

A measurement spec is a dict:
  {"kind": "dc",   "probes": ["V(out)", "I(R1)"]}
  {"kind": "ac",   "f": "1k", "probes": ["V(out)"]}                               -> |V(out)| (peak) and its phase in degrees
  {"kind": "tran", "stop": "10m", "steps": 500, "stat": "final|peak|pp|mean|rms|max|min", "probes": ["V(out)"], "settle": 0.5}
A probe is V(net), V(a,b) (a relative to b) or I(part id). ``evaluate`` returns {label: number or None}."""
import math

from . import ac as AC
from . import thermal
from . import transient as TR
from .solver import SolveError, is_ground
from .units import parse_value

STATS = ("final", "peak", "pp", "mean", "rms", "max", "min")


def parse_probe(text):
    t = str(text).strip(); u = t.upper()
    if u.startswith("V(") and t.endswith(")"):
        a = [x.strip() for x in t[2:-1].split(",")]
        if len(a) == 1 and a[0]: return ("V", a[0], "0")
        if len(a) == 2 and all(a): return ("V", a[0], a[1])
    if u.startswith("I(") and t.endswith(")") and t[2:-1].strip(): return ("I", t[2:-1].strip())
    raise ValueError(f"'{text}' is not a probe. Write V(net), V(net1,net2) or I(part).")


def _net(n): return "0" if is_ground(n) else str(n).strip()


def check_spec(nl, spec):
    """Raise ValueError (plain words) if the spec cannot be measured on this circuit."""
    if not isinstance(spec, dict): raise ValueError("Choose what to measure.")
    kind = spec.get("kind", "dc")
    if kind not in ("dc", "ac", "tran"): raise ValueError("The measurement kind must be dc, ac or tran.")
    probes = spec.get("probes") or []
    if not probes: raise ValueError("Choose at least one probe, for example V(out).")
    nets = set(nl.nets()) | {"0"}; ids = {p.id for p in nl.parts}
    for t in probes:
        pr = parse_probe(t)
        if pr[0] == "V":
            for n in pr[1:]:
                if _net(n) not in nets: raise ValueError(f"The circuit has no net '{n}'.")
        elif pr[1] not in ids: raise ValueError(f"The circuit has no part '{pr[1]}'.")
    if kind == "ac":
        if parse_value(spec.get("f", 0)) <= 0: raise ValueError("The frequency must be greater than 0.")
    if kind == "tran":
        if parse_value(spec.get("stop", 0)) <= 0: raise ValueError("The stop time must be greater than 0.")
        if spec.get("stat", "final") not in STATS: raise ValueError("stat must be one of " + ", ".join(STATS))


def _stat(ys, stat):
    if stat == "final": return ys[-1]
    if stat == "max": return max(ys)
    if stat == "min": return min(ys)
    if stat == "pp": return max(ys) - min(ys)
    if stat == "peak": return max(abs(y) for y in ys)
    if stat == "mean": return sum(ys) / len(ys)
    if stat == "rms": return math.sqrt(sum(y * y for y in ys) / len(ys))
    raise ValueError(stat)


def evaluate(nl, spec):
    """Measure. A circuit that has no solution gives None for every label (the caller counts the failures)."""
    check_spec(nl, spec); kind = spec.get("kind", "dc"); probes = [parse_probe(t) for t in spec["probes"]]; names = list(spec["probes"])
    out = {}
    try:
        if kind == "dc":
            volts, res = nl.solve()
            for nm, p in zip(names, probes):
                out[nm] = (volts[_net(p[1])] - volts[_net(p[2])]) if p[0] == "V" else res[p[1]][1]
        elif kind == "ac":
            prep = AC.prepare(nl); pt = AC.point(prep, parse_value(spec["f"]))
            for nm, p in zip(names, probes):
                z = (pt["V"][_net(p[1])] - pt["V"][_net(p[2])]) if p[0] == "V" else pt["parts"][p[1]]["i"]
                out[f"|{nm}|"] = abs(z); out[f"∠{nm}"] = math.degrees(math.atan2(z.imag, z.real)) if abs(z) > 1e-30 else 0.0
        else:
            res = TR.run(nl, parse_value(spec["stop"]), int(spec.get("steps", 500)), spec.get("method", "trap"))
            k0 = int(len(res["t"]) * min(0.95, max(0.0, float(spec.get("settle", 0))))); stat = spec.get("stat", "final")
            for nm, p in zip(names, probes):
                if p[0] == "V": ys = [a - b for a, b in zip(res["V"].get(_net(p[1])) or [0.0] * len(res["t"]), res["V"].get(_net(p[2])) or [0.0] * len(res["t"]))]
                else: ys = res["I"][p[1]]
                out[f"{stat}({nm})"] = _stat(ys[k0:], stat)
    except (SolveError, ValueError) as e:
        if isinstance(e, ValueError) and "not valid" in str(e): raise
        labels = (list(out) if out else ([f"{pre}{nm}" for nm in names for pre in (("|", "∠") if kind == "ac" else ("",))] if kind != "tran" else [f"{spec.get('stat', 'final')}({n})" for n in names]))
        if kind == "ac": labels = [x for nm in names for x in (f"|{nm}|", f"∠{nm}")]
        return {k: None for k in labels}
    return out


def evaluate_with(nl, spec, change):
    """Measure a modified copy: change(copy) edits it first."""
    c = nl.copy(); change(c)
    try: return evaluate(c, spec)
    finally: thermal.use(nl)
