"""Transistors, op-amp, transformer: Jacobians vs finite differences, bias points vs independent solutions, N/P symmetry, AC vs transient."""
import sys, os, json, math, random, cmath
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog import components as C, ac, transient as T
bad = 0
def chk(n, c, extra=""):
    global bad; print("ok  " if c else "FAIL", n, extra if not c else ""); bad += (not c)
def mk(comps, analysis=None):
    d = {"components": comps}
    if analysis: d["analysis"] = analysis
    nl, e = parse(json.dumps(d)); assert not e, e; return nl
rng = random.Random(5)
# 1. Jacobians vs finite differences, KCL (currents sum to zero)
for cls, ex in ((C.NPN, {}), (C.PNP, {}), (C.NMOS, {}), (C.PMOS, {}), (C.NJFET, {}), (C.PJFET, {})):
    p = cls("X1", ["a", "b", "c"], None, **ex); worst = 0; kcl = 0
    for _ in range(300):
        if cls in (C.NPN, C.PNP): vc = [rng.uniform(-1, 0.85), rng.uniform(-8, 0.85)]; vc = [cls.pol * x for x in vc]
        elif cls in (C.NJFET, C.PJFET): vgs, vgd = rng.uniform(-6, 0.7), rng.uniform(-6, 0.7); vc = [cls.pol * vgs, cls.pol * (vgs - vgd)]
        else: vc = [rng.uniform(-6, 6), rng.uniform(-6, 6)]
        I, J = p.ev(list(vc)); kcl = max(kcl, abs(sum(I)))
        for c in range(2):
            h = 1e-6; vp = list(vc); vm = list(vc); vp[c] += h; vm[c] -= h
            Ip, _ = p.ev(vp); Im, _ = p.ev(vm)
            for t in range(3):
                num = (Ip[t] - Im[t]) / (2 * h); worst = max(worst, abs(num - J[t][c]) / (1e-7 + abs(J[t][c]) + abs(num)))
    chk(f"{cls.type_name}: analytic Jacobian = numeric (worst rel {worst:.1e}), KCL {kcl:.1e}", worst < 2e-4 and kcl < 1e-9)
# 2. NPN bias vs independent nested bisection
nl = mk([{"id": "Vcc", "type": "VoltageSource", "value": "12", "nodes": ["vcc", "0"]}, {"id": "Rb", "type": "Resistor", "value": "470k", "nodes": ["vcc", "b"]},
         {"id": "Rc", "type": "Resistor", "value": "2.2k", "nodes": ["vcc", "c"]}, {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "0"]}])
assert not nl.validate(), nl.validate()
v, res = nl.solve(); IS, BF, VAF, VT = 1e-14, 100, 100, C.VT
def ic_ib(vbe, vce):
    vbc = vbe - vce; If = IS * (math.exp(vbe / VT) - 1); Ir = IS * (math.exp(vbc / VT) - 1); E = max(1 - vbc / VAF, 0.05)
    return (If - Ir) * E - Ir / 1.0, If / BF + Ir / 1.0
def solve_ref():
    lo, hi = 0.3, 0.9
    for _ in range(100):                                   # outer: vbe so that base resistor equation holds with the vce found by the inner loop
        vbe = (lo + hi) / 2; a, b = 0.0, 12.0
        for _ in range(100):
            vce = (a + b) / 2; ic, _ = ic_ib(vbe, vce)
            if (12 - vce) / 2200 - ic > 0: a = vce            # Rc supplies more than the transistor passes: the collector rises
            else: b = vce
        ic, ib = ic_ib(vbe, vce)
        if (12 - vbe) / 470e3 - ib > 0: lo = vbe
        else: hi = vbe
    return vbe, vce
vbe, vce = solve_ref()
chk(f"NPN common emitter: solver {v['b']:.6f}/{v['c']:.6f} vs reference {vbe:.6f}/{vce:.6f}", abs(v["b"] - vbe) < 1e-6 and abs(v["c"] - vce) < 1e-5)
info = dict(nl.part("Q1").info(v)); chk("NPN region reported", info["region"] == "forward active", info)
# 3. N/P symmetry: mirror every voltage
def mirror(comps_n, swap, flip):
    out = []
    for c in comps_n:
        d = dict(c); d["type"] = swap.get(d["type"], d["type"])
        if d["type"] == "VoltageSource": d["value"] = str(-float(d["value"]))
        out.append(d)
    return out
cases = {
 "NPN/PNP": ([{"id": "Vcc", "type": "VoltageSource", "value": "9", "nodes": ["vcc", "0"]}, {"id": "Rb", "type": "Resistor", "value": "220k", "nodes": ["vcc", "b"]}, {"id": "Rc", "type": "Resistor", "value": "1k", "nodes": ["vcc", "c"]}, {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "0"]}], {"NPN": "PNP"}),
 "NMOS/PMOS": ([{"id": "Vdd", "type": "VoltageSource", "value": "10", "nodes": ["vdd", "0"]}, {"id": "Vg", "type": "VoltageSource", "value": "4", "nodes": ["g", "0"]}, {"id": "Rd", "type": "Resistor", "value": "500", "nodes": ["vdd", "d"]}, {"id": "M1", "type": "NMOS", "nodes": ["d", "g", "0"]}], {"NMOS": "PMOS"}),
 "NJFET/PJFET": ([{"id": "Vdd", "type": "VoltageSource", "value": "12", "nodes": ["vdd", "0"]}, {"id": "Rd", "type": "Resistor", "value": "2k", "nodes": ["vdd", "d"]}, {"id": "Rs", "type": "Resistor", "value": "500", "nodes": ["s", "0"]}, {"id": "Rg", "type": "Resistor", "value": "1meg", "nodes": ["g", "0"]}, {"id": "J1", "type": "NJFET", "nodes": ["d", "g", "s"]}], {"NJFET": "PJFET"}),
}
for name, (comps, swap) in cases.items():
    n1 = mk(comps); v1, _ = n1.solve(); c2 = mirror(comps, swap, None)
    for d in c2:
        if d["type"] == "PMOS": d["vto"] = "-2"
        if d["type"] == "PJFET": d["vto"] = "2"
    n2 = mk(c2); v2, _ = n2.solve(); err = max(abs(v1[k] + v2[k]) for k in v1)
    chk(f"{name}: mirrored circuit gives mirrored voltages (max err {err:.1e})", err < 1e-8, {k: (v1[k], v2[k]) for k in v1})
# 4. NMOS analytic
nl = mk(cases["NMOS/PMOS"][0]); v, _ = nl.solve(); kp, vto, lam = 5e-3, 2.0, 0.02; vov = 2.0
# Id = kp/2 vov^2 (1+lam vds), vds = 10 - 500 id  (saturation if vds >= vov)
 # solve linear: id = k0 (1 + lam (10 - 1000 id)) -> id (1 + 1000 k0 lam) = k0 (1 + 10 lam)
k0 = kp / 2 * vov * vov; idd = k0 * (1 + 10 * lam) / (1 + 500 * k0 * lam); vds = 10 - 500 * idd
chk(f"NMOS saturation: Vd {v['d']:.6f} vs analytic {vds:.6f}", abs(v["d"] - vds) < 1e-6 and nl.part("M1").info(v)[0][1] == "saturation")
# triode: lower the load
nl = mk([{"id": "Vdd", "type": "VoltageSource", "value": "10", "nodes": ["vdd", "0"]}, {"id": "Vg", "type": "VoltageSource", "value": "8", "nodes": ["g", "0"]}, {"id": "Rd", "type": "Resistor", "value": "5k", "nodes": ["vdd", "d"]}, {"id": "M1", "type": "NMOS", "nodes": ["d", "g", "0"]}])
v, _ = nl.solve(); vd = v["d"]; idt = 5e-3 * ((8 - 2) * vd - vd * vd / 2) * (1 + 0.02 * vd); chk(f"NMOS triode KCL: {idt:.6e} vs {(10 - vd) / 5000:.6e}", abs(idt - (10 - vd) / 5000) < 1e-9 and "triode" in nl.part("M1").info(v)[0][1])
# 5. op-amp
inv = mk([{"id": "V1", "type": "VoltageSource", "value": "0.5", "nodes": ["in", "0"]}, {"id": "Ri", "type": "Resistor", "value": "1k", "nodes": ["in", "m"]}, {"id": "Rf", "type": "Resistor", "value": "10k", "nodes": ["m", "out"]}, {"id": "U1", "type": "OpAmp", "nodes": ["0", "m", "out"]}])
v, _ = inv.solve(); chk(f"inverting amp: out {v['out']:.5f} (ideal -5)", abs(v["out"] + 5) < 2e-3)
inv.part("V1").value = "3"; v, _ = inv.solve(); chk(f"inverting amp saturates: out {v['out']:.4f}", -15.01 < v["out"] < -14.0)
cl = mk([{"id": "V1", "type": "VoltageSource", "value": "0", "ac": "0.001", "nodes": ["in", "0"]}, {"id": "Ri", "type": "Resistor", "value": "1k", "nodes": ["m", "0"]}, {"id": "Rf", "type": "Resistor", "value": "99k", "nodes": ["m", "out"]}, {"id": "U1", "type": "OpAmp", "nodes": ["in", "m", "out"]}])
sw = ac.sweep(cl, 100, 1e6, 200); m = ac.metrics(sw["f"], sw["V"]["out"], None); print("   noninverting x100: gain", m["peak"] / 0.001, "f3dB", m["f_high"])
chk("op-amp GBW: gain 100, -3 dB near GBW/100 = 10 kHz", abs(m["peak"] / 0.001 - 100) < 0.5 and abs(m["f_high"] - 1e4) < 400)
# 6. transformer AC vs analytic 2x2
tf = mk([{"id": "V1", "type": "VoltageSource", "value": "0", "ac": "1", "freq": "1k", "nodes": ["p", "0"]}, {"id": "T1", "type": "Transformer", "value": "100m", "ratio": "2", "k": "0.95", "nodes": ["p", "0", "s", "sg"]},
         {"id": "RL", "type": "Resistor", "value": "1k", "nodes": ["s", "sg"]}, {"id": "Rg", "type": "Resistor", "value": "1meg", "nodes": ["sg", "0"]}])
assert not tf.validate(), tf.validate()
pt = ac.point(ac.prepare(tf), 1000.0); w = 2 * math.pi * 1000; L1, L2, M = 0.1, 0.4, 0.95 * 0.1 * 2
# primary V=1; secondary: V2 = -I2*RL (I2 from s+ to s- through winding, load across winding) : jw(M I1 + L2 I2) = V2 = -RL I2  ; jw(L1 I1 + M I2) = 1
a11, a12, a21, a22 = 1j * w * L1, 1j * w * M, 1j * w * M, 1j * w * L2 + 1000; det = a11 * a22 - a12 * a21
I1 = a22 / det; I2 = -a21 / det; Vs = -1000 * I2
chk(f"transformer: |Vsec| {abs(pt['V']['s'] - pt['V']['sg']):.5f} vs analytic {abs(Vs):.5f}", abs(abs(pt["V"]["s"] - pt["V"]["sg"]) - abs(Vs)) < 1e-4)
# 7. AC vs transient on an amplifier with junction capacitances (small signal)
amp = mk([{"id": "Vcc", "type": "VoltageSource", "value": "12", "nodes": ["vcc", "0"]}, {"id": "Vin", "type": "VoltageSource", "value": "0", "ac": "0.002", "freq": "20k", "nodes": ["in", "0"]},
          {"id": "Cc", "type": "Capacitor", "value": "10u", "nodes": ["in", "b"]}, {"id": "R1", "type": "Resistor", "value": "47k", "nodes": ["vcc", "b"]}, {"id": "R2", "type": "Resistor", "value": "10k", "nodes": ["b", "0"]},
          {"id": "Rc", "type": "Resistor", "value": "3.3k", "nodes": ["vcc", "c"]}, {"id": "Re", "type": "Resistor", "value": "1k", "nodes": ["e", "0"]}, {"id": "Ce", "type": "Capacitor", "value": "100u", "nodes": ["e", "0"]},
          {"id": "Q1", "type": "NPN", "cbe": "20p", "cbc": "5p", "nodes": ["c", "b", "e"]}])
assert not amp.validate(), amp.validate()
prep = ac.prepare(amp); pt = ac.point(prep, 20000.0); H = pt["V"]["c"]; r = T.run(amp, 0.0016, 8000); st = T.stats(r["t"], r["V"]["c"], 0.0010)
print("   amplifier gain", abs(H) / 0.002, " tran pp/2 / vin", st["pp"] / 2 / 0.002)
chk("BJT amplifier: AC gain = transient amplitude", abs(st["pp"] / 2 - abs(H)) / abs(H) < 0.03)
# 8. op-amp follower step response: first-order pole at GBW (backward Euler)
fol = mk([{"id": "V1", "type": "VoltageSource", "value": "0", "ac": "0.5", "freq": "100k", "wave": "square", "nodes": ["in", "0"]}, {"id": "U1", "type": "OpAmp", "gbw": "1meg", "nodes": ["in", "o", "o"]}])
r = T.run(fol, 2e-6, 4000); tau = 1 / (2 * math.pi * 1e6); worst = 0
for tt in (0.1e-6, 0.2e-6, 0.4e-6, 0.8e-6):
    k = round(tt / 2e-6 * 4000); worst = max(worst, abs(r["V"]["o"][k] - 0.5 * (1 - math.exp(-tt / tau))))
chk(f"op-amp follower step response matches 1-exp(-t/tau) (worst {worst:.1e} V)", worst < 3e-3)
# 9. CMOS inverter transfer
def inv(vin):
    n, _ = parse(json.dumps({"components": [{"id": "Vdd", "type": "VoltageSource", "value": "5", "nodes": ["vdd", "0"]}, {"id": "Vi", "type": "VoltageSource", "value": str(vin), "nodes": ["in", "0"]},
        {"id": "Mp", "type": "PMOS", "vto": "-1", "kp": "2m", "nodes": ["out", "in", "vdd"]}, {"id": "Mn", "type": "NMOS", "vto": "1", "kp": "2m", "nodes": ["out", "in", "0"]}, {"id": "Rl", "type": "Resistor", "value": "1meg", "nodes": ["out", "0"]}]}))
    return n.solve()[0]["out"]
chk(f"CMOS inverter: 0 V -> {inv(0):.4f}, 5 V -> {inv(5):.4f}, 2.5 V -> {inv(2.5):.3f}", inv(0) > 4.99 and inv(5) < 0.01 and abs(inv(2.5) - 2.5) < 0.05)
# 10. BJT as a switch: saturation
sw = mk([{"id": "V1", "type": "VoltageSource", "value": "5", "nodes": ["a", "0"]}, {"id": "Rb", "type": "Resistor", "value": "10k", "nodes": ["a", "b"]}, {"id": "Rc", "type": "Resistor", "value": "1k", "nodes": ["a", "c"]}, {"id": "Q1", "type": "NPN", "nodes": ["c", "b", "0"]}])
v, _ = sw.solve(); inf = dict(sw.part("Q1").info(v)); chk(f"BJT switch saturates: Vce {v['c']:.3f} V, {inf['region']}", v["c"] < 0.3 and inf["region"] == "saturation")
print("TRTEST failures", bad); sys.exit(1 if bad else 0)
