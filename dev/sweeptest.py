"""Parameter sweep, temperature sweep, Monte Carlo against closed-form answers."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog import measure as M, sweeps as S, montecarlo as MC, thermal
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)
def mk(parts):
    nl, e = parse(json.dumps({"components": parts})); assert not e, e; assert not nl.validate(), nl.validate(); return nl
div = lambda **kw: mk([{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, dict({"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "o"]}, **kw), {"id": "R2", "type": "R", "value": "1k", "nodes": ["o", "0"]}])
nl = div()
ok(abs(M.evaluate(nl, {"kind": "dc", "probes": ["V(o)", "I(R1)", "V(a,o)"]})["V(o)"] - 5) < 1e-9, "dc measure")
# parameter sweep of R2: Vo = 10 R2/(1k+R2)
xs = S.values(100, 10000, 7, log=True)
r = S.parameter_sweep(nl, "R2", "value", xs, {"kind": "dc", "probes": ["V(o)"]})
ok(all(abs(v - 10 * x / (1000 + x)) < 1e-9 for v, x in zip(r["series"]["V(o)"], xs)), "parameter sweep matches Vo = 10 R2/(R1+R2)")
ok(nl.part("R2").value == "1k", "the circuit itself is untouched")
# sweep of a setting (pot position)
pot = mk([{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "RV", "type": "Potentiometer", "value": "10k", "pos": "0.5", "nodes": ["a", "w", "0"]}, {"id": "RL", "type": "R", "value": "1G", "nodes": ["w", "0"]}])
r = S.parameter_sweep(pot, "RV", "pos", S.values(0, 1, 5), {"kind": "dc", "probes": ["V(w)"]})
ok(all(abs(v - 10 * (1 - x)) < 1e-3 for v, x in zip(r["series"]["V(w)"], r["x"])), "sweep a part setting (pos)")
# AC sweep of C in an RC filter: |H| = 1/sqrt(1+(wRC)^2)
rc = mk([{"id": "V1", "type": "V", "value": 0, "ac": 1, "freq": 1000, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "o"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["o", "0"]}])
cs = S.values(1e-8, 1e-6, 5, log=True); r = S.parameter_sweep(rc, "C1", "value", cs, {"kind": "ac", "f": 1000, "probes": ["V(o)"]})
ok(all(abs(v - 1 / math.sqrt(1 + (2 * math.pi * 1000 * 1000 * c) ** 2)) < 1e-6 for v, c in zip(r["series"]["|V(o)|"], cs)), "AC measurement in a sweep")
# transient measurement
sq = mk([{"id": "V1", "type": "V", "value": 0, "ac": 1, "wave": "square", "freq": 10, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "o"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["o", "0"]}])
g = M.evaluate(sq, {"kind": "tran", "stop": "0.2", "steps": 800, "stat": "pp", "probes": ["V(a)"]}); ok(abs(g["pp(V(a))"] - 2) < 1e-6, "tran stat pp")
# temperature: resistor tc1, diode forward voltage falls ~2 mV/K
tr = div(tc1="0.004"); r = S.temperature_sweep(tr, [0, 27, 100], {"kind": "dc", "probes": ["V(o)"]})
want = lambda T: 10 * 1000 / (1000 * (1 + 0.004 * (T - 27)) + 1000)
ok(all(abs(v - want(t)) < 1e-9 for v, t in zip(r["series"]["V(o)"], r["x"])), "temperature coefficient of a resistor")
ok(abs(M.evaluate(tr, {"kind": "dc", "probes": ["V(o)"]})["V(o)"] - 5) < 1e-9, "back at 27 degrees afterwards")
dio = mk([{"id": "I1", "type": "CurrentSource", "value": "1m", "nodes": ["0", "a"]}, {"id": "D1", "type": "Diode", "nodes": ["a", "0"]}])
r = S.temperature_sweep(dio, [0, 27, 85], {"kind": "dc", "probes": ["V(a)"]}); v = r["series"]["V(a)"]
slope = (v[2] - v[0]) / 85
ok(-2.6e-3 < slope < -1.5e-3, f"diode drop falls about 2 mV/K ({slope * 1000:.2f} mV/K)")
ok(v[0] > v[1] > v[2], "monotonic")
# Monte Carlo: divider with 5 % resistors, gaussian (3 sigma = 5 %)
mc = div(tol="5"); mc.part("R2").extra["tol"] = "5"
r = MC.run(mc, {"kind": "dc", "probes": ["V(o)"]}, runs=3000, seed=1, limits=(4.8, 5.2))
st = r["stats"]["V(o)"]
# Vo = 10 R2/(R1+R2); with independent deviations d1, d2: sd(Vo) = 10 * 0.25 * sqrt(s1^2 + s2^2), s = 0.05/3
exp_sd = 10 * 0.25 * math.sqrt(2) * (0.05 / 3)
ok(abs(st["mean"] - 5) < 0.01 and abs(st["std"] - exp_sd) < 0.12 * exp_sd, f"MC mean {st['mean']:.4f} std {st['std']:.4f} (expected {exp_sd:.4f})")
ok(0.9 < st["yield"] <= 1.0 and st["min"] < 4.95 and st["max"] > 5.05 and sum(st["hist"]["counts"]) == st["n"], f"yield {st['yield']:.3f}, histogram")
r2 = MC.run(mc, {"kind": "dc", "probes": ["V(o)"]}, runs=50, seed=1); r3 = MC.run(mc, {"kind": "dc", "probes": ["V(o)"]}, runs=50, seed=1)
ok(r2["samples"] == r3["samples"], "the same seed repeats the same runs")
ok(MC.run(div(), {"kind": "dc", "probes": ["V(o)"]}, runs=20, default_tol=1, dist="uniform", seed=2)["stats"]["V(o)"]["std"] > 0, "default tolerance applies to every part")
try: MC.run(div(), {"kind": "dc", "probes": ["V(o)"]}, runs=10); ok(False, "no tolerance is an error")
except ValueError as e: ok("tolerance" in str(e), "no tolerance is explained")
try: M.check_spec(nl, {"kind": "dc", "probes": ["V(zzz)"]}); ok(False, "bad net")
except ValueError as e: ok("zzz" in str(e), "bad probe is explained")
sys.exit(1 if bad else 0)
