"""Independent checks of the analog solver: KCL, KVL, power balance, textbook circuits, diode equation, validation and SPICE text."""
import sys, os, random, math, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.analog.netlist import parse, to_spice, dumps
from vibesimulation.analog.document import AnalogDocument, SAMPLE
from vibesimulation.analog.solver import SolveError, is_ground
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
def mk(parts): return parse(json.dumps({"components": parts}))
# 1. textbook circuits
nl, e = mk([{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "R2", "type": "R", "value": "1k", "nodes": ["b", "0"]}])
ok(not e and not nl.validate(), f"divider valid {e} {nl.validate() if nl else ''}"); v, r = nl.solve(); ok(abs(v["b"] - 5) < 1e-6, "divider 5 V"); ok(abs(r["R1"][1] - 5e-3) < 1e-8, "divider 5 mA"); ok(abs(r["V1"][2] + 0.05) < 1e-6, "source delivers 50 mW")
nl, e = mk(SAMPLE["components"]); ok(not nl.validate(), "sample valid"); v, r = nl.solve()
R1, R2, R3, R4, R5 = 100, 220, 470, 150, 100; r45 = R4 + R5; r3 = 1 / (1 / R3 + 1 / r45); vn2 = 5 * r3 / (R2 + r3); ok(abs(v["n2"] - vn2) < 1e-6, "ladder n2"); ok(abs(v["n3"] - vn2 * R5 / r45) < 1e-6, "ladder n3")
nl, e = mk([{"id": "I1", "type": "I", "value": "2m", "nodes": ["0", "a"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "0"]}]); v, r = nl.solve(); ok(abs(v["a"] - 2) < 1e-6, "current source into R = 2 V")
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "L1", "type": "L", "nodes": ["a", "b"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["b", "c"]}, {"id": "C1", "type": "C", "nodes": ["c", "0"]}, {"id": "R2", "type": "R", "value": 100, "nodes": ["c", "0"]}]); v, r = nl.solve()
ok(abs(v["b"] - 5) < 1e-6 and abs(v["c"] - 2.5) < 1e-6 and abs(r["C1"][1]) < 1e-9, "L short, C open")
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "D1", "type": "D", "nodes": ["b", "0"]}]); v, r = nl.solve()
vd = v["b"]; idd = 1e-14 * (math.exp(vd / 0.025852) - 1); ok(0.5 < vd < 0.8 and abs(idd - (5 - vd) / 1000) < 1e-7, f"diode forward {vd:.4f}")
nl, e = mk([{"id": "V1", "type": "V", "value": -5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "D1", "type": "D", "nodes": ["b", "0"]}]); v, r = nl.solve(); ok(abs(r["D1"][1]) < 1e-9 and abs(v["b"] + 5) < 1e-3, "diode reverse blocks")
# 2. wiring validation (the bug: dangling nets used to be accepted)
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["n1", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["n1", "0"]}, {"id": "D1", "type": "D", "nodes": ["n4", "0"]}]); er = nl.validate(); ok(any("n4" in x and "only one terminal" in x for x in er), f"dangling net flagged {er}")
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["n1", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["n1", "0"]}, {"id": "R2", "type": "R", "value": 100, "nodes": ["x", "y"]}, {"id": "R3", "type": "R", "value": 100, "nodes": ["x", "y"]}]); er = nl.validate(); ok(any("no DC path" in x for x in er), f"floating island flagged {er}")
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["n1", "0"]}, {"id": "C1", "type": "C", "nodes": ["n1", "n2"]}, {"id": "C2", "type": "C", "nodes": ["n2", "0"]}]); er = nl.validate(); ok(any("n2" in x and "no DC path" in x for x in er), f"cap-only net flagged {er}")
nl, e = mk([{"id": "R1", "type": "R", "value": 100, "nodes": ["a", "b"]}, {"id": "R2", "type": "R", "value": 100, "nodes": ["a", "b"]}]); ok(any("No ground" in x for x in nl.validate()), "no ground flagged")
nl, e = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "V2", "type": "V", "value": 3, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "0"]}])
try: nl.validate() or nl.solve(); ok(False, "parallel sources must be rejected")
except SolveError: ok(True, "parallel sources rejected")
# 3. random circuits: build a connected resistor/source network, check KCL / KVL / power
random.seed(7); checked = 0
for t in range(300):
    n = random.randint(2, 7); nets = [f"n{i}" for i in range(1, n + 1)]; parts = []
    parts.append({"id": "V1", "type": "V", "value": random.choice([1, 3.3, 5, 12]), "nodes": [nets[0], "0"]})
    for i in range(1, n): parts.append({"id": f"R{i}", "type": "R", "value": random.choice([10, 47, 100, "1k", "4.7k", "100k"]), "nodes": [nets[random.randrange(i)], nets[i]]})
    for j in range(random.randint(1, 4)):
        a, b = random.sample(nets + ["0"], 2); parts.append({"id": f"R{n + j}", "type": random.choice(["R", "R", "L", "C"]), "value": random.choice([10, 220, "2.2k"]), "nodes": [a, b]})
    if random.random() < 0.4: parts.append({"id": "I1", "type": "I", "value": "1m", "nodes": [random.choice(nets), "0"]})
    if random.random() < 0.4: parts.append({"id": "D1", "type": "D", "nodes": [random.choice(nets), random.choice(nets + ["0"])]})
    nl, e = mk(parts)
    if e: continue
    if nl.validate(): continue
    try: v, r = nl.solve()
    except SolveError: continue
    checked += 1
    canon = lambda x: "0" if is_ground(x) else str(x)
    net = {}
    for p in nl.parts:
        va, vb, i = v[canon(p.nodes[0])], v[canon(p.nodes[1])], r[p.id][1]
        ok(abs((va - vb) - r[p.id][0]) < 1e-9, f"KVL {p.id}")
        net[canon(p.nodes[0])] = net.get(canon(p.nodes[0]), 0) + i; net[canon(p.nodes[1])] = net.get(canon(p.nodes[1]), 0) - i
    for k, s in net.items():
        if k != "0": ok(abs(s) < 1e-7 * max(1, max(abs(r[p.id][1]) for p in nl.parts)), f"KCL at {k}: {s}")
    ok(abs(sum(x[2] for x in r.values())) < 1e-6 * max(1, sum(abs(x[2]) for x in r.values())), "power balance")
print("random circuits solved & verified:", checked)
# 4. SPICE text
txt = to_spice(parse(json.dumps(SAMPLE))[0]); ok(".end" in txt and "V1 n1 0 DC 5" in txt and "R2 n1 n2 220" in txt, "spice text")
# 5. document flow: dangling net now makes the doc invalid with a clear message
d = AnalogDocument(); d.load_sample(); ok(d.valid, "sample doc valid"); d.edit(lambda n: n.parts.append(type(n.parts[1])("R9", ["n9", "0"], "1k"))); ok(not d.valid and any("n9" in x for x in d.errors), f"dangling part -> invalid {d.errors}")
print("FAILURES:", bad); sys.exit(1 if bad else 0)
