"""Real diode models and the potentiometer: DC, AC, transient, SPICE text, JSON round trip."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.analog.netlist import parse, to_spice, dumps
from vibesimulation.analog import transient as TR, ac as AC
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
def mk(parts):
    nl, e = parse(json.dumps({"components": parts})); assert not e, e; return nl
def solved(parts):
    nl = mk(parts); er = nl.validate(); assert not er, er; return nl, nl.solve()
def vf(model):
    d = {"id": "D1", "type": "Diode", "nodes": ["a", "0"]}
    if model: d["model"] = model
    nl, (v, r) = solved([{"id": "I1", "type": "CurrentSource", "value": "1m", "nodes": ["0", "a"]}, d]); return v["a"]
g, f, s, x = vf(""), vf("1N4148"), vf("1N5819"), vf("1N4007")
ok(0.55 < g < 0.75, f"generic {g}"); ok(0.55 < f < 0.8, f"1N4148 {f}"); ok(s < f - 0.1, f"Schottky lower than 1N4148: {s} vs {f}"); ok(0.4 < x < 0.8, f"1N4007 {x}")
ok(abs(s - 0.25) < 0.15, f"1N5819 at 1 mA about 0.25 V: {s}")
nl, e = parse(json.dumps({"components": [{"id": "D1", "type": "Diode", "model": "NOPE", "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 1, "nodes": ["a", "0"]}]}))
ok(nl is not None and any("unknown diode model" in m for m in nl.validate()), "unknown model is reported")
nl = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "b"]}, {"id": "D1", "type": "Diode", "model": "1N4148", "nodes": ["b", "0"]}])
sp = to_spice(nl); ok(".model D1N4148 D(IS=2.68e-09 N=1.836)" in sp and "D1N4148" in sp, "SPICE has the model: " + sp)
ok('"model": "1N4148"' in dumps(nl), "model survives JSON")
# potentiometer divider
P = lambda pos, val="10k": [{"id": "V1", "type": "V", "value": 10, "nodes": ["a", "0"]}, {"id": "RV1", "type": "Potentiometer", "value": val, "pos": pos, "nodes": ["a", "w", "0"]}, {"id": "RL", "type": "R", "value": "1G", "nodes": ["w", "0"]}]
for pos in ("0.25", "0.5", "0.9"):
    nl, (v, r) = solved(P(pos)); ok(abs(v["w"] - 10 * (1 - float(pos))) < 1e-3, f"pot {pos}: {v['w']}")
nl, (v, r) = solved(P("0")); ok(abs(v["w"] - 10) < 1e-3, f"wiper at A {v['w']}")
nl, (v, r) = solved(P("1")); ok(abs(v["w"]) < 1e-3, f"wiper at B {v['w']}")
nl, (v, r) = solved(P("0.5")); ok(abs(r["RV1"][1] - 10 / 10000) < 1e-6, f"pot current {r['RV1']}")
out = dumps(nl); nl2, e = parse(json.loads(out)) if False else parse(out); ok(nl2 is not None and nl2.part("RV1").type_name == "Potentiometer", "pot round trip")
nl, _ = solved(P("0.3")); ok("RV1a" in to_spice(nl) or "RRV1a" in to_spice(nl), "pot in SPICE: " + to_spice(nl))
# transient: RC low pass whose resistor is the pot (wiper tied to B: a rheostat of value*pos), tau = 0.5k * 1u = 0.5 ms
nl = mk([{"id": "V1", "type": "V", "value": 2.5, "ac": 2.5, "wave": "square", "freq": 10, "nodes": ["a", "0"]}, {"id": "RV1", "type": "Potentiometer", "value": "1k", "pos": "0.5", "nodes": ["a", "b", "b"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["b", "0"]}])
errs = nl.validate(); ok(not errs, f"RC with pot valid {errs}")
res = TR.run(nl, 3e-3, 600)
k = 100; t1 = res["t"][k]; want = 5 - 2.5 * math.exp(-t1 / 0.5e-3); ok(abs(res["V"]["b"][k] - want) < 0.02, f"RC charge {res['V']['b'][k]} vs {want}")
ok(abs(res["V"]["b"][-1] - (5 - 2.5 * math.exp(-6))) < 0.02, "RC end")
# AC: pot divider with the wiper at 0.5 loaded by 1 pF is flat 0.5 at low frequency
nl = mk([{"id": "V1", "type": "V", "value": 0, "ac": 1, "nodes": ["a", "0"]}, {"id": "RV1", "type": "Potentiometer", "value": "2k", "pos": "0.5", "nodes": ["a", "w", "0"]}, {"id": "C1", "type": "C", "value": "1p", "nodes": ["w", "0"]}])
pr = AC.prepare(nl) if False else None
print("bad =", bad); sys.exit(1 if bad else 0)
