"""AC phasor solution vs the steady state of the transient solver on random RLC networks (and biased diodes with a small signal)."""
import sys, os, json, math, random, cmath
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog import ac, transient as T
seed, N = int(sys.argv[1]) if len(sys.argv) > 1 else 1, int(sys.argv[2]) if len(sys.argv) > 2 else 20
rng = random.Random(seed); bad = done = 0; worst = 0.0
for case in range(N):
    nn = rng.randint(2, 4); nets = [f"n{i}" for i in range(1, nn + 1)]; comps = []
    diode = case % 5 == 4
    comps.append({"id": "V1", "type": "VoltageSource", "value": "2" if diode else "0", "ac": "0.005" if diode else str(rng.choice([1, 2, 5])), "freq": "1k", "phase": str(rng.choice([0, 30, -45])), "nodes": ["n1", "0"]})
    k = 0
    for n in nets[1:] + nets[:1]:                                      # every net gets a resistor to ground: damping and a DC path
        if n == "n1" and not diode: continue
        k += 1; comps.append({"id": f"Rg{k}", "type": "Resistor", "value": str(rng.choice([220, 470, 1000, 2000])), "nodes": [n, "0"]})
    for j in range(rng.randint(3, 6)):
        a, b = rng.sample(nets + ["0"], 2); t = rng.choice("RLC")
        if diode and j == 0: comps.append({"id": "D1", "type": "Diode", "nodes": [a, b]}); continue
        v = {"R": rng.choice([100, 330, 1000, 1500]), "L": rng.choice([1e-3, 4.7e-3, 10e-3, 20e-3]), "C": rng.choice([47e-9, 220e-9, 470e-9, 1e-6])}[t]
        comps.append({"id": f"{t}{j}", "type": {"R": "Resistor", "L": "Inductor", "C": "Capacitor"}[t], "value": str(v), "nodes": [a, b]})
    nl, e = parse(json.dumps({"components": comps}))
    if e or nl.validate(): continue
    try: prep = ac.prepare(nl); pt = ac.point(prep, 1000.0); r = T.run(nl, 0.06, 12000)
    except ValueError as ex: print("skip", ex); continue
    done += 1; w = 2 * math.pi * 1000
    for n in nets:
        H = pt["V"][n]; big = max(abs(H), 1e-12); err = 0.0
        for kk in range(9600, 12001, 25):
            t = r["t"][kk]; ex = abs(H) * math.sin(w * t + cmath.phase(H)); err = max(err, abs(r["V"][n][kk] - (ex + (r["V"][n][-1] * 0 if False else 0))))
        # remove DC offset (diode cases): compare AC part only
        if diode:
            seg = r["V"][n][9600:]; dc = sum(seg) / len(seg); err = 0.0
            for kk in range(9600, 12001, 25):
                t = r["t"][kk]; err = max(err, abs((r["V"][n][kk] - dc) - abs(H) * math.sin(w * t + cmath.phase(H))))
        tol = (0.06 if diode else 3e-3) * big + (2e-5 if diode else 1e-6); worst = max(worst, err / big)
        if err > tol: bad += 1; print("MISMATCH case", case, n, "err", err, "amp", abs(H), json.dumps(comps)[:300])
print("circuits", done, "mismatches", bad, "worst rel err %.2e" % worst); sys.exit(1 if bad else 0)
