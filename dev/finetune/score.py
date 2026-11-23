"""Is the model's circuit the same as the true one? Digital: same behaviour on every input row. Analog: same parts, values and wiring (names of nets may differ)."""
import itertools, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
import vibesimulation.workspaces.multisim.core.netlist as anet
from vibesimulation.workspaces.multisim.core.solver import is_ground
from vibesimulation.workspaces.multisim.core.units import parse_value
import vibesimulation.workspaces.logisim.core.serializer as serializer
ORDERED = {"Diode", "Zener", "LED", "VoltageSource", "CurrentSource", "Switch"}      # swapping the two nodes changes the meaning


def _digital(truth, pred):
    """-> dict of checks."""
    r = {"parses": False, "io_names": False, "behaviour": False, "gate_types": False}
    c, errs = serializer.parse(pred)
    if c is None or errs: return r
    r["parses"] = True
    t, _ = serializer.parse(truth)
    ins, outs = [p.name for p in t.inputs], [p.name for p in t.outputs]
    r["io_names"] = [p.name for p in c.inputs] == ins and sorted(p.name for p in c.outputs) == sorted(outs)
    r["gate_types"] = sorted(g.type_name for g in c.components) == sorted(g.type_name for g in t.components)
    if r["io_names"] and len(ins) <= 8 and c.order() is not None:
        ok = True
        for bits in itertools.product((0, 1), repeat=len(ins)):
            iv = dict(zip(ins, bits))
            a, b = t.simulate(iv), c.simulate(iv)
            if any(a.get(o) != b.get(o) for o in outs): ok = False; break
        r["behaviour"] = ok
    return r


def _val(v):
    try: return round(float(parse_value(v)), 12)
    except Exception: return str(v).strip().lower()


def _wl(nl, rounds=3):
    """Weisfeiler-Lehman colours of the part/net graph: equal graphs give equal colour multisets."""
    col, adj = {}, {}
    for p in nl.parts:
        col[("p", p.id)] = (p.type_name, _val(p.value) if p.value is not None else None)
        for k, n in enumerate(p.nodes):
            net = ("n", "0" if is_ground(n) else str(n))
            col.setdefault(net, "gnd" if net[1] == "0" else "net")
            port = k if p.type_name in ORDERED or len(p.nodes) > 2 else 0
            adj.setdefault(("p", p.id), []).append((port, net)); adj.setdefault(net, []).append((port, ("p", p.id)))
    for _ in range(rounds):
        col = {n: hash((col[n], tuple(sorted((pt, col[m]) for pt, m in adj.get(n, []))))) for n in col}
    return sorted(col.values())


def _analog(truth, pred):
    r = {"parses": False, "part_types": False, "values": False, "wiring": False, "behaviour": False}
    nl, errs = anet.parse(pred)
    if nl is None or errs: return r
    r["parses"] = True
    t, _ = anet.parse(truth)
    r["part_types"] = sorted(p.type_name for p in nl.parts) == sorted(p.type_name for p in t.parts)
    r["values"] = sorted((p.type_name, str(_val(p.value))) for p in nl.parts) == sorted((p.type_name, str(_val(p.value))) for p in t.parts)
    r["wiring"] = r["part_types"] and _wl(nl) == _wl(t)
    r["behaviour"] = r["values"] and r["wiring"]          # same parts, same values, same graph = same circuit
    return r


def score(truth: dict, answer_text: str):
    """truth: the true JSON dict. answer_text: what the model wrote. Returns (kind_ok, checks dict, correct bool)."""
    try:
        from vibesimulation.workspaces.ai_import.core import extract_json
    except ImportError:
        from vibesimulation.workspaces.ai_import.core.providers import extract_json
    kind = truth["kind"]
    try: pred = extract_json(answer_text)
    except Exception: return False, {"parses": False}, False
    if not isinstance(pred, dict) or pred.get("kind", kind) != kind: return False, {"parses": True, "kind": False}, False
    checks = (_digital if kind == "digital" else _analog)(truth, pred)
    return True, checks, bool(checks.get("behaviour"))
