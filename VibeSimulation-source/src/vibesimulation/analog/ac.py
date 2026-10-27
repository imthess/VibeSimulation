"""AC analysis (phasors): small-signal solution at one frequency, frequency sweep (Bode), pass-band metrics and power.
Capacitors and inductors become complex admittances / impedances, diodes are linearised around the DC operating point, the AC sources are the
phasors  ac ∠ phase.  Angles are in degrees, magnitudes are peak values (RMS = peak / √2)."""
import cmath
import math

from . import components as C
from .solver import SolveError, System, _gauss, branch_currents, solve


def prepare(nl):
    """DC operating point first (it fixes the diodes' small-signal conductance). Returns (parts, node voltages, node list, branch parts)."""
    errs = nl.validate()
    if errs: raise ValueError(f"The circuit is not valid: {errs[0]}")
    from . import thermal
    thermal.use(nl); parts = [nl._dup(p) for p in nl.parts]
    try: volts, _ = solve(parts)
    except SolveError as e: raise ValueError(f"The DC operating point cannot be found, so the AC analysis cannot start: {e}")
    nodes = sorted({n for p in parts for n in p.nodes if n != "0"}); branches = [p for p in parts if p.branch]
    return parts, volts, nodes, branches


def _terminal_currents(p, V, bcur, w, volts): return p.ac_currents(V, bcur, w, volts)


def _stamp(p, s, w, volts):
    if p.nterm != 2: p.ac_stamp(s, w, volts)
    elif isinstance(p, C.Capacitor): s.conductance(p.nodes[0], p.nodes[1], 1j * w * p.number())
    elif isinstance(p, C.Inductor): s.branch_voltage(p, 0.0); k = s.bidx[id(p)]; s.A[k][k] -= 1j * w * p.number()
    elif isinstance(p, C.VoltageSource): s.branch_voltage(p, p.phasor())
    elif isinstance(p, C.CurrentSource): s.inject(p.nodes[0], p.nodes[1], p.phasor())
    elif isinstance(p, C.Diode): s.conductance(p.nodes[0], p.nodes[1], p.gsmall(volts[p.nodes[0]] - volts[p.nodes[1]]))
    else: p.stamp(s, volts)


def _current(p, V, bcur, w, volts):
    if p.nterm != 2: return p.ac_currents(V, bcur, w, volts)[0]
    va, vb = V[p.nodes[0]], V[p.nodes[1]]
    if isinstance(p, C.Capacitor): return 1j * w * p.number() * (va - vb)
    if isinstance(p, C.CurrentSource): return p.phasor()
    if isinstance(p, C.Diode): return p.gsmall(volts[p.nodes[0]] - volts[p.nodes[1]]) * (va - vb)
    return p.res_current(V, bcur)


def point(prep, f):
    """Solve at frequency f (Hz). Returns {"f", "V": {net: phasor}, "parts": {id: {"v", "i", "s"}}} (s = V·I*/2: real part = average power absorbed, imaginary = reactive power)."""
    parts, volts, nodes, branches = prep; w = 2 * math.pi * f
    def build(leak):
        nonlocal s
        s = System(nodes, branches)
        for n in nodes: s.conductance(n, "0", leak)
        for p in parts: _stamp(p, s, w, volts)
        return _gauss(s.A, s.b)
    s = None
    try: x = build(0.0)
    except SolveError:
        try: x = build(1e-12)
        except SolveError as e: raise ValueError(str(e))
    V = {n: x[i] for i, n in enumerate(nodes)}; V["0"] = 0j
    bcur = branch_currents(s, branches, x)
    out = {}
    for p in parts:
        v = V[p.nodes[0]] - V[p.nodes[1]]; i = _current(p, V, bcur, w, volts)
        if p.nterm != 2: out[p.id + "#t"] = p.ac_currents(V, bcur, w, volts)
        out[p.id] = {"v": v, "i": i, "s": sum(V[n] * c.conjugate() for n, c in zip(p.nodes, _terminal_currents(p, V, bcur, w, volts))) / 2 if p.nterm != 2 else v * i.conjugate() / 2}
    return {"f": f, "V": V, "parts": out}


def power_summary(prep, pt):
    """What the independent sources deliver at this frequency: real P (W), reactive Q (var), apparent |S| (VA), power factor."""
    P = Q = 0.0
    for p in prep[0]:
        if isinstance(p, (C.VoltageSource, C.CurrentSource)):
            s = pt["parts"][p.id]["s"]; P -= s.real; Q -= s.imag
    S = math.hypot(P, Q)
    return {"P": P, "Q": Q, "S": S, "pf": (P / S if S > 1e-30 else None), "leading": Q < 0}


def freqs(f1, f2, n, log=True):
    n = max(2, int(n))
    if f1 <= 0 or f2 <= f1: raise ValueError("The frequency range must satisfy 0 < from < to.")
    if log: return [f1 * (f2 / f1) ** (k / (n - 1)) for k in range(n)]
    return [f1 + (f2 - f1) * k / (n - 1) for k in range(n)]


def sweep(nl, f1, f2, n=100, log=True):
    """Frequency response. Returns {"f": [...], "V": {net: [phasor]}, "I": {part id: [phasor]}, "Z": {source id: [impedance seen by that source]}}."""
    prep = prepare(nl); fs = freqs(f1, f2, n, log)
    if not any(isinstance(p, (C.VoltageSource, C.CurrentSource)) and p.is_ac() for p in prep[0]):
        raise ValueError("No source has an AC part. Give a voltage or current source an 'ac' amplitude (right-click > Edit source…).")
    V = {k: [] for k in prep[2]}; I = {p.id: [] for p in prep[0]}
    tmap = {}
    for p in prep[0]:
        if p.nterm != 2:
            for j, sh in enumerate(p.short): I[f"{p.id}.{sh}"] = []; tmap[f"{p.id}.{sh}"] = (p.id, j)
    Z = {p.id: [] for p in prep[0] if isinstance(p, C.VoltageSource)}
    for f in fs:
        pt = point(prep, f)
        for k in V: V[k].append(pt["V"][k])
        for pid in I:
            if pid in tmap: base, j = tmap[pid]; I[pid].append(pt["parts"][base + "#t"][j])
            else: I[pid].append(pt["parts"][pid]["i"])
        for pid in Z:
            i = pt["parts"][pid]["i"]; v = pt["parts"][pid]["v"]; Z[pid].append(-v / i if abs(i) > 1e-30 else None)
    return {"f": fs, "V": V, "I": I, "Z": Z, "log": log}


def db(x): return -400.0 if abs(x) < 1e-20 else 20 * math.log10(abs(x))


def unwrap_deg(zs):
    out, prev, off = [], None, 0.0
    for z in zs:
        if z is None or abs(z) < 1e-30: out.append(None); continue
        a = math.degrees(cmath.phase(z))
        if prev is not None:
            while a + off - prev > 180: off -= 360
            while a + off - prev < -180: off += 360
        out.append(a + off); prev = a + off
    return out


def _cross(f, m, k0, k1, level):
    """Frequency where |m| crosses `level` between samples k0 and k1 (log-frequency interpolation)."""
    a, b = m[k0], m[k1]
    if a == b: return f[k0]
    t = (level - a) / (b - a); lf0, lf1 = math.log(f[k0]), math.log(f[k1])
    return math.exp(lf0 + t * (lf1 - lf0))


def metrics(fs, zs, fn=None):
    """Shape of a magnitude response: reference (peak) gain, -3 dB corner(s), type (low-pass / high-pass / band-pass / flat), bandwidth, Q, roll-off."""
    m = [abs(z) if z is not None else 0.0 for z in zs]; k = max(range(len(m)), key=lambda i: m[i]); peak = m[k]; fpk = fs[k]
    mag = (lambda f: abs(fn(f) or 0.0)) if fn else None
    if mag and 0 < k < len(fs) - 1:                               # the samples are only a net: look for the true top between the neighbours of the highest sample
        lo, hi = math.log(fs[k - 1]), math.log(fs[k + 1])
        for _ in range(60):
            a, b = lo + (hi - lo) / 3, hi - (hi - lo) / 3
            if mag(math.exp(a)) < mag(math.exp(b)): lo = a
            else: hi = b
        f2 = math.exp((lo + hi) / 2)
        if mag(f2) >= peak: fpk, peak = f2, mag(f2)
    out = {"peak": peak, "f_peak": fpk, "kind": "flat", "f_low": None, "f_high": None, "f0": None, "bw": None, "q": None, "rolloff_db_per_dec": None}
    if peak < 1e-20: return out
    lv = peak / math.sqrt(2)
    def refine(fa, fb, f0):                                          # bisection on log f for |z| = lv, between a sample above the level and one below it
        if not mag: return f0
        la, lb = math.log(fa), math.log(fb); ua = mag(fa) >= lv
        for _ in range(50):
            lm = (la + lb) / 2; um = mag(math.exp(lm)) >= lv
            if um == ua: la = lm
            else: lb = lm
        return math.exp((la + lb) / 2)
    for j in range(k, len(m) - 1):
        if m[j] >= lv > m[j + 1]: out["f_high"] = refine(fs[j], fs[j + 1], _cross(fs, m, j, j + 1, lv)); break
    for j in range(k, 0, -1):
        if m[j] >= lv > m[j - 1]: out["f_low"] = refine(fs[j], fs[j - 1], _cross(fs, m, j - 1, j, lv)); break
    lo, hi = out["f_low"], out["f_high"]
    if lo and hi:
        out["kind"] = "band-pass"; out["f0"] = math.sqrt(lo * hi); out["bw"] = hi - lo; out["q"] = out["f0"] / out["bw"]
    elif hi: out["kind"] = "low-pass"
    elif lo: out["kind"] = "high-pass"
    n = len(fs)
    if n > 4 and out["kind"] in ("low-pass", "high-pass", "band-pass"):             # slope over the last half-decade of the edge that rolls off
        a, b = (n - 1, max(0, n - 1 - n // 4)) if out["kind"] != "high-pass" else (min(n - 1, n // 4), 0)      # (far end, near end) of the stretch measured
        if m[a] > 0 and m[b] > 0 and fs[a] != fs[b]: out["rolloff_db_per_dec"] = (db(m[a]) - db(m[b])) / math.log10(fs[a] / fs[b])
    return out
