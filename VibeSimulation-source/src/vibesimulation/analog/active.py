"""Parts with three or four terminals: bipolar transistors (NPN, PNP), MOSFETs (N, P; enhancement or depletion by the sign of vto), JFETs (N, P),
an op-amp (with supply rails and a gain-bandwidth pole) and a transformer (two coupled windings).

Every nonlinear transistor is described the same way: a few 'control voltages' (vbe and vbc, or vgs and vds), the currents flowing INTO the terminals
and their derivatives. The DC solver (Newton), the AC analysis (small-signal) and the transient analysis all use that one description."""
import math

from ..core.render import ACCENT, FILL, LABEL, MUTED, OUTLINE
from .components import AnalogPart, VT
from .solver import terminal_stamp
from .units import fmt_si, parse_value

GMIN = 1e-12


def _exp(x): return math.exp(min(x, 80.0))


class Multi(AnalogPart):
    """Base of the transistors. Subclasses give: rows (control voltages), ev(vc), lim, caps."""
    nterm = 3
    nonlinear = True
    short = ("1", "2", "3")
    rows = ()                      # control voltage c = v[i] - v[j]  ->  ((i, j), ...)
    leaks = ()                     # terminal pairs that get a tiny conductance (like SPICE's gmin) so that an off device does not leave a net floating
    unit, default = "", None

    def pv(self, k):
        try: return parse_value(self.extra[k])
        except (ValueError, KeyError): return None

    def vcs(self, v):
        return [v[i] - v[j] for i, j in self.rows]

    def jac(self, Jc):
        """Terminal Jacobian J[t][k] = d(current into terminal t) / d(voltage of terminal k)."""
        J = [[0.0] * self.nterm for _ in range(self.nterm)]
        for t in range(self.nterm):
            for c, (i, j) in enumerate(self.rows): J[t][i] += Jc[t][c]; J[t][j] -= Jc[t][c]
        for a, b in self.leaks:
            J[a][a] += GMIN; J[b][b] += GMIN; J[a][b] -= GMIN; J[b][a] -= GMIN
        return J

    def lim(self, s, vc): return vc

    def currents_at(self, volts):
        v = [volts.get(n, 0.0) for n in self.nodes]; I, Jc = self.ev(self.vcs(v))
        for a, b in self.leaks: g = GMIN * (v[a] - v[b]); I[a] += g; I[b] -= g
        return I, Jc, v

    def stamp(self, s, volts):
        v = [volts.get(n, 0.0) for n in self.nodes]; vc = self.lim(s, self.vcs(v)); I, Jc = self.ev(vc); J = self.jac(Jc)
        # leaving current of terminal t, linearised at the (limited) control voltages: I_t + sum_c Jc[t][c] (vc_new - vc) -> constant part below
        const = [I[t] - sum(Jc[t][c] * vc[c] for c in range(len(vc))) for t in range(self.nterm)]
        terminal_stamp(s, self.nodes, const, J, [0.0] * self.nterm)

    # ---- results
    def terminal_currents(self, volts, bcur=None):
        I, _, _ = self.currents_at(volts); return I

    def res_current(self, volts, bcur): return self.terminal_currents(volts, bcur)[0]

    def result(self, volts, bcur):
        I = self.terminal_currents(volts, bcur); v = [volts[n] for n in self.nodes]
        return (v[0] - v[-1], I[0], sum(a * b for a, b in zip(v, I)))

    # ---- AC
    def ac_stamp(self, s, w, volts):
        I, Jc, v = self.currents_at(volts); J = self.jac(Jc)
        for t, nt in enumerate(self.nodes):
            it = s._i(nt)
            if it is None: continue
            for k, nk in enumerate(self.nodes):
                ik = s._i(nk)
                if ik is not None and J[t][k] != 0.0: s.A[it][ik] += J[t][k]
        for ti, tj, c in self.caps():
            if c: s.conductance(self.nodes[ti], self.nodes[tj], 1j * w * c)

    def ac_currents(self, V, bcur, w, volts):
        I, Jc, v = self.currents_at(volts); J = self.jac(Jc); out = [sum(J[t][k] * V[self.nodes[k]] for k in range(self.nterm)) for t in range(self.nterm)]
        for ti, tj, c in self.caps():
            ic = 1j * w * c * (V[self.nodes[ti]] - V[self.nodes[tj]]); out[ti] += ic; out[tj] -= ic
        return out

    def caps(self):
        return [(i, j, self.pv(k)) for (i, j), k in zip(self.CAPS, self.CAPKEYS) if self.pv(k)]

    CAPS, CAPKEYS = (), ()

    def dc_links(self): return self.LINKS
    LINKS = ()


# ---------------------------------------------------------------- bipolar transistors
class BJT(Multi):
    letter, pol = "Q", 1
    terminals = ("collector", "base", "emitter"); short = ("c", "b", "e")
    extras = {"is": "1e-14", "bf": "100", "br": "1", "vaf": "100", "cbe": "0", "cbc": "0"}
    PINS = ((14, -40), (-40, 0), (14, 40))     # where the terminals sit relative to the symbol's centre
    rows = ((1, 2), (1, 0))                    # vbe, vbc
    leaks = ((1, 2), (1, 0))
    CAPS, CAPKEYS = ((1, 2), (1, 0)), ("cbe", "cbc")
    LINKS = ((0, 1), (1, 2))
    idp = "Q"

    def check(self):
        errs = AnalogPart.check(self)
        for k, lo in (("is", 0), ("bf", 0), ("br", 0), ("vaf", 0), ("cbe", -1), ("cbc", -1)):
            v = self.pv(k)
            if v is None or (lo >= 0 and v <= lo) or (lo < 0 and v < 0): errs.append(f"{self.id}: '{k}' must be a number" + (" greater than 0" if lo >= 0 else " (0 or more)"))
        return errs

    def dc_links(self): return [(self.nodes[a], self.nodes[b]) for a, b in self.LINKS]

    def lim(self, s, vc):
        p = self.pol; IS = self.pv("is")
        return [p * s.limit(self, "be", p * vc[0], VT, IS), p * s.limit(self, "bc", p * vc[1], VT, IS)]

    def ev(self, vc):
        p = self.pol; vbe, vbc = p * vc[0], p * vc[1]; IS, BF, BR, VAF = self.pv("is"), self.pv("bf"), self.pv("br"), self.pv("vaf")
        ef, er = _exp(vbe / VT), _exp(vbc / VT); If, Ir = IS * (ef - 1), IS * (er - 1); gf, gr = IS * ef / VT, IS * er / VT
        E, dE = 1 - vbc / VAF, -1 / VAF
        if E < 0.05: E, dE = 0.05, 0.0
        ict = (If - Ir) * E
        ic = ict - Ir / BR; ib = If / BF + Ir / BR
        dic = [gf * E, -gr * E + (If - Ir) * dE - gr / BR]; dib = [gf / BF, gr / BR]
        I = [p * ic, p * ib, -p * (ic + ib)]
        Jc = [dic, dib, [-(dic[0] + dib[0]), -(dic[1] + dib[1])]]
        return I, Jc

    def region(self, v):
        vbe, vbc = self.pol * (v[1] - v[2]), self.pol * (v[1] - v[0]); on_e, on_c = vbe > 0.45, vbc > 0.45
        return "saturation" if on_e and on_c else "forward active" if on_e else "reverse active" if on_c else "cut-off"

    def info(self, volts, bcur=None):
        I, Jc, v = self.currents_at(volts); ic, ib = self.pol * I[0], self.pol * I[1]
        out = [("region", self.region(v)), ("Vbe", fmt_si(v[1] - v[2], "V", 4)), ("Vce", fmt_si(v[0] - v[2], "V", 4)), ("Ic", fmt_si(I[0], "A", 4)), ("Ib", fmt_si(I[1], "A", 4))]
        if abs(ib) > 1e-15: out.append(("Ic/Ib", f"{ic / ib:.4g}"))
        out.append(("gm", fmt_si(abs(Jc[0][0]), "S", 4)))
        return out

    def caption(self, digits=4): return f"β={self.pv('bf'):g}"

    def spice_lines(self, node):
        nm = f"{'QN' if self.pol > 0 else 'QP'}_{self.id}"; n = [node(x) for x in self.nodes]
        return [f"{self.spice_name()} {n[0]} {n[1]} {n[2]} {nm}",
                f".model {nm} {'NPN' if self.pol > 0 else 'PNP'}(IS={self.pv('is'):g} BF={self.pv('bf'):g} BR={self.pv('br'):g} VAF={self.pv('vaf'):g}" +
                (f" CJE={self.pv('cbe'):g} MJE=0" if self.pv("cbe") else "") + (f" CJC={self.pv('cbc'):g} MJC=0" if self.pv("cbc") else "") + ")"]

    def draw(self, r, cx, cy, tags):
        # drawn upright in the part's own frame: collector top (cx, cy-40), emitter bottom (cx, cy+40), base left (cx-40, cy)
        r.line([(cx - 40, cy), (cx - 8, cy)], 2, OUTLINE, tags); r.line([(cx - 8, cy - 20), (cx - 8, cy + 20)], 3, OUTLINE, tags)
        r.line([(cx - 8, cy - 9), (cx + 14, cy - 28), (cx + 14, cy - 40)], 2, OUTLINE, tags); r.line([(cx - 8, cy + 9), (cx + 14, cy + 28), (cx + 14, cy + 40)], 2, OUTLINE, tags)
        if self.pol > 0: r.polygon([(cx + 14, cy + 28), (cx + 4, cy + 27), (cx + 11, cy + 19)], LABEL, LABEL, 1, tags)        # arrow out of the emitter
        else: r.polygon([(cx - 8, cy + 9), (cx + 2, cy + 10), (cx - 5, cy + 18)], LABEL, LABEL, 1, tags)                   # arrow into the emitter


class NPN(BJT):
    type_name, aliases, pol = "NPN", ("BJT", "NPNBJT"), 1
    summary = "NPN bipolar transistor. nodes = [collector, base, emitter]. Parameters: is (saturation current), bf / br (forward / reverse beta), vaf (Early voltage), cbe / cbc (junction capacitances, for AC and transient)."


class PNP(BJT):
    type_name, aliases, pol = "PNP", ("PNPBJT",), -1
    summary = "PNP bipolar transistor. nodes = [collector, base, emitter]. Same parameters as NPN."


# ---------------------------------------------------------------- field-effect transistors
class FET(Multi):
    """Shared by MOSFETs and JFETs: terminals drain, gate, source; control voltages vgs and vds."""
    terminals = ("drain", "gate", "source"); short = ("d", "g", "s")
    PINS = ((14, -40), (-40, 0), (14, 40))
    rows = ((1, 2), (0, 2))
    CAPS, CAPKEYS = ((1, 2), (1, 0)), ("cgs", "cgd")
    pol = 1
    idp = "M"

    def lim(self, s, vc):
        out = []
        for k, (tag, step) in enumerate((("vgs", 3.0), ("vds", 6.0))):
            key = (id(self), tag); old = s.old.get(key)
            if old is not None and abs(vc[k] - old) > step:
                s.limited = True; vc[k] = old + step * (1 if vc[k] > old else -1)
            s.old[key] = vc[k]; out.append(vc[k])
        return out

    def chan(self, vgs, vds, vto, beta, lam):
        """Channel current (NPN frame, vds >= 0) with d/dvgs and d/dvds, region."""
        raise NotImplementedError

    def sym(self, vgs, vds, par):
        """Channel current for either sign of vds (source and drain swap), in the N frame."""
        if vds >= 0: return self.chan(vgs, vds, *par)
        i, gm, gds, reg = self.chan(vgs - vds, -vds, *par)
        return -i, -gm, gm + gds, reg

    def check(self):
        errs = AnalogPart.check(self)
        for k in self.CHECKPOS:
            v = self.pv(k)
            if v is None or v <= 0: errs.append(f"{self.id}: '{k}' must be a number greater than 0")
        for k in ("vto",) + tuple(self.CAPKEYS):
            v = self.pv(k)
            if v is None: errs.append(f"{self.id}: '{k}' must be a number")
            elif k in self.CAPKEYS and v < 0: errs.append(f"{self.id}: '{k}' must be 0 or more")
        v = self.pv("lambda")
        if v is None or v < 0: errs.append(f"{self.id}: 'lambda' must be 0 or more")
        return errs

    def par(self): return (self.pol * self.pv("vto"), self.pv(self.BETA), self.pv("lambda"))

    def region_of(self, v):
        p = self.pol; _, _, _, reg = self.sym(p * (v[1] - v[2]), p * (v[0] - v[2]), self.par()); return reg

    def info(self, volts, bcur=None):
        I, Jc, v = self.currents_at(volts); p = self.pol; _, gm, gds, reg = self.sym(p * (v[1] - v[2]), p * (v[0] - v[2]), self.par())
        return [("region", reg), ("Vgs", fmt_si(v[1] - v[2], "V", 4)), ("Vds", fmt_si(v[0] - v[2], "V", 4)), ("Id", fmt_si(I[0], "A", 4)), ("gm", fmt_si(abs(gm), "S", 4)), ("gds", fmt_si(abs(gds), "S", 4))]

    def draw_body(self, r, cx, cy, tags, depletion=False):
        pass


class MOS(FET):
    letter = "M"
    extras = {"vto": "2", "kp": "5m", "lambda": "0.02", "cgs": "0", "cgd": "0"}
    BETA, CHECKPOS = "kp", ("kp",)
    leaks = ((0, 2),)
    LINKS = ((0, 2),)

    def chan(self, vgs, vds, vto, kp, lam):
        vov = vgs - vto
        if vov <= 0: return 0.0, 0.0, 0.0, "cut-off"
        cl = 1 + lam * vds
        if vds < vov: return kp * (vov * vds - vds * vds / 2) * cl, kp * vds * cl, kp * (vov - vds) * cl + kp * (vov * vds - vds * vds / 2) * lam, "triode (linear)"
        return kp / 2 * vov * vov * cl, kp * vov * cl, kp / 2 * vov * vov * lam, "saturation"

    def ev(self, vc):
        p = self.pol; i, gm, gds, _ = self.sym(p * vc[0], p * vc[1], self.par())
        I = [p * i, 0.0, -p * i]; return I, [[gm, gds], [0.0, 0.0], [-gm, -gds]]

    def caption(self, digits=4): return f"Vto={self.pv('vto'):g} V"

    def spice_lines(self, node):
        nm = f"{'MN' if self.pol > 0 else 'MP'}_{self.id}"; n = [node(x) for x in self.nodes]
        return [f"{self.spice_name()} {n[0]} {n[1]} {n[2]} {n[2]} {nm} W=1 L=1",           # W = L = 1 so KP and the overlap capacitances (CGSO, CGDO are per metre of W) are used as they are
                f".model {nm} {'NMOS' if self.pol > 0 else 'PMOS'}(LEVEL=1 VTO={self.pv('vto'):g} KP={self.pv('kp'):g} LAMBDA={self.pv('lambda'):g}" +
                (f" CGSO={self.pv('cgs'):g}" if self.pv("cgs") else "") + (f" CGDO={self.pv('cgd'):g}" if self.pv("cgd") else "") + ")"]

    def draw(self, r, cx, cy, tags):
        # gate left (cx-40, cy); drain top (cx+14, cy-40); source bottom (cx+14, cy+40)
        r.line([(cx - 40, cy), (cx - 14, cy)], 2, OUTLINE, tags); r.line([(cx - 14, cy - 18), (cx - 14, cy + 18)], 3, OUTLINE, tags)
        dep = self.pv("vto") * self.pol < 0
        for y0, y1 in ((-18, -10), (-4, 4), (10, 18)):
            r.line([(cx - 8, cy + y0 if y0 > -5 else cy + y0), (cx - 8, cy + y1)], 3 if not (dep and y0 == -4) else 3, OUTLINE, tags)
        if dep: r.line([(cx - 8, cy - 18), (cx - 8, cy + 18)], 3, OUTLINE, tags)
        r.line([(cx - 8, cy - 14), (cx + 14, cy - 14), (cx + 14, cy - 40)], 2, OUTLINE, tags); r.line([(cx - 8, cy + 14), (cx + 14, cy + 14), (cx + 14, cy + 40)], 2, OUTLINE, tags)
        r.line([(cx - 8, cy), (cx + 14, cy)], 2, OUTLINE, tags)
        if self.pol > 0: r.polygon([(cx - 8, cy), (cx + 2, cy - 5), (cx + 2, cy + 5)], LABEL, LABEL, 1, tags)
        else: r.polygon([(cx + 14, cy), (cx + 4, cy - 5), (cx + 4, cy + 5)], LABEL, LABEL, 1, tags)


class NMOS(MOS):
    type_name, aliases, pol = "NMOS", ("NMOSFET", "MOSFET"), 1
    summary = "N-channel MOSFET (level 1). nodes = [drain, gate, source] (body tied to the source). vto = threshold (negative: depletion type), kp = transconductance parameter in A/V² (includes W/L), lambda = channel-length modulation, cgs / cgd = capacitances."


class PMOS(MOS):
    type_name, aliases, pol = "PMOS", ("PMOSFET",), -1
    extras = {"vto": "-2", "kp": "5m", "lambda": "0.02", "cgs": "0", "cgd": "0"}
    summary = "P-channel MOSFET (level 1). nodes = [drain, gate, source]. vto is negative for an enhancement device (SPICE convention)."


class IGBT(MOS):
    """N-channel IGBT, compact behavioural model: the MOS channel (vto = gate threshold, kp) in series with the fixed forward drop vf of the bipolar part.
    It conducts only forward (no body diode)."""
    type_name, aliases, pol = "IGBT", ("NIGBT",), 1
    extras = {"vto": "5", "kp": "2", "lambda": "0.01", "vf": "0.7", "cgs": "0", "cgd": "0"}
    summary = ("N-channel IGBT (compact model). nodes = [collector, gate, emitter]. vto = gate threshold, kp = channel gain in A/V², vf = forward drop of the PN junction (~0.7 V), "
               "lambda = output conductance. It blocks reverse voltage. No turn-off tail or latch-up.")
    terminals = ("collector", "gate", "emitter"); short = ("c", "g", "e")
    idp = "IGBT"

    def check(self):
        errs = MOS.check(self)
        if self.pv("vf") is None or self.pv("vf") < 0: errs.append(f"{self.id}: 'vf' must be 0 or more")
        return errs

    def ev(self, vc):
        vgs, vds = vc; vf = self.pv("vf"); eps = 0.05; x = vds - vf; r = math.sqrt(x * x + eps * eps); veff, dv = 0.5 * (x + r), 0.5 * (1 + x / r)
        i, gm, gds, _ = self.chan(vgs, veff, self.pv("vto"), self.pv("kp"), self.pv("lambda"))
        gds *= dv; return [i, 0.0, -i], [[gm, gds], [0.0, 0.0], [-gm, -gds]]

    def info(self, volts, bcur=None):
        I, Jc, v = self.currents_at(volts); vgs, vds = v[1] - v[2], v[0] - v[2]; vf = self.pv("vf"); veff = max(vds - vf, 0.0)
        reg = self.chan(vgs, veff, self.pv("vto"), self.pv("kp"), self.pv("lambda"))[3] if vgs > self.pv("vto") and vds > vf else "off"
        return [("region", reg), ("Vge", fmt_si(vgs, "V", 4)), ("Vce", fmt_si(vds, "V", 4)), ("Ic", fmt_si(I[0], "A", 4)), ("gm", fmt_si(abs(Jc[0][0]), "S", 4))]

    def spice_lines(self, node):
        n = [node(x) for x in self.nodes]
        return [f"* {self.id}: IGBT as an N-channel MOSFET plus a diode drop (compact model)",
                f"M{self.id} {n[0]} {n[1]} {n[2]} {n[2]} MI_{self.id}", f".model MI_{self.id} NMOS(LEVEL=1 VTO={self.pv('vto'):g} KP={self.pv('kp'):g} LAMBDA={self.pv('lambda'):g})"]

    def draw(self, r, cx, cy, tags):
        MOS.draw(self, r, cx, cy, tags)
        r.polygon([(cx + 14, cy - 28), (cx + 9, cy - 20), (cx + 19, cy - 20)], LABEL, LABEL, 1, tags)         # the PN junction's arrow on the collector lead


class JFET(FET):
    letter = "J"
    extras = {"vto": "-2", "beta": "1m", "lambda": "0.02", "is": "1e-14", "cgs": "0", "cgd": "0"}
    BETA, CHECKPOS = "beta", ("beta", "is")
    leaks = ((0, 2),)
    idp = "J"
    LINKS = ((0, 2),)

    def chan(self, vgs, vds, vto, beta, lam):
        vov = vgs - vto
        if vov <= 0: return 0.0, 0.0, 0.0, "cut-off (pinched off)"
        cl = 1 + lam * vds
        if vds < vov: return beta * vds * (2 * vov - vds) * cl, 2 * beta * vds * cl, beta * (2 * vov - 2 * vds) * cl + beta * vds * (2 * vov - vds) * lam, "triode (linear)"
        return beta * vov * vov * cl, 2 * beta * vov * cl, beta * vov * vov * lam, "saturation"

    def lim(self, s, vc):
        vc = FET.lim(self, s, vc); IS = self.pv("is")
        vgs = self.pol * vc[0]; vgd = self.pol * (vc[0] - vc[1])
        vgs = s.limit(self, "gs", vgs, VT, IS); vgd = s.limit(self, "gd", vgd, VT, IS)
        return [self.pol * vgs, self.pol * (vgs - vgd)]

    def ev(self, vc):
        p = self.pol; vgs, vds = p * vc[0], p * vc[1]; IS = self.pv("is"); i, gm, gds, _ = self.sym(vgs, vds, self.par())
        e1, e2 = _exp(vgs / VT), _exp((vgs - vds) / VT); ig1, ig2 = IS * (e1 - 1), IS * (e2 - 1); g1, g2 = IS * e1 / VT, IS * e2 / VT
        I = [p * (i - ig2), p * (ig1 + ig2), p * (-i - ig1)]
        Jc = [[gm - g2, gds + g2], [g1 + g2, -g2], [-gm - g1, -gds]]
        return I, Jc

    def caption(self, digits=4): return f"Vto={self.pv('vto'):g} V"

    def spice_lines(self, node):
        nm = f"{'JN' if self.pol > 0 else 'JP'}_{self.id}"; n = [node(x) for x in self.nodes]
        return [f"{self.spice_name()} {n[0]} {n[1]} {n[2]} {nm}",
                f".model {nm} {'NJF' if self.pol > 0 else 'PJF'}(VTO={self.pv('vto'):g} BETA={self.pv('beta'):g} LAMBDA={self.pv('lambda'):g} IS={self.pv('is'):g}" +
                (f" CGS={self.pv('cgs'):g}" if self.pv("cgs") else "") + (f" CGD={self.pv('cgd'):g}" if self.pv("cgd") else "") + ")"]

    def draw(self, r, cx, cy, tags):
        r.line([(cx - 40, cy), (cx - 8, cy)], 2, OUTLINE, tags)                          # gate lead
        r.line([(cx - 8 + 8, cy - 26), (cx - 8 + 8, cy + 26)], 3, OUTLINE, tags)        # channel
        r.line([(cx, cy - 22), (cx + 14, cy - 22), (cx + 14, cy - 40)], 2, OUTLINE, tags); r.line([(cx, cy + 22), (cx + 14, cy + 22), (cx + 14, cy + 40)], 2, OUTLINE, tags)
        if self.pol > 0: r.polygon([(cx - 8, cy), (cx - 8 + 10, cy - 5), (cx - 8 + 10, cy + 5)], LABEL, LABEL, 1, tags)
        else: r.polygon([(cx + 2, cy), (cx - 8, cy - 5), (cx - 8, cy + 5)], LABEL, LABEL, 1, tags)


class NJFET(JFET):
    type_name, aliases, pol = "NJFET", ("NJF", "JFET"), 1
    summary = "N-channel JFET. nodes = [drain, gate, source]. vto = pinch-off voltage (negative), beta in A/V², lambda, is = gate junction saturation current."


class PJFET(JFET):
    type_name, aliases, pol = "PJFET", ("PJF",), -1
    extras = {"vto": "2", "beta": "1m", "lambda": "0.02", "is": "1e-14", "cgs": "0", "cgd": "0"}
    summary = "P-channel JFET. nodes = [drain, gate, source]. vto = pinch-off voltage (positive, SPICE convention)."


# ---------------------------------------------------------------- op-amp
class OpAmp(AnalogPart):
    """Op-amp with finite gain, output rails (soft limiting) and a single pole set by the gain-bandwidth product. Inputs draw no current;
    the output is an ideal voltage source behind the limiter. nodes = [non-inverting input, inverting input, output]."""
    type_name, aliases, letter, unit, default = "OpAmp", ("Op-Amp", "OPAMP"), "U", "", None
    terminals = ("in+", "in-", "out"); short = ("p", "n", "o"); nterm = 3
    extras = {"gain": "1e5", "vpos": "15", "vneg": "-15", "gbw": "1meg"}
    PINS = ((-40, -20), (-40, 20), (50, 0))
    branch, nbranch, nonlinear, idp = True, 2, True, "U"
    summary = ("Op-amp. nodes = [in+, in-, out]. gain = open-loop DC gain (default 1e5), vpos / vneg = output limits (default ±15 V), "
               "gbw = gain-bandwidth product in Hz (0 = infinite bandwidth).")

    def pv(self, k):
        try: return parse_value(self.extra[k])
        except (ValueError, KeyError): return None

    def check(self):
        errs = AnalogPart.check(self)
        for k in ("gain", "vpos", "vneg", "gbw"):
            if self.pv(k) is None: errs.append(f"{self.id}: '{k}' must be a number")
        if not errs:
            if self.pv("gain") <= 0: errs.append(f"{self.id}: gain must be greater than 0")
            if self.pv("vneg") >= self.pv("vpos"): errs.append(f"{self.id}: vneg must be below vpos")
            if self.pv("gbw") < 0: errs.append(f"{self.id}: gbw must be 0 or more")
        return errs

    def dc_links(self): return [(self.nodes[2], "0")]      # the output is a ground-referenced source
    def conducts(self): return False

    def soft(self, y):
        hi, lo = self.pv("vpos"), self.pv("vneg"); d = 0.05 * (hi - lo); h, l = hi - d, lo + d
        if y > h: t = math.tanh((y - h) / d); return h + d * t, 1 - t * t
        if y < l: t = math.tanh((y - l) / d); return l + d * t, 1 - t * t
        return y, 1.0

    def tau(self):
        g = self.pv("gbw"); return self.pv("gain") / (2 * math.pi * g) if g and g > 0 else 0.0

    def _idx(self, s):
        return s.bidx[id(self)], s._i(self.nodes[2]), s._i(self.nodes[0]), s._i(self.nodes[1])

    def post(self, s, x):
        s.old[(self.id, "x")] = x[s.bidx[id(self)] + 1]

    def stamp(self, s, volts, tau_dt=0.0, xprev=0.0):
        """Two unknowns: k = output current, k+1 = x, the internal node after the gain and pole but before the output limiter.
        (1 + tau/dt) x = A (v+ - v-) + tau/dt xprev      and      Vout = limit(x)"""
        k, io, ip, im = self._idx(s); A = self.pv("gain"); g = tau_dt; k2 = k + 1
        x0 = s.old.get((self.id, "x"), A * (volts.get(self.nodes[0], 0.0) - volts.get(self.nodes[1], 0.0)))
        out0, d = self.soft(x0)
        if io is not None: s.A[io][k] += 1; s.A[k][io] += 1
        s.A[k][k2] -= d; s.b[k] = out0 - d * x0
        s.A[k2][k2] += 1 + g
        if ip is not None: s.A[k2][ip] -= A
        if im is not None: s.A[k2][im] += A
        s.b[k2] = g * xprev

    def tr_stamp(self, s, volts, dt, be, mem):
        self.stamp(s, volts, self.tau() / dt, mem[(self.id, "X")])

    def ac_stamp(self, s, w, volts):
        k, io, ip, im = self._idx(s); A = self.pv("gain"); k2 = k + 1; vd = volts[self.nodes[0]] - volts[self.nodes[1]]; _, d = self.soft(A * vd)
        if io is not None: s.A[io][k] += 1; s.A[k][io] += 1
        s.A[k][k2] -= d; s.A[k2][k2] += 1 + 1j * w * self.tau()
        if ip is not None: s.A[k2][ip] -= A
        if im is not None: s.A[k2][im] += A

    def terminal_currents(self, volts, bcur): return [0.0, 0.0, bcur.get(self.id, 0.0)]
    def ac_currents(self, V, bcur, w, volts): return [0j, 0j, bcur.get(self.id, 0j)]
    def res_current(self, volts, bcur): return bcur.get(self.id, 0.0)

    def result(self, volts, bcur):
        i = bcur.get(self.id, 0.0); return (volts[self.nodes[0]] - volts[self.nodes[1]], i, volts[self.nodes[2]] * i)

    def info(self, volts, bcur=None):
        vd = volts[self.nodes[0]] - volts[self.nodes[1]]; out = volts[self.nodes[2]]; hi, lo = self.pv("vpos"), self.pv("vneg")
        state = "saturated at the positive limit" if out > hi - 0.06 * (hi - lo) else "saturated at the negative limit" if out < lo + 0.06 * (hi - lo) else "linear"
        return [("state", state), ("Vd", fmt_si(vd, "V", 4)), ("Vout", fmt_si(out, "V", 4))]

    def caption(self, digits=4): return ""

    def spice_lines(self, node):
        n = [node(x) for x in self.nodes]
        return [f"E{self.id} {n[2]} 0 {n[0]} {n[1]} {self.pv('gain'):g}   * op-amp: gain only (rails vpos={self.pv('vpos'):g} vneg={self.pv('vneg'):g}, gbw={self.pv('gbw'):g} are not exported)"]

    def draw(self, r, cx, cy, tags):
        # in+ top-left (cx-40, cy-20), in- bottom-left (cx-40, cy+20), output right (cx+50, cy)
        r.polygon([(cx - 30, cy - 34), (cx - 30, cy + 34), (cx + 36, cy)], FILL, OUTLINE, 2, tags)
        r.line([(cx - 40, cy - 20), (cx - 30, cy - 20)], 2, OUTLINE, tags); r.line([(cx - 40, cy + 20), (cx - 30, cy + 20)], 2, OUTLINE, tags); r.line([(cx + 36, cy), (cx + 50, cy)], 2, OUTLINE, tags)
        r.text(cx - 23, cy - 20, "+", 12, ACCENT, True, "c", tags); r.text(cx - 23, cy + 20, "−", 12, LABEL, True, "c", tags)


# ---------------------------------------------------------------- transformer
class Transformer(AnalogPart):
    """Two windings coupled by k. value = primary inductance L1; secondary L2 = L1 · ratio²; mutual M = k · sqrt(L1 L2) = k · L1 · ratio.
    At DC both windings are (almost) short circuits (1 µΩ), so a secondary needs its own ground reference."""
    type_name, aliases, letter, unit, default = "Transformer", ("Trafo", "TRANSFORMER"), "T", "H", "100m"
    terminals = ("p+", "p-", "s+", "s-"); short = ("p+", "p-", "s+", "s-"); nterm = 4
    extras = {"ratio": "1", "k": "0.99"}
    PINS = ((-40, -30), (-40, 30), (40, -30), (40, 30))
    branch, nbranch, idp = True, 2, "T"
    summary = "Transformer: nodes = [primary +, primary -, secondary +, secondary -]. value = primary inductance, ratio = turns ratio secondary/primary, k = coupling (0 < k < 1)."

    def pv(self, k):
        try: return parse_value(self.extra[k])
        except (ValueError, KeyError): return None

    def check(self):
        errs = AnalogPart.check(self)
        r, k = self.pv("ratio"), self.pv("k")
        if r is None or r <= 0: errs.append(f"{self.id}: ratio must be a number greater than 0")
        if k is None or not 0 < k < 1: errs.append(f"{self.id}: k must be between 0 and 1 (e.g. 0.99)")
        return errs

    def L(self):
        l1, r, k = self.number(), self.pv("ratio"), self.pv("k"); return l1, l1 * r * r, k * l1 * r

    def dc_links(self): return [(self.nodes[0], self.nodes[1]), (self.nodes[2], self.nodes[3])]
    def conducts(self): return True

    def _wind(self, s, kb, a, b):
        ia, ib = s._i(a), s._i(b)
        if ia is not None: s.A[ia][kb] += 1; s.A[kb][ia] += 1
        if ib is not None: s.A[ib][kb] -= 1; s.A[kb][ib] -= 1

    def stamp(self, s, volts):
        k = s.bidx[id(self)]; self._wind(s, k, self.nodes[0], self.nodes[1]); self._wind(s, k + 1, self.nodes[2], self.nodes[3])
        s.A[k][k] -= 1e-6; s.A[k + 1][k + 1] -= 1e-6              # a micro-ohm of winding resistance: a source straight across a winding (0 V at DC) stays solvable

    def ac_stamp(self, s, w, volts):
        k = s.bidx[id(self)]; self.stamp(s, volts); l1, l2, m = self.L(); jw = 1j * w
        s.A[k][k] -= jw * l1; s.A[k][k + 1] -= jw * m; s.A[k + 1][k] -= jw * m; s.A[k + 1][k + 1] -= jw * l2

    def tr_stamp(self, s, volts, dt, be, mem):
        k = s.bidx[id(self)]; self.stamp(s, volts); l1, l2, m = self.L(); c = (1 if be else 2) / dt
        (v1, i1), (v2, i2) = mem[(self.id, 1)], mem[(self.id, 2)]
        s.A[k][k] -= c * l1; s.A[k][k + 1] -= c * m; s.A[k + 1][k] -= c * m; s.A[k + 1][k + 1] -= c * l2
        s.b[k] = -(c * (l1 * i1 + m * i2)) - (0 if be else v1); s.b[k + 1] = -(c * (m * i1 + l2 * i2)) - (0 if be else v2)

    def terminal_currents(self, volts, bcur): i1, i2 = bcur.get(self.id, 0.0), bcur.get(self.id + "#2", 0.0); return [i1, -i1, i2, -i2]
    def ac_currents(self, V, bcur, w, volts): return self.terminal_currents(V, bcur)
    def res_current(self, volts, bcur): return bcur.get(self.id, 0.0)

    def result(self, volts, bcur):
        i1, i2 = bcur.get(self.id, 0.0), bcur.get(self.id + "#2", 0.0); v1 = volts[self.nodes[0]] - volts[self.nodes[1]]; v2 = volts[self.nodes[2]] - volts[self.nodes[3]]
        return (v1, i1, v1 * i1 + v2 * i2)

    def info(self, volts, bcur=None):
        l1, l2, m = self.L(); return [("L1 / L2", f"{fmt_si(l1, 'H', 4)} / {fmt_si(l2, 'H', 4)}"), ("M", fmt_si(m, "H", 4)), ("Is", fmt_si((bcur or {}).get(self.id + '#2', 0.0), "A", 4))]

    def caption(self, digits=4): return f"{fmt_si(self.number(), 'H', digits)}  1:{self.pv('ratio'):g}"

    def spice_lines(self, node):
        n = [node(x) for x in self.nodes]; l1, l2, m = self.L()
        return [f"L{self.id}p {n[0]} {n[1]} {l1:g}", f"L{self.id}s {n[2]} {n[3]} {l2:g}", f"K{self.id} L{self.id}p L{self.id}s {self.pv('k'):g}"]

    def draw(self, r, cx, cy, tags):
        # primary left (terminals at cx-40, cy-30 / cx-40, cy+30), secondary right (cx+40, ...)
        for sx, sg in ((-1, -1), (1, 1)):
            x = cx + sx * 12
            r.line([(cx + sx * 40, cy - 30), (x, cy - 30), (x, cy - 24)], 2, OUTLINE, tags); r.line([(cx + sx * 40, cy + 30), (x, cy + 30), (x, cy + 24)], 2, OUTLINE, tags)
            pts = []
            for q in range(3):
                for t in range(0, 11):
                    a = math.pi * t / 10; pts.append((x + sg * 0 + sx * 9 * math.sin(a), cy - 24 + 16 * q + 8 - 8 * math.cos(a)))
            r.line(pts, 2, OUTLINE, tags)
        r.line([(cx - 3, cy - 26), (cx - 3, cy + 26)], 2, OUTLINE, tags); r.line([(cx + 3, cy - 26), (cx + 3, cy + 26)], 2, OUTLINE, tags)


class Potentiometer(Multi):
    """A resistor with a sliding contact: value = total resistance, 'pos' = wiper position from 0 (at A) to 1 (at B). R(A-wiper) = value * pos, R(wiper-B) = value * (1 - pos).
    Linear, so it is stamped as two conductances (kept at least 1 mOhm so a wiper at the end does not make the matrix singular)."""
    type_name, aliases, letter, unit, default = "Potentiometer", ("Pot", "Trimmer", "Rheostat"), "R", "Ω", "10k"
    terminals = ("A", "wiper", "B"); short = ("a", "w", "b"); nterm = 3
    extras = {"pos": "0.5", "tol": "0"}
    PINS = ((-40, 0), (0, -36), (40, 0))
    rows = ((0, 1), (2, 1))                       # v(A) - v(W) and v(B) - v(W)
    nonlinear, idp = False, "RV"
    LINKS = ((0, 1), (1, 2))

    def dc_links(self): return [(self.nodes[a], self.nodes[b]) for a, b in self.LINKS]
    summary = "Potentiometer. nodes = [A, wiper, B]. value = total resistance, pos = wiper position 0..1 (0 = at A, 1 = at B)."

    def check(self):
        errs = AnalogPart.check(self); p = self.pv("pos")
        if p is None or not 0 <= p <= 1: errs.append(f"{self.id}: pos must be a number from 0 to 1")
        return errs

    def rs(self):
        r, p = self.number(), min(1.0, max(0.0, self.pv("pos") or 0.0)); return max(r * p, 1e-3), max(r * (1 - p), 1e-3)

    def ev(self, vc):
        r1, r2 = self.rs(); g1, g2 = 1 / r1, 1 / r2; i1, i2 = g1 * vc[0], g2 * vc[1]
        return [i1, -(i1 + i2), i2], [[g1, 0.0], [-g1, -g2], [0.0, g2]]

    def caption(self, digits=4): return f"{fmt_si(self.number(), 'Ω', digits)}  ·  {self.pv('pos') * 100:g}%"

    def info(self, volts, bcur=None):
        r1, r2 = self.rs(); return [("A–wiper", fmt_si(r1, "Ω", 4)), ("wiper–B", fmt_si(r2, "Ω", 4))]

    def spice_lines(self, node):
        r1, r2 = self.rs(); n = [node(x) for x in self.nodes]
        return [f"R{self.id}a {n[0]} {n[1]} {r1:g}", f"R{self.id}b {n[1]} {n[2]} {r2:g}"]

    def draw(self, r, cx, cy, tags):
        r.line([(cx - 40, cy), (cx - 30, cy)], 2, OUTLINE, tags); r.line([(cx + 30, cy), (cx + 40, cy)], 2, OUTLINE, tags)
        r.line([(cx - 30, cy)] + [(cx - 24 + 8 * i, cy + (-8 if i % 2 == 0 else 8)) for i in range(7)] + [(cx + 30, cy)], 2, OUTLINE, tags)
        r.line([(cx, cy - 36), (cx, cy - 16)], 2, OUTLINE, tags); r.polygon([(cx, cy - 9), (cx - 5, cy - 18), (cx + 5, cy - 18)], LABEL, LABEL, 1, tags)


ACTIVE = (NPN, PNP, NMOS, PMOS, NJFET, PJFET, IGBT, OpAmp, Transformer, Potentiometer)
