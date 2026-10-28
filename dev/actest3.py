"""Round trip of AC sources / analyses through SPICE text and JSON."""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.analog.netlist import parse, to_spice, dumps
from vibesimulation.imports.spice_in import parse_spice
bad = 0
def chk(n, c):
    global bad; print("ok  " if c else "FAIL", n); bad += (not c)
for wave, ph in (("sine", 0), ("sine", 37.5), ("square", 0), ("square", 90), ("triangle", 0), ("triangle", 45)):
    J = {"components": [{"id": "V1", "type": "VoltageSource", "value": "1", "ac": "2", "freq": "1k", "phase": str(ph), "wave": wave, "nodes": ["a", "0"]},
                        {"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["a", "b"]}, {"id": "C1", "type": "Capacitor", "value": "1u", "nodes": ["b", "0"]}],
         "analysis": {"ac": {"from": "10", "to": "100k", "points": 41, "scale": "log"}, "tran": {"stop": "5m", "steps": 500}}}
    nl, e = parse(json.dumps(J)); assert not e, e
    txt = to_spice(nl); nl2, notes = parse_spice(txt); p = nl2.part("V1")
    ok = abs(p.ac_amp() - 2) < 1e-9 and abs(p.freq() - 1000) < 1e-6 and p.extra["wave"] == wave and abs(p.number() - 1) < 1e-9
    # compare waveforms numerically (phase may be wrapped by 360)
    q = nl.part("V1"); err = max(abs(q.at(t * 1e-5 + 3.3e-6) - p.at(t * 1e-5 + 3.3e-6)) for t in range(0, 300))
    chk(f"{wave} {ph}: params ok, waveform max diff {err:.2e}, notes {notes}", ok and err < 1e-6)
    chk("  analysis", nl2.analysis.get("tran", {}).get("steps") == 500 and nl2.analysis.get("ac", {}).get("points") in (41, 42, 40) and ".ac dec" in txt and ".tran" in txt)
# only AC card
nl, notes = parse_spice("t\nV1 a 0 DC 0 AC 1 90\nR1 a 0 1k\n.end\n"); p = nl.part("V1"); chk("AC card only", p.ac_amp() == 1 and p.ac_phase() == 90)
nl, notes = parse_spice("t\nI1 0 a SIN(0 1m 50 0 0 0)\nR1 a 0 1k\n.end\n"); chk("current SIN", abs(nl.part("I1").ac_amp() - 1e-3) < 1e-12 and not notes)
nl, notes = parse_spice("t\nV1 a 0 PULSE(0 5 0 1n 1n 1m 10m)\nR1 a 0 1k\n.end\n"); chk("odd pulse noted", notes and nl.part("V1").ac_amp() == 0)
print("FAILURES:", bad); sys.exit(1 if bad else 0)
