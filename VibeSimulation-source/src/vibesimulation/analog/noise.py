"""Noise analysis (small signal, like SPICE's .noise).

Every noisy part becomes a random current source between two nodes, with a power density in A²/Hz at the DC operating point:
  resistor / potentiometer   4kT / R                      (thermal)
  diode, LED, Zener          2q·|Id|                      (shot)
  bipolar transistor         2q·|Ic| (collector-emitter) and 2q·|Ib| (base-emitter)
  MOSFET, JFET, IGBT         4kT · 2/3 · gm  (drain-source)  (channel thermal)
Flicker (1/f) noise, base resistance and op-amp input noise are not modelled (op-amps are noise free).
For each frequency the circuit is solved once per source with the independent sources turned off; the output noise density is
sqrt(Σ |H_k|² · S_k) with H_k the transfer from source k to the output. Input-referred noise divides by the gain from a chosen source."""
import math

from . import ac as AC
from . import active as A
from . import components as C
from . import thermal
from .solver import SolveError, System, _gauss
from .units import parse_value

K, Q = thermal.K, thermal.Q


def sources(prep):
    """[(part id, node a, node b, S in A²/Hz, kind)] for the circuit at its operating point."""
    parts, volts, _, _ = prep; kT = K * thermal.kelvin(thermal.temp()); out = []
    for p in parts:
        if isinstance(p, A.Potentiometer):
            r1, r2 = p.rs(); out += [(p.id, p.nodes[0], p.nodes[1], 4 * kT / r1, "thermal"), (p.id, p.nodes[1], p.nodes[2], 4 * kT / r2, "thermal")]
        elif isinstance(p, C.Resistor): out.append((p.id, p.nodes[0], p.nodes[1], 4 * kT / p.number(), "thermal"))
        elif isinstance(p, C.Diode):
            i = abs(p.current(volts[p.nodes[0]], volts[p.nodes[1]], 0.0))
            if i > 0: out.append((p.id, p.nodes[0], p.nodes[1], 2 * Q * i, "shot"))
        elif isinstance(p, A.BJT):
            I, Jc, _v = p.currents_at(volts)
            out += [(p.id, p.nodes[0], p.nodes[2], 2 * Q * abs(I[0]), "shot (Ic)"), (p.id, p.nodes[1], p.nodes[2], 2 * Q * abs(I[1]), "shot (Ib)")]
        elif isinstance(p, A.FET):
            I, Jc, _v = p.currents_at(volts); gm = abs(Jc[0][0])
            if gm > 0: out.append((p.id, p.nodes[0], p.nodes[2], 4 * kT * (2.0 / 3.0) * gm, "channel thermal"))
    return [x for x in out if x[3] > 0]


def _system(prep, w):
    parts, volts, nodes, branches = prep
    for leak in (0.0, 1e-12):
        s = System(nodes, branches)
        for n in nodes: s.conductance(n, "0", leak)
        for p in parts: AC._stamp(p, s, w, volts)
        try: _gauss([r[:] for r in s.A], s.b[:]); return s
        except SolveError: continue
    raise ValueError("The circuit cannot be solved for noise (a floating part?).")


def _solve(s, inj=()):
    A_ = [r[:] for r in s.A]; b = s.b[:]
    for a, c, i in inj:
        ia, ic = s._i(a), s._i(c)
        if ia is not None: b[ia] -= i
        if ic is not None: b[ic] += i
    return _gauss(A_, b)


def _v(s, x, n): i = s._i(n); return 0j if i is None else x[i]


def run(nl, out_node, f1, f2, points=100, ref_node="0", input_source=None):
    """-> {"f", "onoise" (V/√Hz), "inoise" (V/√Hz or A/√Hz at the input, when input_source is given), "gain", "contrib": {part id: [V²/Hz]},
    "total_rms" (V over the band), "by_part_rms": {part id: V}, "kinds": {part id: kinds}}"""
    out_node, ref_node = (("0" if str(n).strip().lower() in ("0", "gnd", "ground") else str(n).strip()) for n in (out_node, ref_node))
    if out_node not in set(nl.nets()): raise ValueError(f"The circuit has no net '{out_node}' to look at the noise on.")
    if out_node == ref_node: raise ValueError("The output and the reference net are the same.")
    fs = AC.freqs(parse_value(f1), parse_value(f2), points, True)
    prep = AC.prepare(nl); parts = prep[0]
    for p in parts:
        if isinstance(p, (C.VoltageSource, C.CurrentSource)): p.extra["ac"] = "0"
    src = None
    if input_source:
        src = next((p for p in parts if p.id == input_source and isinstance(p, (C.VoltageSource, C.CurrentSource))), None)
        if src is None: raise ValueError(f"'{input_source}' is not a voltage or current source of this circuit.")
    srcs = sources(prep)
    if not srcs: raise ValueError("Nothing in this circuit makes noise (add resistors, diodes or transistors).")
    res = {"f": fs, "onoise": [], "contrib": {}, "kinds": {}, "gain": [], "inoise": []}
    for pid, a, b, S, kind in srcs: res["contrib"].setdefault(pid, [0.0] * len(fs)); res["kinds"].setdefault(pid, set()).add(kind)
    for k, f in enumerate(fs):
        s = _system(prep, 2 * math.pi * f); tot = 0.0
        for pid, a, b, S, kind in srcs:
            x = _solve(s, [(a, b, 1.0)]); h = abs(_v(s, x, out_node) - _v(s, x, ref_node)); c = S * h * h
            res["contrib"][pid][k] += c; tot += c
        res["onoise"].append(math.sqrt(tot))
        if src is not None:
            src.extra["ac"] = "1"; s2 = _system(prep, 2 * math.pi * f); src.extra["ac"] = "0"
            x = _solve(s2); g = abs(_v(s2, x, out_node) - _v(s2, x, ref_node)); res["gain"].append(g)
            res["inoise"].append(res["onoise"][-1] / g if g > 1e-30 else None)
    if src is None: del res["gain"], res["inoise"]
    def band(vals):                                             # integral of a density (V²/Hz) over the band, trapezoid rule
        return sum((vals[i] + vals[i + 1]) / 2 * (fs[i + 1] - fs[i]) for i in range(len(fs) - 1))
    res["total_rms"] = math.sqrt(band([v * v for v in res["onoise"]]))
    res["by_part_rms"] = {pid: math.sqrt(band(v)) for pid, v in res["contrib"].items()}
    res["kinds"] = {k: sorted(v) for k, v in res["kinds"].items()}
    thermal.use(nl)
    return res
