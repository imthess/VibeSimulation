"""DC operating point by Modified Nodal Analysis with Newton iteration for diodes (with source stepping and gmin stepping when plain Newton fails)."""
import math

from .components import VT

GROUND = {"0", "gnd", "ground"}


def is_ground(n): return str(n).strip().lower() in GROUND


class SolveError(Exception): pass


class System:
    """The equations A x = b being built: node voltages first, then one current per voltage-like part."""
    def __init__(self, nodes, branches):
        self.idx = {n: i for i, n in enumerate(nodes)}
        self.bidx, pos = {}, len(nodes)
        for p in branches: self.bidx[id(p)] = pos; pos += getattr(p, "nbranch", 1)      # a part with two windings has two current unknowns
        self.n = pos
        self.A = [[0.0] * self.n for _ in range(self.n)]; self.b = [0.0] * self.n
        self.old = {}; self.limited = False; self.scale = 1.0
        self.t = None; self.dt = None; self.mem = {}      # transient: time, step, and what each capacitor / inductor remembers

    def _i(self, node): return self.idx.get(str(node).strip(), None)

    def conductance(self, a, b, g):
        ia, ib = self._i(a), self._i(b)
        if ia is not None: self.A[ia][ia] += g
        if ib is not None: self.A[ib][ib] += g
        if ia is not None and ib is not None: self.A[ia][ib] -= g; self.A[ib][ia] -= g

    def inject(self, a, b, i):
        """Current i flows from a through a part to b."""
        ia, ib = self._i(a), self._i(b)
        if ia is not None: self.b[ia] -= i
        if ib is not None: self.b[ib] += i

    def branch_voltage(self, part, e):
        k = self.bidx[id(part)]; ia, ib = self._i(part.nodes[0]), self._i(part.nodes[1])
        if ia is not None: self.A[ia][k] += 1; self.A[k][ia] += 1
        if ib is not None: self.A[ib][k] -= 1; self.A[k][ib] -= 1
        self.b[k] = e

    def limit(self, d, tag, vnew, nvt, is_):
        """SPICE-style junction voltage limiting so that Newton does not jump into the exponential."""
        raw = vnew; key = (id(d), tag); vold = self.old.get(key, 0.0); vcrit = nvt * math.log(nvt / (math.sqrt(2) * is_))
        if vnew > vcrit and abs(vnew - vold) > 2 * nvt:
            if vold > 0:
                arg = 1 + (vnew - vold) / nvt; vnew = vold + nvt * math.log(arg) if arg > 0 else vcrit
            else: vnew = nvt * math.log(vnew / nvt)
        self.old[key] = vnew
        if abs(vnew - raw) > 1e-12: self.limited = True      # the step was shortened: this iteration cannot count as converged
        return vnew

    # ---- controlled sources
    def vccs(self, a, b, cp, cn, g):
        ia, ib, icp, icn = self._i(a), self._i(b), self._i(cp), self._i(cn)
        for r, sg in ((ia, 1), (ib, -1)):
            if r is None: continue
            if icp is not None: self.A[r][icp] += sg * g
            if icn is not None: self.A[r][icn] -= sg * g

    def vcvs(self, part, cp, cn, k):
        self.branch_voltage(part, 0.0); kk = self.bidx[id(part)]; icp, icn = self._i(cp), self._i(cn)
        if icp is not None: self.A[kk][icp] -= k
        if icn is not None: self.A[kk][icn] += k

    def ccvs(self, part, ctrl, r):
        self.branch_voltage(part, 0.0); self.A[self.bidx[id(part)]][self.bidx[id(ctrl)]] -= r

    def cccs(self, a, b, ctrl, f):
        kc = self.bidx[id(ctrl)]; ia, ib = self._i(a), self._i(b)
        if ia is not None: self.A[ia][kc] += f
        if ib is not None: self.A[ib][kc] -= f


def branch_currents(s, branches, x):
    """{part id: current unknown} (a second unknown of the same part is 'id#2')."""
    out = {}
    for p in branches:
        k = s.bidx[id(p)]; out[p.id] = x[k]
        for j in range(1, getattr(p, "nbranch", 1)): out[f"{p.id}#{j + 1}"] = x[k + j]
    return out


def terminal_stamp(s, nodes, i0, J, v0):
    """Linearised currents INTO the part at its terminals: i_t = i0_t + sum_k J[t][k] (v_k - v0_k). Adds them to the equations."""
    for t, nt in enumerate(nodes):
        it = s._i(nt)
        if it is None: continue
        c = i0[t]
        for k, nk in enumerate(nodes):
            g = J[t][k]
            if g == 0.0: continue
            ik = s._i(nk); c -= g * v0[k]
            if ik is not None: s.A[it][ik] += g
        s.b[it] -= c


def _gauss(A, b):
    n = len(b)
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[p][c]) < 1e-18: raise SolveError("The circuit has no unique solution: check for a missing ground (node 0), a floating part, or voltage sources in a loop.")
        A[c], A[p] = A[p], A[c]; b[c], b[p] = b[p], b[c]
        for r in range(c + 1, n):
            f = A[r][c] / A[c][c]
            if f:
                for k in range(c, n): A[r][k] -= f * A[c][k]
                b[r] -= f * b[c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (b[r] - sum(A[r][k] * x[k] for k in range(r + 1, n))) / A[r][r]
    return x


def _wire_controls(parts):
    """Controlled sources need the part whose current controls them."""
    by = {p.id: p for p in parts}
    for p in parts:
        if getattr(p, "current_controlled", False):
            c = by.get(str(p.extra["control"]).strip())
            if c is None or not c.branch or c is p:
                raise SolveError(f"{p.id}: its control '{p.extra['control']}' must be a voltage source, ammeter, inductor or voltage-type controlled source in this circuit.")
            p.ctrl, p.ctrl_spice = c, c.spice_name()


def _newton(parts, nodes, branches, volts, old, scale, gmin, limit):
    x = []
    for it in range(limit):
        s = System(nodes, branches); s.old = old; s.scale = scale          # scale < 1: independent sources at a fraction (source stepping)
        for n in nodes: s.conductance(n, "0", gmin)
        for p in parts: p.stamp(s, volts)
        x = _gauss(s.A, s.b); s.x = x
        for p in parts:
            if hasattr(p, "post"): p.post(s, x)                           # parts with an internal state unknown remember this iterate
        new = {n: x[i] for i, n in enumerate(nodes)}; new["0"] = 0.0
        done = (not s.limited) and all(abs(new[n] - volts[n]) <= 1e-9 + 1e-8 * abs(new[n]) for n in nodes)
        volts.update(new)
        if done: return (x, s), True
    return (x, s), False


def solve(parts, guess=None, want_bcur=False):
    """Returns (node voltages {name: V} including '0', {part id: (V across, I a->b, P absorbed)}).
    guess: node voltages of a nearby solution (a sweep passes the previous point) to start Newton from."""
    nodes = sorted({str(n).strip() for p in parts for n in p.nodes if not is_ground(n)})
    def canon(n): return "0" if is_ground(n) else str(n).strip()
    for p in parts:
        p.nodes = [canon(n) for n in p.nodes]
        if hasattr(p, "ctrl_nodes") and p.control_nodes(): p.extra["control"] = [canon(n) for n in p.control_nodes()]
    _wire_controls(parts)
    branches = [p for p in parts if p.branch]
    start = {n: (guess or {}).get(n, 0.0) for n in nodes}; start["0"] = 0.0
    nonlinear = any(p.nonlinear for p in parts)
    ok, volts, x = True, dict(start), ([], None)
    if not nonlinear:
        try: x, ok = _newton(parts, nodes, branches, volts, {}, 1.0, 0.0, 1)         # exact: no leak to ground at all
        except SolveError: volts = dict(start); x, ok = _newton(parts, nodes, branches, volts, {}, 1.0, 1e-12, 1)   # a tiny leak only if the matrix is singular (floating nets)
        ok = True
    else:
        x, ok = _newton(parts, nodes, branches, volts, {}, 1.0, 1e-12, 300)
        if not ok:                                                    # fallback 1: source stepping, 0 -> 100 %
            volts = {n: 0.0 for n in nodes}; volts["0"] = 0.0; old = {}
            for k in range(1, 21):
                x, ok = _newton(parts, nodes, branches, volts, old, k / 20, 1e-12, 200)
                if not ok: break
        if not ok:                                                    # fallback 2: gmin stepping, a big leak to ground that shrinks to 1e-12
            volts = {n: 0.0 for n in nodes}; volts["0"] = 0.0; old = {}
            for g in (1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-8, 1e-10, 1e-12):
                x, ok = _newton(parts, nodes, branches, volts, old, 1.0, g, 200)
                if not ok: break
        if not ok: raise SolveError("The diode equations did not settle (no stable operating point found). Check the polarity of diodes and add a series resistor.")
    bcur = branch_currents(x[1], branches, x[0]) if x[1] is not None else {}
    for p in parts:
        if p.nterm == 2 and p.vmax is not None and volts[p.nodes[0]] - volts[p.nodes[1]] > p.vmax:
            raise SolveError(f"{p.id} has {volts[p.nodes[0]] - volts[p.nodes[1]]:.2f} V across it in the forward direction, which would destroy a real {p.type_name.lower()} "
                             "(its current is only limited by the circuit). Put a resistor in series with it.")
    res = {}
    for p in parts: res[p.id] = p.result(volts, bcur)
    return (volts, res, bcur) if want_bcur else (volts, res)
