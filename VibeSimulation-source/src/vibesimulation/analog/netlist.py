"""The analog circuit: parsing, validation, JSON writing, solving, SPICE export."""
import json
import math

from . import components as C
from .solver import SolveError, is_ground, solve


class Netlist:
    def __init__(self, parts=None, title=""):
        self.parts, self.title = parts or [], title
        self.wires = {}            # net -> [[x1, y1, x2, y2], ...]: routes the user drew by hand
        self.analysis = {}         # saved analysis settings, e.g. {"sweep": {"part": "V1", "from": 0, "to": 10, "points": 21}} (written to the JSON)

    def copy(self):
        n = Netlist([p.clone() for p in self.parts], self.title); n.analysis = json.loads(json.dumps(self.analysis)); n.wires = {k: [list(x) for x in v] for k, v in self.wires.items()}; return n

    @staticmethod
    def _dup(p):
        """A copy of a part for an analysis, at the current temperature (see thermal.use)."""
        from . import thermal
        return thermal.adjust(p.clone())

    def part(self, cid): return next((p for p in self.parts if p.id == cid), None)

    def merge_nets(self, a, b):
        """A wire drawn between net a and net b makes them one net (ground wins, then the plainer name). Returns the name they now share."""
        def canon(n): return "0" if is_ground(n) else str(n).strip()
        a, b = canon(a), canon(b)
        if a == b: return a
        keep, gone = (a, b) if (b != "0" and (a == "0" or (b.startswith("~") and not a.startswith("~")) or (a.startswith("~") == b.startswith("~") and a <= b))) else (b, a)
        for p in self.parts:
            p.nodes = [keep if canon(n) == gone else n for n in p.nodes]
            ctl = p.extra.get("control") if hasattr(p, "extra") else None
            if isinstance(ctl, list): p.extra["control"] = [keep if canon(n) == gone else n for n in ctl]
        if gone in self.wires:
            self.wires[keep] = self.wires.get(keep, []) + self.wires.pop(gone)
        return keep

    def floating(self):
        """[(part, terminal index)] for every terminal left unplugged (a net called '~<part>.<pin>'): the circuit is not complete while there are any."""
        return [(p, k) for p in self.parts for k, n in enumerate(p.nodes) if str(n).strip().startswith("~")]

    def tidy_floating(self):
        """Editing leaves terminals unplugged: a net that only one terminal uses is renamed '~<part>.<pin>' (a floating pin, allowed like in Multisim),
        and a '~' net that two terminals share again gets an ordinary name. Hand-made routes of nets that no longer exist are dropped."""
        def canon(n): return "0" if is_ground(n) else str(n).strip()
        def count():
            cnt = {}
            for p in self.parts:
                for n in list(p.nodes) + list(p.control_nodes()): cnt[canon(n)] = cnt.get(canon(n), 0) + 1
            return cnt
        cnt = count()
        for p in self.parts:
            for k, n in enumerate(p.nodes):
                c = canon(n)
                if c != "0" and cnt[c] == 1 and not c.startswith("~"):
                    p.nodes[k] = f"~{p.id}.{k + 1}"
                    if c in self.wires: self.wires[p.nodes[k]] = self.wires.pop(c)             # a dangling wire stays with its terminal
        cnt = count(); used = set(cnt); fresh = {}
        for c, n in sorted(cnt.items()):
            if c.startswith("~") and n >= 2:
                i = 1
                while f"n{i}" in used or f"n{i}" in fresh.values(): i += 1
                fresh[c] = f"n{i}"
        for p in self.parts:
            for k, n in enumerate(p.nodes):
                if canon(n) in fresh: p.nodes[k] = fresh[canon(n)]
        for old, new in fresh.items():
            if old in self.wires: self.wires[new] = self.wires.pop(old)
        live = {canon(n) for p in self.parts for n in p.nodes}
        self.wires = {k: v for k, v in self.wires.items() if k in live}
        return self

    def nets(self): return sorted({str(n) for p in self.parts for n in p.nodes if not is_ground(n)})

    def validate(self):
        errs, seen = [], set()
        if not self.parts: errs.append("Add at least one part.")
        for p in self.parts:
            if p.id in seen: errs.append(f"Two parts are called '{p.id}'.")
            seen.add(p.id); errs += p.check()
            if p.nterm == 2 and len(p.nodes) == 2 and str(p.nodes[0]).strip() == str(p.nodes[1]).strip(): errs.append(f"{p.id}: both ends are on the same node ({p.nodes[0]}), so it does nothing")
            elif p.nterm == 2 and len(p.nodes) == 2 and is_ground(p.nodes[0]) and is_ground(p.nodes[1]): errs.append(f"{p.id}: both ends are ground")
        if self.parts and not any(is_ground(n) for p in self.parts for n in p.nodes):
            errs.append('No ground: connect one node to "0" (or "GND").')
        errs += self.control_errors()
        if not errs: errs += self.connectivity()
        return errs

    def control_errors(self):
        errs, ids = [], {p.id: p for p in self.parts}
        used = {("0" if is_ground(n) else str(n).strip()) for p in self.parts for n in p.nodes}
        for p in self.parts:
            if getattr(p, "current_controlled", False):
                c = ids.get(str(p.extra["control"]).strip())
                if c is None: errs.append(f"{p.id}: control '{p.extra['control']}' is not a part of this circuit")
                elif not c.branch or c is p or c.nterm != 2: errs.append(f"{p.id}: control '{c.id}' must be a voltage source, ammeter, inductor or voltage-controlled/current-controlled voltage source (its current is what controls {p.id})")
            else:
                for n in p.control_nodes():
                    if ("0" if is_ground(n) else n) not in used: errs.append(f"{p.id}: control node '{n}' is not used by any part")
        return errs

    def connectivity(self):
        """Wiring checks: every net must join at least two terminals, and every net needs a DC path to ground."""
        def canon(n): return "0" if is_ground(n) else str(n).strip()
        errs, ends = [], {}
        for p in self.parts:
            for n in p.nodes: ends.setdefault(canon(n), []).append(p.id)
            for n in p.control_nodes(): ends.setdefault(canon(n), []).append(p.id + " (control)")
        for net, owners in sorted(ends.items()):
            if net != "0" and len(owners) == 1 and not net.startswith("~"):      # "~..." = a terminal left unplugged by the editor (Multisim allows floating pins)
                errs.append(f"Net '{net}' is wired to only one terminal ({owners[0]}). Connect it to another part, or to ground (0).")
        # DC path to ground: capacitors and current sources do not give one
        parent = {}
        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for p in self.parts:
            for n in p.nodes: find(canon(n))
            if p.nterm == 2 and p.conducts(): parent[find(canon(p.nodes[0]))] = find(canon(p.nodes[1]))
            elif p.nterm != 2:
                for a, b in p.dc_links(): parent[find(canon(a))] = find(canon(b))
        g = find("0")
        for net in sorted(ends):
            if find(net) != g and not net.startswith("~") and not any(f"'{net}'" in e for e in errs):
                errs.append(f"Net '{net}' has no DC path to ground (only capacitors or current sources touch it), so its voltage is undefined.")
        return errs

    def solve(self):
        from . import thermal
        thermal.use(self); parts = [self._dup(p) for p in self.parts]
        return solve(parts)

    def to_dict(self, layout=False):
        d = {"title": self.title} if self.title else {}
        d["components"] = [p.to_dict(layout) for p in self.parts]
        if self.analysis: d["analysis"] = self.analysis
        if layout and self.wires: d["wires"] = {k: [list(x) for x in v] for k, v in self.wires.items()}
        return d


def extract_state(nl):
    return {"pos": {p.id: [int(p.pos[0]), int(p.pos[1])] for p in nl.parts if p.pos and tuple(p.pos) != (0, 0)},
            "wires": {k: [list(x) for x in v] for k, v in nl.wires.items()}}


def apply_state(nl, st):
    st = st or {}
    for p in nl.parts:
        v = st.get("pos", {}).get(p.id)
        if v: p.pos = (int(v[0]), int(v[1]))
    nets = set(nl.nets()) | {"0"}          # the ground wire counts too
    nl.wires = {k: [list(x) for x in v] for k, v in st.get("wires", {}).items() if k in nets}
    return nl


def dumps(nl, layout=False):
    lines = ["{"]
    if nl.title: lines.append(f'  "title": {json.dumps(nl.title)},')
    lines.append('  "components": [')
    lines.append(",\n".join("    " + json.dumps(p.to_dict(layout)) for p in nl.parts))
    lines.append("  ]")
    if nl.analysis: lines[-1] += ","; lines.append('  "analysis": ' + json.dumps(nl.analysis))
    if layout and nl.wires:
        lines[-1] += ","; lines.append('  "wires": {')
        items = list(nl.wires.items())
        for i, (k, v) in enumerate(items): lines.append("    " + json.dumps(k) + ": " + json.dumps(v) + ("," if i + 1 < len(items) else ""))
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def parse(text):
    try: raw = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError as e: return None, [f"Not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})"]
    if not isinstance(raw, dict) or not isinstance(raw.get("components"), list):
        return None, ['The JSON must look like {"components": [{"id": "R1", "type": "Resistor", "value": "1k", "nodes": ["n1", "0"]}, ...]}']
    parts, errs = [], []
    for i, d in enumerate(raw["components"]):
        if not isinstance(d, dict): errs.append(f"Component {i + 1} must be an object."); continue
        cls = C.lookup(d.get("type", ""))
        cid = str(d.get("id") or f"P{i + 1}")
        if cls is None:
            errs.append(f"{cid}: unknown type '{d.get('type')}'. Known: {', '.join(c.type_name for c in C.part_types())}"); continue
        part = cls(cid, d.get("nodes", []), d.get("value"), **{k: d[k] for k in cls.extras if k in d})
        pos = d.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2 and all(isinstance(v, (int, float)) for v in pos): part.pos = (int(pos[0]), int(pos[1]))
        parts.append(part)
    nl = Netlist(parts, str(raw.get("title", "")))
    an = raw.get("analysis")
    if isinstance(an, dict): nl.analysis = an
    elif an is not None: errs.append('"analysis" must be an object like {"sweep": {"part": "V1", "from": 0, "to": 10, "points": 21}}')
    w = raw.get("wires", {})
    if isinstance(w, dict):
        for net, segs in w.items():
            if isinstance(segs, list) and segs and all(isinstance(x, list) and len(x) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in x) for x in segs):
                nl.wires[str(net)] = [[int(round(v)) for v in x] for x in segs]
            else: errs.append(f'"wires" > "{net}" must be a list of [x1, y1, x2, y2] pieces')
    elif w: errs.append('"wires" must be an object like {"n1": [[x1, y1, x2, y2], ...]}')
    return (None if errs else nl), errs


def to_spice(nl):
    name = nl.title or "VibeSimulation circuit"
    out = [f"* {name}", "* Import into Multisim: File > Import > From SPICE netlist (or use any SPICE simulator)"]
    def node(n): return "0" if is_ground(n) else "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(n))
    from . import solver as _s
    parts = [p.clone() for p in nl.parts]
    try: _s._wire_controls(parts)
    except _s.SolveError: pass
    for p in parts:
        for att in ("ctrl_spice",):
            if not hasattr(p, att) and getattr(p, "current_controlled", False): p.ctrl_spice = str(p.extra["control"])
        if p.nterm != 2: out += p.spice_lines(node); continue
        line = p.spice(node(p.nodes[0]), node(p.nodes[1]))
        if hasattr(p, "ctrl_nodes") and p.control_nodes() and "{" not in line: line = line.replace(" ".join(p.control_nodes()), " ".join(node(n) for n in p.control_nodes()))
        out.append(line)
    models = list(dict.fromkeys(p.model() for p in parts if hasattr(p, "model")))
    out += models
    sw = nl.analysis.get("sweep") if isinstance(nl.analysis, dict) else None
    out.append(".op")
    if isinstance(sw, dict) and sw.get("part"):
        try:
            from .units import parse_value
            a0, a1, n = parse_value(sw.get("from", 0)), parse_value(sw.get("to", 1)), max(2, int(sw.get("points", 11)))
            sp = next((p for p in parts if p.id == sw["part"]), None)
            if sp is not None: out.append(f".dc {sp.spice_name()} {a0:g} {a1:g} {(a1 - a0) / (n - 1):g}")
        except (TypeError, ValueError): pass
    ac = nl.analysis.get("ac") if isinstance(nl.analysis, dict) else None
    if isinstance(ac, dict) and ac.get("from") and ac.get("to"):
        try:
            from .units import parse_value
            f1, f2, n = parse_value(ac["from"]), parse_value(ac["to"]), max(2, int(ac.get("points", 100)))
            if str(ac.get("scale", "log")) == "lin": out.append(f".ac lin {n} {f1:g} {f2:g}")
            else: out.append(f".ac dec {max(1, round((n - 1) / math.log10(f2 / f1))) if f2 > f1 > 0 else 10} {f1:g} {f2:g}")
        except (TypeError, ValueError): pass
    tr = nl.analysis.get("tran") if isinstance(nl.analysis, dict) else None
    if isinstance(tr, dict) and tr.get("stop"):
        try:
            from .units import parse_value
            ts, n = parse_value(tr["stop"]), max(2, int(tr.get("steps", 1000))); out.append(f".tran {ts / n:g} {ts:g}")
        except (TypeError, ValueError): pass
    out += [".end"]
    return "\n".join(out) + "\n"
