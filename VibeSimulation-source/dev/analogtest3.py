"""Random circuits with transistors, op-amps and transformers: every solution found must satisfy Kirchhoff's current law at every node (computed from the terminal currents, independently of the Newton iteration)."""
import sys, os, json, random, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog.solver import solve, SolveError
seed, N = int(sys.argv[1]) if len(sys.argv) > 1 else 1, int(sys.argv[2]) if len(sys.argv) > 2 else 200
reasons = {}
rng = random.Random(seed); ok = refused = bad = invalid = 0; types = {}
def gen():
    nets = [f"n{i}" for i in range(1, rng.randint(3, 6))]; pool = nets + ["0"]; comps = []
    comps.append({"id": "V1", "type": "VoltageSource", "value": str(rng.choice([5, 9, 12, -5, -12])), "nodes": [nets[0], "0"]})
    k = 0
    for n in nets[1:]: k += 1; comps.append({"id": f"Rg{k}", "type": "Resistor", "value": str(rng.choice([100, 1000, 4700, 22000])), "nodes": [n, "0"]})
    for j in range(rng.randint(2, 5)):
        a, b = rng.sample(pool, 2); comps.append({"id": f"R{j}", "type": "Resistor", "value": str(rng.choice([220, 1000, 10000, 100000])), "nodes": [a, b]})
    if rng.random() < 0.4: comps.append({"id": "V2", "type": "VoltageSource", "value": str(rng.choice([1, 2, 3.3, -2])), "nodes": [rng.choice(nets[1:]), "0"]})
    for j in range(rng.randint(1, 3)):
        t = rng.choice(["NPN", "PNP", "NMOS", "PMOS", "NJFET", "PJFET", "IGBT", "OpAmp", "Transformer"])
        nn = {"OpAmp": 3, "Transformer": 4}.get(t, 3); nodes = [rng.choice(pool) for _ in range(nn)]
        if t == "Transformer": nodes = rng.sample(pool, 2) + rng.sample(pool, 2)
        if t == "OpAmp" and nodes[2] == "0": nodes[2] = rng.choice(nets)
        d = {"id": f"X{j}", "type": t, "nodes": nodes}
        if t == "Transformer": d["value"] = "10m"; d["ratio"] = str(rng.choice([0.5, 1, 2]))
        comps.append(d)
    return comps
for case in range(N):
    comps = gen(); nl, e = parse(json.dumps({"components": comps}))
    if e or nl.validate(): invalid += 1; continue
    parts = [nl._dup(p) for p in nl.parts]
    try: volts, res, bcur = solve(parts, want_bcur=True)
    except SolveError as ex: refused += 1; reasons[str(ex)[:60]] = reasons.get(str(ex)[:60], 0) + 1; continue
    # KCL at every node from the terminal currents
    flow = {n: 0.0 for n in volts}; big = 1e-9
    for p in parts:
        if p.nterm == 2:
            i = res[p.id][1]; tc = [i, -i]
        else: tc = p.terminal_currents(volts, bcur)
        for n, c in zip(p.nodes, tc): flow[n] += c; big = max(big, abs(c))
    resid = max(abs(flow[n]) for n in flow if n != "0")
    for p in parts: types[type(p).__name__] = types.get(type(p).__name__, 0) + 1
    if resid > 1e-6 * big + 1e-9: bad += 1; print("KCL violated", case, resid, big, json.dumps(comps)[:400])
    else: ok += 1
print(f"circuits solved & verified: {ok}  refused by the solver: {refused}  invalid (rejected by validation): {invalid}  KCL failures: {bad}"); print("parts exercised:", types)
print(reasons); sys.exit(1 if bad else 0)
