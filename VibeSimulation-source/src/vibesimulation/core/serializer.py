"""JSON <-> Circuit.

Accepts the original simple format (``{"inputs": ["A"], "outputs": ["Y"], "gates": [{"id", "type", "in": [...], "out": "x"}]}``)
as well as the extended one with bit widths and multi-pin components.
"""
import json

from .model import Circuit, IOPin


def _pins(raw, key, errs, allow_width):
    if not isinstance(raw, list):
        errs.append(f'"{key}" must be a list'); return []
    pins = []
    for x in raw:
        if isinstance(x, dict) and "name" in x:
            w = x.get("width", 1)
            if not isinstance(w, int) or not 1 <= w <= 64:
                errs.append(f'{key} "{x["name"]}": width must be 1 to 64'); w = 1
            pin = IOPin(str(x["name"]), w if allow_width else 1)
            v = x.get("pos")
            if isinstance(v, list) and len(v) == 2 and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in v): pin.pos = (int(round(v[0] / 10.0)) * 10, int(round(v[1] / 10.0)) * 10)
            elif v is not None: errs.append(f'{key} "{x["name"]}": "pos" must be two numbers')
            pins.append(pin)
        elif isinstance(x, (str, int)):
            pins.append(IOPin(str(x), 1))
        else:
            errs.append(f'Each item of "{key}" must be a name or {{"name": ..., "width": ...}}')
    return pins


def parse(text):
    """text (str) or already-parsed dict -> (Circuit or None, [error messages])."""
    from ..components.registry import ComponentRegistry
    if isinstance(text, str):
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            return None, [f"Not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})"]
    else:
        raw = text
    if not isinstance(raw, dict):
        return None, ['The JSON must be an object like {"inputs": [...], "outputs": [...], "gates": [...]}']
    errs = []
    circuit = Circuit(_pins(raw.get("inputs", []), "inputs", errs, True), _pins(raw.get("outputs", []), "outputs", errs, False))
    items = raw.get("gates", raw.get("components", []))
    if not isinstance(items, list):
        errs.append('"gates" must be a list'); items = []
    used = set()
    for k, d in enumerate(items, 1):
        if not isinstance(d, dict):
            errs.append(f"Item #{k} of \"gates\" must be an object"); continue
        d = dict(d)
        cid = str(d.get("id") or f"g{k}")
        while cid in used: cid += "_"
        used.add(cid); d["id"] = cid
        try:
            circuit.components.append(ComponentRegistry.from_dict(d))
        except (ValueError, TypeError, KeyError) as e:
            errs.append(f"{cid}: {e}")
    w = raw.get("wires", {})
    if isinstance(w, dict):
        for net, segs in w.items():
            ok = isinstance(segs, list) and segs and all(isinstance(x, list) and len(x) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in x) for x in segs)
            if not ok: errs.append(f'"wires" > "{net}" must be a list of [x1, y1, x2, y2] pieces'); continue
            circuit.wires[str(net)] = [[int(round(v / 10.0)) * 10 for v in x] for x in segs]
    elif w: errs.append('"wires" must be an object like {"n1": [[x1, y1, x2, y2], ...]}')
    circuit.sync()
    return circuit, errs


def dumps(circuit, layout=False):
    """Readable JSON: one component per line. Layout (positions, wires, orientation) is left out unless layout=True."""
    q = json.dumps
    d = circuit.to_dict(layout)
    lines = ["{", f'  "inputs": {q(d["inputs"])},', f'  "outputs": {q(d["outputs"])},', '  "gates": [']
    for i, g in enumerate(d["gates"]):
        lines.append("    " + q(g) + ("," if i + 1 < len(d["gates"]) else ""))
    lines += ["  ]"]
    if d.get("wires"):
        lines[-1] += ","; lines.append('  "wires": {')
        items = list(d["wires"].items())
        for i, (k, v) in enumerate(items): lines.append("    " + q(k) + ": " + q(v) + ("," if i + 1 < len(items) else ""))
        lines.append("  }")
    lines += ["}"]
    return "\n".join(lines) + "\n"
