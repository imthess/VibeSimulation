"""Function generator waveforms, oscilloscope capture, multimeter readings."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse, to_spice
from vibesimulation.analog import scope as SC, meter as ME, components as C
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1
    print("ok  " if c else "FAIL", m)
def mk(parts):
    nl, e = parse(json.dumps({"components": parts})); assert not e, e; assert not nl.validate(), nl.validate(); return nl
# --- waveforms
def src(**kw): return C.VoltageSource("V1", ["a", "0"], "0", **kw)
s = src(ac="2", freq="1k", wave="square", duty="25")
ok(s.at(0.0001) == 2 and s.at(0.0004) == -2 and s.at(0.001 + 0.0001) == 2, "square with 25 % duty is high for a quarter period")
s = src(ac="1", freq="1k", wave="sawtooth"); ok(abs(s.at(0)) < 1e-9 and abs(s.at(0.00025) - 0.5) < 1e-9 and abs(s.at(0.00049) - 0.98) < 1e-6 and s.at(0.00051) < -0.9, "sawtooth ramps -1..1 with zero at t = 0")
ok(src(ac="1", wave="square").at(0.0001) == 1 and src(ac="1", wave="square", freq="1k").at(0.0006) == -1, "square at 50 % unchanged")
ok(src(ac="1", duty="0").check() and "duty" in " ".join(src(ac="1", duty="0").check()), "bad duty is reported")
nl = mk([{"id": "V1", "type": "V", "value": 1, "ac": 2, "freq": 1000, "wave": "square", "duty": 30, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "0"]}])
ok("PULSE(-1 3 0 1n 1n 0.0003 0.001)" in to_spice(nl).replace("0.000300", "0.0003"), "SPICE keeps the duty: " + [l for l in to_spice(nl).split("\n") if l.startswith("V")][0])
# --- scope
rc = mk([{"id": "V1", "type": "V", "value": 0, "ac": 1, "freq": 1000, "wave": "sine", "nodes": ["in", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["in", "o"]}, {"id": "C1", "type": "C", "value": "159.155n", "nodes": ["o", "0"]}])
cap = SC.capture(rc, [{"probe": "V(in)", "vdiv": 0.5}, {"probe": "V(o)", "vdiv": 0.5}], "200u", trigger={"source": 0, "level": 0, "slope": "rising"}, delay=0.005)
a, b = cap["channels"]
ok(cap["triggered"] and len(cap["t"]) == 1000 and abs(cap["window"] - 0.002) < 1e-12, "capture is triggered and covers 10 divisions")
ok(abs(a["y"][0]) < 0.01 and a["y"][50] > 0.2, "trigger on a rising zero crossing: the trace starts at 0 and goes up")
ok(abs(a["read"]["vpp"] - 2) < 0.02 and abs(a["read"]["rms"] - 1 / math.sqrt(2)) < 0.01, f"Vpp {a['read']['vpp']:.3f}, RMS {a['read']['rms']:.3f}")
ok(abs(a["read"]["freq"] - 1000) < 20, f"frequency {a['read']['freq']}")
ok(abs(b["read"]["vpp"] - 2 / math.sqrt(2)) < 0.03, f"RC at its corner: Vpp {b['read']['vpp']:.3f} (-3 dB)")
# at the corner the output lags by 45 degrees: when A rises through 0, B is at sin(-45 deg) = -0.707 * ... check by value
ok(abs(b["y"][0] - (-0.5)) < 0.03, f"output lags the input by 45°: B at the trigger = {b['y'][0]:.3f} (expected -0.5)")
ac = SC.capture(rc, [{"probe": "V(o)", "coupling": "ac"}], "200u", delay=0.003); ok(abs(ac["channels"][0]["read"]["avg"]) < 1e-9, "AC coupling removes the average")
gnd = SC.capture(rc, [{"probe": "V(o)", "coupling": "gnd"}], "200u"); ok(max(gnd["channels"][0]["y"]) == 0, "grounded input is flat")
nt = SC.capture(rc, [{"probe": "V(o)"}], "200u", trigger={"source": 0, "level": 5.0, "slope": "rising", "mode": "normal"}, delay=0.005); ok(not nt["triggered"] and nt["channels"][0]["y"] is None, "normal mode: no trigger, no trace")
at = SC.capture(rc, [{"probe": "V(o)"}], "200u", trigger={"source": 0, "level": 5.0, "slope": "rising", "mode": "auto"}, delay=0.005); ok(not at["triggered"] and at["channels"][0]["y"] is not None, "auto mode: trace without a trigger")
try: SC.capture(rc, [{"probe": "V(nope)"}], "1m"); ok(False, "bad probe")
except ValueError as e: ok("nope" in str(e), "bad probe explained")
# --- meter
d = mk([{"id": "V1", "type": "V", "value": 12, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": "1k", "nodes": ["a", "o"]}, {"id": "R2", "type": "R", "value": "2k", "nodes": ["o", "0"]}])
ok(abs(ME.read(d, "vdc", "o")["value"] - 8) < 1e-9 and ME.read(d, "vdc", "o")["text"].startswith("8"), "DC voltage " + ME.read(d, "vdc", "o")["text"])
ok(abs(ME.read(d, "vdc", "a", "o")["value"] - 4) < 1e-9, "voltage between two nets")
ok(abs(ME.read(d, "idc", part="R1")["value"] - 4e-3) < 1e-12, "DC current through R1")
ok(abs(ME.read(d, "ohm", "o")["value"] - 2000) < 1, "resistance seen from o to ground (sources off): R2 || R1 = 667")  if False else None
r = ME.read(d, "ohm", "o")["value"]; ok(abs(r - 1 / (1 / 1000 + 1 / 2000)) < 0.5, f"ohms from o to ground with the supply off: {r:.1f}")
ok(abs(ME.read(d, "ohm", "a", "o")["value"] - 1000 / 1.5) < 0.5 and ME.read(d, "ohm", "a", "a")["value"] == 0, "ohms between nets")
op = mk([{"id": "V1", "type": "V", "value": 1, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "o"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["o", "q"]}, {"id": "R2", "type": "R", "value": 100, "nodes": ["q", "0"]}])
ok(abs(ME.read(op, "ohm", "o", "q")["value"] - 200) < 0.5, "ohms through the rest of the circuit, the capacitor itself is open")
cap_ = mk([{"id": "V1", "type": "V", "value": 1, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "0"]}, {"id": "C1", "type": "C", "value": "1u", "nodes": ["o", "q"]}, {"id": "R2", "type": "R", "value": 100, "nodes": ["o", "0"]}, {"id": "R3", "type": "R", "value": 100, "nodes": ["q", "0"]}])
ok(abs(ME.read(cap_, "ohm", "o", "q")["value"] - 200) < 0.5, "capacitor open in ohms mode")
ac_ = mk([{"id": "V1", "type": "V", "value": 0, "ac": 10, "freq": 50, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "0"]}])
ok(abs(ME.read(ac_, "vac", "a")["value"] - 10 / math.sqrt(2)) < 1e-9 and abs(ME.read(ac_, "iac", part="R1")["value"] - 0.1 / math.sqrt(2)) < 1e-9, "AC RMS = peak / √2")
try: ME.read(d, "vac", "o"); ok(False, "no AC source")
except ValueError as e: ok("AC" in str(e), "no AC source is explained")
try: ME.read(d, "vdc", "zz"); ok(False, "bad net")
except ValueError as e: ok("zz" in str(e), "bad net explained")
sys.exit(1 if bad else 0)
