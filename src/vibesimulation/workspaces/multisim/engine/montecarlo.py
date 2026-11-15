"""Monte Carlo analysis: every resistor, capacitor, inductor and potentiometer takes a random value inside its tolerance, the circuit is measured,
and the spread of the result is reported (mean, standard deviation, extremes, percentiles, histogram and the share of runs inside given limits).
Tolerance of a part: its "tol" setting in percent ("5" = ±5 %); parts without one use the default tolerance given to the analysis."""
import math
import random

from . import components as C
from . import measure as M
from . import thermal
from .active import Potentiometer
from .units import parse_value

TOLERANT = (C.Resistor, C.Capacitor, C.Inductor, Potentiometer)


def tolerance_of(part, default=0.0):
    try: t = parse_value(str(part.extra.get("tol", "0")).replace("%", ""))
    except (ValueError, TypeError): t = 0.0
    return (t if t else default) / 100.0


def tolerant_parts(nl): return [p for p in nl.parts if isinstance(p, TOLERANT)]


def perturb(nl, rng, default_tol=0.0, dist="gauss"):
    """A copy of the circuit with random values. gauss: standard deviation = tol/3, cut at ±tol. uniform: anywhere in ±tol."""
    c = nl.copy()
    for p in tolerant_parts(c):
        t = tolerance_of(p, default_tol)
        if t <= 0 or p.value is None: continue
        r = rng.uniform(-1, 1) if dist == "uniform" else max(-1.0, min(1.0, rng.gauss(0, 1) / 3))
        p.value = repr(p.number() * (1 + t * r))
    return c


def percentile(sorted_xs, q):
    if not sorted_xs: return None
    k = (len(sorted_xs) - 1) * q; lo, hi = math.floor(k), math.ceil(k)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (k - lo)


def histogram(xs, bins=20):
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-300 * max(1.0, abs(hi)): return {"edges": [lo, hi], "counts": [len(xs)]}
    w = (hi - lo) / bins; counts = [0] * bins
    for x in xs: counts[min(bins - 1, int((x - lo) / w))] += 1
    return {"edges": [lo + w * k for k in range(bins + 1)], "counts": counts}


def stats(xs, limits=None):
    s = sorted(xs); n = len(s); mean = sum(s) / n; var = sum((x - mean) ** 2 for x in s) / (n - 1) if n > 1 else 0.0
    out = {"n": n, "mean": mean, "std": math.sqrt(var), "min": s[0], "max": s[-1], "p5": percentile(s, 0.05), "p50": percentile(s, 0.5), "p95": percentile(s, 0.95), "hist": histogram(s)}
    if limits and (limits[0] is not None or limits[1] is not None):
        lo, hi = limits; out["yield"] = sum((lo is None or x >= lo) and (hi is None or x <= hi) for x in s) / n
    return out


def run(nl, spec, runs=200, default_tol=0.0, dist="gauss", seed=None, limits=None, label=None):
    """-> {"runs", "failed", "samples": {label: [values]}, "stats": {label: stats}, "nominal": {label: value}, "tolerant": [part ids]}"""
    M.check_spec(nl, spec); runs = int(runs)
    if not 2 <= runs <= 20000: raise ValueError("Use between 2 and 20000 runs.")
    if dist not in ("gauss", "uniform"): raise ValueError("The distribution is gauss or uniform.")
    used = [p.id for p in tolerant_parts(nl) if tolerance_of(p, default_tol) > 0]
    if not used: raise ValueError('No part has a tolerance. Give resistors, capacitors or inductors a "tol" (percent) or set a default tolerance.')
    rng = random.Random(seed); samples, failed = {}, 0
    nominal = M.evaluate(nl, spec)
    for _ in range(runs):
        got = M.evaluate(perturb(nl, rng, default_tol, dist), spec)
        if all(v is None for v in got.values()): failed += 1; continue
        for k, v in got.items():
            if v is not None: samples.setdefault(k, []).append(v)
    thermal.use(nl)
    if not samples: raise ValueError("None of the random circuits could be solved.")
    st = {k: stats(v, limits if (label in (None, k)) else None) for k, v in samples.items()}
    return {"runs": runs, "failed": failed, "samples": samples, "stats": st, "nominal": nominal, "tolerant": used}
