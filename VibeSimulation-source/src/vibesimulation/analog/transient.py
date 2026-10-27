"""Transient (time-domain) analysis: capacitors and inductors become companion models (trapezoidal rule, backward Euler for the first step),
sources follow their waveforms, diodes are solved by Newton iteration at every time step (a step that does not converge is halved)."""
import math

from . import active as A
from . import components as C
from .solver import SolveError, System, _gauss, branch_currents, solve


class Sim:
    def __init__(self, nl, method="trap"):
        errs = nl.validate()
        if errs: raise ValueError(f"The circuit is not valid: {errs[0]}")
        from . import thermal
        thermal.use(nl); self.parts = [nl._dup(p) for p in nl.parts]
        try: self.volts, res, self.bc0 = solve(self.parts, want_bcur=True)          # DC operating point at t = 0 (sources at their DC level)
        except SolveError as e: raise ValueError(f"The DC operating point cannot be found, so the transient cannot start: {e}")
        self.nodes = sorted({n for p in self.parts for n in p.nodes if n != "0"}); self.branches = [p for p in self.parts if p.branch]
        self.method = "euler" if method == "euler" else "trap"
        self.mem = {}                                                  # id -> (v, i) of capacitors / inductors at the last accepted time
        self.old = {}
        for p in self.parts:
            if isinstance(p, C.Capacitor): self.mem[p.id] = (self.volts[p.nodes[0]] - self.volts[p.nodes[1]], 0.0)
            elif isinstance(p, C.Inductor): self.mem[p.id] = (0.0, res[p.id][1])
            elif isinstance(p, A.Transformer): self.mem[(p.id, 1)] = (0.0, self.bc0.get(p.id, 0.0)); self.mem[(p.id, 2)] = (0.0, self.bc0.get(p.id + "#2", 0.0))
            elif isinstance(p, A.OpAmp): self.mem[(p.id, "X")] = self.bc0.get(p.id + "#2", 0.0); self.old[(p.id, "x")] = self.mem[(p.id, "X")]
            elif p.nterm != 2:
                for k, (ti, tj, c) in enumerate(p.caps()): self.mem[(p.id, "c", k)] = (self.volts[p.nodes[ti]] - self.volts[p.nodes[tj]], 0.0)
        self.t = 0.0; self.first = True; pass

    def _stamp(self, s, volts, dt, be):
        for p in self.parts:
            if isinstance(p, C.Capacitor):
                v0, i0 = self.mem[p.id]; c = p.number(); g = (c / dt) if be else (2 * c / dt)
                s.conductance(p.nodes[0], p.nodes[1], g); s.inject(p.nodes[0], p.nodes[1], -(g * v0 + (0.0 if be else i0)))
            elif isinstance(p, C.Inductor):
                v0, i0 = self.mem[p.id]; l = p.number(); r = (l / dt) if be else (2 * l / dt)
                s.branch_voltage(p, -(r * i0 + (0.0 if be else v0))); k = s.bidx[id(p)]; s.A[k][k] -= r
            elif hasattr(p, "tr_stamp"): p.tr_stamp(s, volts, dt, be, self.mem)
            else:
                p.stamp(s, volts)
                for k, (ti, tj, c) in enumerate(p.caps() if p.nterm != 2 else ()):                 # capacitances inside a transistor
                    v0, i0 = self.mem[(p.id, "c", k)]; g = (c / dt) if be else (2 * c / dt)
                    s.conductance(p.nodes[ti], p.nodes[tj], g); s.inject(p.nodes[ti], p.nodes[tj], -(g * v0 + (0.0 if be else i0)))

    def _try(self, t1, dt, be):
        volts = dict(self.volts); old = dict(self.old); x = None
        for it in range(60):
            s = System(self.nodes, self.branches); s.old = old; s.t = t1; s.dt = dt
            for n in self.nodes: s.conductance(n, "0", 1e-12)
            self._stamp(s, volts, dt, be)
            x = _gauss(s.A, s.b)
            for p in self.parts:
                if hasattr(p, "post"): p.post(s, x)
            new = {n: x[i] for i, n in enumerate(self.nodes)}; new["0"] = 0.0
            done = (not s.limited) and all(abs(new[n] - volts[n]) <= 1e-9 + 1e-7 * abs(new[n]) for n in self.nodes)
            volts.update(new)
            if done or not any(p.nonlinear for p in self.parts): return volts, x, old, s
        return None

    def _accept(self, t1, dt, be, volts, x, old, s_):
        bcur = branch_currents(s_, self.branches, x); cur = {}
        for p in self.parts:
            va, vb = volts[p.nodes[0]], volts[p.nodes[1]]
            if isinstance(p, C.Capacitor):
                v0, i0 = self.mem[p.id]; g = (p.number() / dt) if be else (2 * p.number() / dt)
                i = g * ((va - vb) - v0) - (0.0 if be else i0); cur[p.id] = i; self.mem[p.id] = (va - vb, i)
            elif isinstance(p, C.Inductor): cur[p.id] = bcur[p.id]; self.mem[p.id] = (va - vb, bcur[p.id])
            elif isinstance(p, C.CurrentSource): cur[p.id] = p.at(t1)
            elif p.nterm != 2: self._multi(p, volts, bcur, dt, be, cur, t1)
            else: cur[p.id] = p.res_current(volts, bcur)
        self.volts, self.old, self.t = volts, old, t1
        return cur

    def _multi(self, p, volts, bcur, dt, be, cur, t1):
        """Currents into the terminals of a transistor / op-amp / transformer (channel currents plus the capacitor currents), and the memory for the next step."""
        tc = list(p.terminal_currents(volts, bcur))
        if isinstance(p, A.Transformer):
            for j, bk in ((1, p.id), (2, p.id + "#2")):
                v = volts[p.nodes[2 * j - 2]] - volts[p.nodes[2 * j - 1]]; self.mem[(p.id, j)] = (v, bcur[bk])
        elif isinstance(p, A.OpAmp): self.mem[(p.id, "X")] = bcur[p.id + "#2"]
        else:
            for k, (ti, tj, c) in enumerate(p.caps()):
                v0, i0 = self.mem[(p.id, "c", k)]; g = (c / dt) if be else (2 * c / dt); v = volts[p.nodes[ti]] - volts[p.nodes[tj]]; ic = g * (v - v0) - (0.0 if be else i0)
                self.mem[(p.id, "c", k)] = (v, ic); tc[ti] += ic; tc[tj] -= ic
        cur[p.id] = tc[0]
        for j, sh in enumerate(p.short): cur[f"{p.id}.{sh}"] = tc[j]

    def step(self, dt, depth=0):
        """Advance by dt. Returns the part currents at the new time."""
        be = self.method == "euler" or self.first; t1 = self.t + dt
        got = self._try(t1, dt, be)
        if got is None:
            if depth >= 8: raise ValueError(f"The simulation did not converge at t = {t1:.6g} s (a diode or switching event changes too fast for this step: use more steps).")
            self.step(dt / 2, depth + 1); return self.step(dt / 2, depth + 1)
        self.first = False
        return self._accept(t1, dt, be, *got)


def run(nl, tstop, steps=1000, method="trap"):
    """Returns {"t": [...], "V": {net: [...]}, "I": {part id: [...]}} with steps + 1 samples from 0 to tstop."""
    if not (tstop > 0): raise ValueError("The stop time must be greater than 0.")
    steps = int(steps)
    if not 2 <= steps <= 200000: raise ValueError("steps must be between 2 and 200000.")
    sim = Sim(nl, method); dt = tstop / steps
    out = {"t": [0.0], "V": {n: [sim.volts[n]] for n in sim.nodes}, "I": {}}
    cur0 = {}; bc = _bc0(sim)
    for p in sim.parts:
        if p.nterm != 2:
            tc = p.terminal_currents(sim.volts, sim.bc0); cur0[p.id] = tc[0]
            for j, sh in enumerate(p.short): cur0[f"{p.id}.{sh}"] = tc[j]
            continue
        cur0[p.id] = 0.0 if isinstance(p, C.Capacitor) else (p.at(0.0) if isinstance(p, C.CurrentSource) else p.res_current(sim.volts, bc))
    out["I"] = {k: [v] for k, v in cur0.items()}
    for k in range(1, steps + 1):
        cur = sim.step(dt); out["t"].append(sim.t)
        for n in out["V"]: out["V"][n].append(sim.volts[n])
        for pid in out["I"]: out["I"][pid].append(cur[pid])
    return out


def _bc0(sim):
    """Branch currents of the operating point (the part currents a -> b of the parts that carry one)."""
    _, res = solve([p.clone() for p in sim.parts]); return {pid: r[1] for pid, r in res.items()}


def run_from_settings(nl, cfg=None):
    from .units import parse_value
    cfg = cfg or (nl.analysis or {}).get("tran") or {}
    if not cfg.get("stop"): raise ValueError("Give the stop time.")
    return run(nl, parse_value(cfg["stop"]), int(cfg.get("steps", 1000)), cfg.get("method", "trap"))


def stats(ts, ys, t_from=None):
    """mean / rms / min / max / peak-to-peak of a waveform over [t_from, end] (time-weighted, trapezoid rule)."""
    pts = [(t, y) for t, y in zip(ts, ys) if y is not None and (t_from is None or t >= t_from - 1e-18)]
    if len(pts) < 2: return None
    T = pts[-1][0] - pts[0][0]
    mean = sum((pts[k + 1][0] - pts[k][0]) * (pts[k][1] + pts[k + 1][1]) / 2 for k in range(len(pts) - 1)) / T
    ms = sum((pts[k + 1][0] - pts[k][0]) * (pts[k][1] ** 2 + pts[k][1] * pts[k + 1][1] + pts[k + 1][1] ** 2) / 3 for k in range(len(pts) - 1)) / T
    ys2 = [y for _, y in pts]
    return {"mean": mean, "rms": math.sqrt(max(ms, 0.0)), "min": min(ys2), "max": max(ys2), "pp": max(ys2) - min(ys2), "final": ys2[-1]}


def frequency(ts, ys):
    """Estimate of the frequency (Hz) from rising crossings of the mean level; None if fewer than two."""
    st = stats(ts, ys)
    if not st: return None
    m = st["mean"]; ups = []
    for k in range(len(ys) - 1):
        if ys[k] < m <= ys[k + 1] and ys[k + 1] != ys[k]: ups.append(ts[k] + (m - ys[k]) / (ys[k + 1] - ys[k]) * (ts[k + 1] - ts[k]))
    return (len(ups) - 1) / (ups[-1] - ups[0]) if len(ups) >= 2 else None
