"""New DC parts and analyses: dependent sources, Zener, LED, switch, meters, sweep, Thevenin/Norton, SPICE text, round trips."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.analog.netlist import parse, to_spice, dumps
from vibesimulation.analog import analysis as AN
from vibesimulation.analog.solver import SolveError
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
def mk(parts, **kw):
    nl, e = parse(json.dumps(dict({"components": parts}, **kw))); assert not e, e; return nl
def solved(parts):
    nl = mk(parts); er = nl.validate(); assert not er, er; return nl, nl.solve()
# VCVS amplifier: gain 10 of a divider output
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 2, "nodes": ["a", "0"]}, {"id": "E1", "type": "VCVS", "value": 10, "control": ["a", "0"], "nodes": ["o", "0"]}, {"id": "RL", "type": "R", "value": "1k", "nodes": ["o", "0"]}])
ok(abs(v["o"] - 20) < 1e-6 and abs(r["RL"][1] - 0.02) < 1e-9, f"VCVS {v}")
# VCCS: g = 2 mS, input 3 V -> 6 mA into 1 k = 6 V
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 3, "nodes": ["a", "0"]}, {"id": "G1", "type": "VCCS", "value": "2m", "control": ["a", "0"], "nodes": ["0", "o"]}, {"id": "RL", "type": "R", "value": "1k", "nodes": ["o", "0"]}])
ok(abs(v["o"] - 6) < 1e-6, f"VCCS {v}")
# CCCS: ammeter in series with R carries 5 mA, beta 100 -> 0.5 A?? use beta 10 -> 50 mA into 10 ohm = 0.5 V
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "A1", "type": "Ammeter", "nodes": ["b", "0"]},
                     {"id": "F1", "type": "CCCS", "value": 10, "control": "A1", "nodes": ["0", "o"]}, {"id": "R2", "type": "R", "value": 10, "nodes": ["o", "0"]}])
ok(abs(r["A1"][1] - 5e-3) < 1e-9 and abs(v["o"] - 0.5) < 1e-6, f"CCCS/ammeter {r['A1']} {v}")
# CCVS: 1 k transresistance on 5 mA = 5 V
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "A1", "type": "Ammeter", "nodes": ["b", "0"]},
                     {"id": "H1", "type": "CCVS", "value": "1k", "control": "A1", "nodes": ["o", "0"]}, {"id": "R2", "type": "R", "value": "1k", "nodes": ["o", "0"]}])
ok(abs(v["o"] - 5) < 1e-6, f"CCVS {v}")
# Zener regulator: 12 V, 470 ohm, 5.1 V zener (reverse): output ~5.1 V (+ a little)
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 12, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 470, "nodes": ["a", "o"]}, {"id": "Z1", "type": "Zener", "vz": "5.1", "nodes": ["0", "o"]}])
ok(5.0 < v["o"] < 5.3, f"zener regulates {v['o']}"); iz = (12 - v["o"]) / 470; ok(abs(-r["Z1"][1] - iz) < 1e-6, f"zener current {r['Z1']} vs {iz}")
ok(abs(r["Z1"][1] + iz) < 1e-6 or True, "")
# Zener forward = diode
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "o"]}, {"id": "Z1", "type": "Zener", "nodes": ["o", "0"]}]); ok(0.5 < v["o"] < 0.8, f"zener forward {v['o']}")
# LED with 330 ohm from 5 V: Vf about 1.7 V
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 330, "nodes": ["a", "o"]}, {"id": "D1", "type": "LED", "nodes": ["o", "0"]}]); ok(1.5 < v["o"] < 2.0, f"LED Vf {v['o']}")
# switch
base = [{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "S1", "type": "Switch", "nodes": ["a", "b"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["b", "0"]}]
nl, (v, r) = solved(base); ok(abs(v["b"] - 10) < 1e-5, "closed switch passes")
nl, (v, r) = solved([base[0], dict(base[1], state="open"), base[2]]); ok(abs(v["b"]) < 1e-6, "open switch blocks")
# voltmeter does not load; ammeter reads series current
nl, (v, r) = solved([{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "R2", "type": "R", "value": "1k", "nodes": ["b", "0"]}, {"id": "M1", "type": "Voltmeter", "nodes": ["b", "0"]}])
ok(abs(v["b"] - 5) < 1e-6 and abs(r["M1"][0] - 5) < 1e-6 and abs(r["M1"][1]) < 1e-9, "voltmeter")
# validation of controls
nl = mk([{"id": "V1", "type": "V", "value": 1, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 1, "nodes": ["a", "0"]}, {"id": "F1", "type": "CCCS", "value": 1, "control": "R1", "nodes": ["0", "o"]}, {"id": "R2", "type": "R", "value": 1, "nodes": ["o", "0"]}]); er = nl.validate(); ok(any("F1" in e and "control" in e for e in er), f"control must be a branch part {er}")
nl = mk([{"id": "V1", "type": "V", "value": 1, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 1, "nodes": ["a", "0"]}, {"id": "G1", "type": "VCCS", "value": 1, "control": ["zz", "0"], "nodes": ["0", "o"]}, {"id": "R2", "type": "R", "value": 1, "nodes": ["o", "0"]}]); er = nl.validate(); ok(any("zz" in e for e in er), f"unknown control node {er}")
# DC sweep: divider output versus source, and diode I-V (monotonic, matches the equation)
div = mk([{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "R2", "type": "R", "value": "3k", "nodes": ["b", "0"]}])
sw = AN.sweep(div, "V1", 0, 12, 13); ok(all(abs(sw["V"]["b"][k] - 0.75 * sw["x"][k]) < 1e-9 for k in range(13)), "sweep divider")
sw = AN.sweep(div, "R2", 1000, 3000, 3); ok(abs(sw["V"]["b"][0] - 5) < 1e-9 and abs(sw["V"]["b"][2] - 7.5) < 1e-9, "sweep resistor")
dio = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "D1", "type": "D", "nodes": ["b", "0"]}])
sw = AN.sweep(dio, "V1", -5, 5, 21); ok(not sw["errors"] and all(sw["I"]["D1"][k] <= sw["I"]["D1"][k + 1] + 1e-12 for k in range(20)), f"diode sweep monotone {sw['errors']}")
zen = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 470, "nodes": ["a", "o"]}, {"id": "Z1", "type": "Zener", "vz": 5.1, "nodes": ["0", "o"]}])
sw = AN.sweep(zen, "V1", 0, 15, 31); vo = sw["V"]["o"]; ok(not sw["errors"] and abs(vo[6] - 3.0) < 1e-3 and 5.0 < vo[30] < 5.3, f"zener line regulation {vo[6]:.3f} {vo[30]:.3f}")
# Thevenin / Norton on a classic bridge-ish circuit
th = mk([{"id": "V1", "type": "V", "value": 12, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "b"]}, {"id": "R2", "type": "R", "value": 300, "nodes": ["b", "0"]}, {"id": "R3", "type": "R", "value": 50, "nodes": ["b", "c"]}, {"id": "RL", "type": "R", "value": 200, "nodes": ["c", "0"]}])
t = AN.thevenin(th, "RL"); ok(abs(t["voc"] - 9) < 1e-9 and abs(t["rth"] - 125) < 1e-9 and abs(t["isc"] - 0.072) < 1e-9 and abs(t["pmax"] - 81 / 500) < 1e-9, f"thevenin {t}")
# the equivalent gives the same load current as the original
vl = 9 * 200 / (125 + 200); full = th.solve()[0]["c"]; ok(abs(vl - full) < 1e-9, "equivalent matches")
th2 = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "b"]}, {"id": "D1", "type": "D", "nodes": ["b", "0"]}, {"id": "RL", "type": "R", "value": 10, "nodes": ["b", "0"]}])
try: AN.thevenin(th2, "RL"); ok(False, "diode circuit must be refused")
except ValueError: ok(True, "")
# with a dependent source inside
th3 = mk([{"id": "V1", "type": "V", "value": 2, "nodes": ["a", "0"]}, {"id": "E1", "type": "VCVS", "value": 3, "control": ["a", "0"], "nodes": ["o", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["o", "c"]}, {"id": "RL", "type": "R", "value": 100, "nodes": ["c", "0"]}, {"id": "R9", "type": "R", "value": 1, "nodes": ["a", "0"]}])
t = AN.thevenin(th3, "RL"); ok(abs(t["voc"] - 6) < 1e-9 and abs(t["rth"] - 100) < 1e-9, f"thevenin with VCVS {t}")
# JSON round trip, analysis block, SPICE
nl = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "S1", "type": "Switch", "state": "open", "nodes": ["a", "b"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["b", "0"]}, {"id": "Z1", "type": "Zener", "vz": 3.3, "nodes": ["0", "b"]},
         {"id": "E1", "type": "VCVS", "value": 2, "control": ["b", "0"], "nodes": ["o", "0"]}, {"id": "R2", "type": "R", "value": 1, "nodes": ["o", "0"]}], analysis={"sweep": {"part": "V1", "from": 0, "to": 5, "points": 6}})
nl2 = parse(dumps(nl))[0]; ok(dumps(nl2) == dumps(nl), "round trip"); ok(nl2.part("S1").extra["state"] == "open" and nl2.part("Z1").extra["vz"] == 3.3 and nl2.part("E1").extra["control"] == ["b", "0"] and nl2.analysis["sweep"]["points"] == 6, "extras survive")
sp = to_spice(nl); ok(".model DZ_Z1 D(BV=3.3" in sp and "E1 o 0 b 0 2" in sp and ".dc V1 0 5 1" in sp and "RS1 a b 1e+12" in sp, f"spice\n{sp}")
# random circuits with the new parts: KCL at every node, KVL per part, power balance
import random
from vibesimulation.analog.solver import is_ground
random.seed(11); checked = 0; refused = 0
for t in range(400):
    n = random.randint(3, 7); nets = [f"n{i}" for i in range(1, n + 1)]; parts = [{"id": "V1", "type": "V", "value": random.choice([3, 5, 12]), "nodes": [nets[0], "0"]}]
    for i in range(1, n): parts.append({"id": f"R{i}", "type": "R", "value": random.choice([47, 100, "1k", "4.7k"]), "nodes": [random.choice(nets[:i]), nets[i]]})
    for j in range(random.randint(1, 4)):
        kind = random.choice(["R", "VCVS", "VCCS", "Switch", "LED", "Zener", "CCCS", "CCVS", "Ammeter"]); a, b = random.sample(nets + ["0"], 2); c = random.sample(nets + ["0"], 2)
        d = {"id": f"X{j}", "type": kind, "nodes": [a, b]}
        if kind == "R": d["value"] = 220
        elif kind in ("VCVS", "VCCS"): d.update(value=random.choice([0.5, 2, "1m"]), control=c)
        elif kind in ("CCCS", "CCVS"): d.update(value=random.choice([0.5, 2, "100"]), control="V1")
        elif kind == "Switch": d["state"] = random.choice(["open", "closed"])
        elif kind == "Zener": d["vz"] = random.choice([3.3, 5.1])
        parts.append(d)
    nl, e = parse(json.dumps({"components": parts}))
    if e or nl.validate(): continue
    try: v, r = nl.solve()
    except SolveError: refused += 1; continue
    checked += 1; net = {}; canon = lambda x: "0" if is_ground(x) else str(x)
    for p in nl.parts:
        va, vb, i = v[canon(p.nodes[0])], v[canon(p.nodes[1])], r[p.id][1]
        ok(abs((va - vb) - r[p.id][0]) < 1e-9, f"KVL {p.id}")
        net[canon(p.nodes[0])] = net.get(canon(p.nodes[0]), 0) + i; net[canon(p.nodes[1])] = net.get(canon(p.nodes[1]), 0) - i
    big = max(1e-3, max(abs(x[1]) for x in r.values()))
    for k, sm in net.items():
        if k != "0": ok(abs(sm) < 1e-5 * big, f"KCL {k}: {sm} (circuit {t})")
    ok(abs(sum(x[2] for x in r.values())) < 1e-6 * max(1, sum(abs(x[2]) for x in r.values())), f"power balance circuit {t}")
print("random circuits with new parts verified:", checked, "refused by the solver:", refused)
print("failures", bad)
