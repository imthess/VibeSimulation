"""Noise analysis against closed forms (Johnson noise, parallel resistors, kT/C, shot noise, input-referred)."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse
from vibesimulation.analog import noise as N, thermal
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)
def mk(parts):
    nl, e = parse(json.dumps({"components": parts})); assert not e, e; assert not nl.validate(), nl.validate(); return nl
K = 1.380649e-23; T = 300.15
r = N.run(mk([{"id": "R1", "type": "R", "value": "1k", "nodes": ["o", "0"]}, {"id": "Vx", "type": "V", "value": 0, "nodes": ["z", "0"]}, {"id": "R9", "type": "R", "value": 1, "nodes": ["z", "o"]}]), "o", 10, 1e5, 20) if False else None
nl = mk([{"id": "R1", "type": "R", "value": "1k", "nodes": ["o", "0"]}, {"id": "I1", "type": "CurrentSource", "value": 0, "nodes": ["0", "o"]}])
r = N.run(nl, "o", 10, 1e5, 20)
ok(abs(r["onoise"][5] - math.sqrt(4 * K * T * 1000)) < 1e-12, f"Johnson noise of 1 kΩ: {r['onoise'][5] * 1e9:.3f} nV/√Hz")
nl = mk([{"id": "R1", "type": "R", "value": "1k", "nodes": ["o", "0"]}, {"id": "R2", "type": "R", "value": "3k", "nodes": ["o", "0"]}])
r = N.run(nl, "o", 10, 1e5, 10); ok(abs(r["onoise"][0] - math.sqrt(4 * K * T * 750)) < 1e-12, "two resistors in parallel: noise of 750 Ω")
# divider driven by a source: the source is a short for noise: R1 || R2
nl = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "2k", "nodes": ["a", "o"]}, {"id": "R2", "type": "R", "value": "2k", "nodes": ["o", "0"]}])
r = N.run(nl, "o", 100, 1e4, 10, input_source="V1")
ok(abs(r["onoise"][0] - math.sqrt(4 * K * T * 1000)) < 1e-12, "voltage source counts as a short")
ok(abs(r["gain"][0] - 0.5) < 1e-9 and abs(r["inoise"][0] - r["onoise"][0] / 0.5) < 1e-15, "input-referred noise = output / gain")
ok(set(r["by_part_rms"]) == {"R1", "R2"} and abs(r["contrib"]["R1"][0] - r["contrib"]["R2"][0]) < 1e-30, "equal contributions from equal resistors")
# kT/C
nl = mk([{"id": "R1", "type": "R", "value": "10k", "nodes": ["o", "0"]}, {"id": "C1", "type": "C", "value": "1p", "nodes": ["o", "0"]}])
fc = 1 / (2 * math.pi * 10e3 * 1e-12)
r = N.run(nl, "o", fc / 1e4, fc * 1e4, 600)
want = math.sqrt(K * T / 1e-12); ok(abs(r["total_rms"] - want) / want < 0.02, f"kT/C: {r['total_rms'] * 1e6:.2f} µV rms (expected {want * 1e6:.2f})")
ok(abs(r["by_part_rms"]["R1"] - r["total_rms"]) < 1e-12, "all of it comes from the resistor")
# temperature raises noise by sqrt(T)
t1 = N.run(mk([{"id": "R1", "type": "R", "value": "1k", "nodes": ["o", "0"]}, {"id": "R2", "type": "R", "value": "1k", "nodes": ["o", "0"]}]), "o", 10, 100, 3)["onoise"][0]
nl = mk([{"id": "R1", "type": "R", "value": "1k", "nodes": ["o", "0"]}, {"id": "R2", "type": "R", "value": "1k", "nodes": ["o", "0"]}]); nl.analysis = {"temp": 127}
t2 = N.run(nl, "o", 10, 100, 3)["onoise"][0]; ok(abs(t2 / t1 - math.sqrt(400.15 / 300.15)) < 1e-6, "noise follows sqrt(absolute temperature)")
# shot noise: a diode carrying 1 mA from a 5 V source through 4.3 kΩ sees 2 q I into its small-signal resistance
nl = mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "4.3k", "nodes": ["a", "o"]}, {"id": "D1", "type": "Diode", "nodes": ["o", "0"]}])
r = N.run(nl, "o", 100, 1e3, 3); volts, res = nl.solve(); i = res["D1"][1]; rd = 0.025852 / i
rt = 1 / (1 / rd + 1 / 4300.0); want = math.sqrt((2 * 1.602176634e-19 * i) * rt ** 2 + (4 * K * T / 4300.0) * rt ** 2)
ok(abs(r["onoise"][0] - want) / want < 0.01, f"diode shot + resistor thermal: {r['onoise'][0] * 1e9:.3f} nV/√Hz vs {want * 1e9:.3f}")
try: N.run(mk([{"id": "V1", "type": "V", "value": 5, "nodes": ["a", "0"]}, {"id": "L1", "type": "L", "value": "1m", "nodes": ["a", "o"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["o", "0"]}]), "o", 1, 10, 3); ok(False, "no noise sources")
except ValueError as e: ok("noise" in str(e), "a circuit with nothing noisy is explained")
try: N.run(nl, "zz", 1, 10, 3); ok(False, "bad node")
except ValueError as e: ok("zz" in str(e), "bad output net is explained")
sys.exit(1 if bad else 0)
