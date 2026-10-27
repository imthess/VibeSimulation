"""Logisim-evolution ``.circ`` file -> circuit JSON (the reverse of export/logisim.py).

The file is XML: components at grid positions plus wire segments. We work out where every pin of every
component is, join pins and wires that touch into nets, give each net a name and rebuild the circuit.
Pin positions of gates come from measurements of Logisim-evolution 3.8 (all sizes, input counts and directions).
Every circuit of the project is read (sub-circuits become parts of the circuits that use them); parts that cannot be simulated yet are reported, not imported.
"""
import re
import xml.etree.ElementTree as ET

from ..components.registry import ComponentRegistry as R
from ..core import project as PRJ
from ..core.model import Circuit, IOPin
from ..core.serializer import dumps
from ..layout.routing import on_seg, touch
from .logisim_defaults import DEFAULTS

GATES = {"AND Gate", "OR Gate", "XOR Gate", "NAND Gate", "NOR Gate", "XNOR Gate", "NOT Gate", "Buffer"}
GATE_TYPE = {"AND Gate": "AND", "OR Gate": "OR", "XOR Gate": "XOR", "NAND Gate": "NAND", "NOR Gate": "NOR", "XNOR Gate": "XNOR", "NOT Gate": "NOT", "Buffer": "BUFFER"}
EXTRA_X = {"XOR Gate": 10, "NAND Gate": 10, "NOR Gate": 10, "XNOR Gate": 20}
_Y = {30: {2: [-10, 10], 3: [-10, 0, 10], 4: [-20, -10, 10, 20], 5: [-20, -10, 0, 10, 20]},
      50: {2: [-20, 20], 3: [-20, 0, 20], 4: [-20, -10, 10, 20], 5: [-20, -10, 0, 10, 20]},
      70: {2: [-20, 20], 3: [-30, 0, 30], 4: [-30, -10, 10, 30], 5: [-20, -10, 0, 10, 20]}}
IGNORED = {"LED", "Probe", "7-Segment Display", "Hex Digit Display", "Text", "RGB LED", "LED Bar"}


def _loc(s):
    m = re.match(r"\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _int(v, default=0):
    try: return int(str(v), 0)
    except (TypeError, ValueError): return default


def rot(p, facing):
    x, y = p
    return {"east": (x, y), "west": (-x, -y), "north": (y, -x), "south": (-y, x)}.get(facing, (x, y))


def gate_ys(size, n):
    if n in _Y.get(size, _Y[50]): return _Y.get(size, _Y[50])[n]
    return [(i - n // 2) * 10 for i in range(n)] if n % 2 else [i * 10 for i in range(-n // 2, 0)] + [i * 10 for i in range(1, n // 2 + 1)]


def gate_inputs(name, attrs):
    """Offsets of the input pins of a gate (relative to its location)."""
    facing = attrs.get("facing", "east")
    if name == "NOT Gate": pts = [(-_int(attrs.get("size"), 30), 0)]
    elif name == "Buffer": pts = [(-20, 0)]
    else:
        size = _int(attrs.get("size"), 50); n = max(2, _int(attrs.get("inputs"), 2))
        x = -(size + EXTRA_X.get(name, 0))
        pts = [(x, y) for y in gate_ys(size, n)]
    return [rot(p, facing) for p in pts]


def splitter_part_pos(i, k, appear, facing):
    x = 20 if facing != "west" else -20
    if appear == "center" or appear == "legacy": y = 10 * (i - k // 2)
    elif appear == "right": y = 10 * (i + 1) if facing != "west" else -10 * (k - i)
    else: y = -10 * (k - i) if facing != "west" else 10 * (i + 1)           # "left" is Logisim's default
    return (x, y)


class _Net:
    def __init__(self): self.par = {}

    def find(self, a):
        self.par.setdefault(a, a)
        while self.par[a] != a:
            self.par[a] = self.par[self.par[a]]; a = self.par[a]
        return a

    def join(self, a, b): self.par[self.find(a)] = self.find(b)


def _read(path_or_text):
    text = path_or_text
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"This is not a readable Logisim file ({e}).")
    if root.tag != "project": raise ValueError("This XML file is not a Logisim project (.circ).")
    circuits = {c.get("name"): c for c in root.findall("circuit")}
    if not circuits: raise ValueError("The file contains no circuit.")
    main = root.find("main")
    name = main.get("name") if main is not None and main.get("name") in circuits else next(iter(circuits))
    libs = {l.get("name"): l.get("desc", "") for l in root.findall("lib")}
    return circuits, name, libs


def _attr_inverse(cls, eff):
    """Settings of one of our components from Logisim attributes (defaults filled in)."""
    out = {}
    base = cls("x"); base_la = {k: str(v) for k, v in base.logisim_attrs().items()}
    for a in cls.attrs_spec:
        if a.kind == "map":
            from ..components.memory.rom import decode_contents
            d = decode_contents(str(eff.get(a.name, "")))
            if d: out[a.name] = d[2]
            continue
        if a.kind == "int":
            key = getattr(cls, "lkeys", {}).get(a.name, a.name)
            if key in eff:
                v = _int(eff[key], a.default)
                out[a.name] = max(a.lo, min(a.hi, v))
        elif a.kind in ("choice", "bool"):
            options = a.choices if a.kind == "choice" else (False, True)
            for ch in options:
                try:
                    v = cls("x"); v.set_attr(a.name, ch)
                except ValueError: continue
                la = {k: str(x) for k, x in v.logisim_attrs().items()}
                diff = {k: x for k, x in la.items() if base_la.get(k) != x}
                if not diff and ch == a.default: continue
                if diff and all(str(eff.get(k)) == x for k, x in diff.items()):
                    out[a.name] = ch; break
    return out


def _plan(ckt, libs):
    """What the pins of a circuit are called (the same names the importer gives them) and which appearance it has."""
    ins, outs, used = [], [], set()

    def unique(s):
        s = re.sub(r"\s+", "_", str(s).strip()) or "n"
        base, k = s, 1
        while s in used: k += 1; s = f"{base}_{k}"
        used.add(s); return s
    raw_in, raw_out = [], []
    for e in ckt.findall("comp"):
        if e.get("name") != "Pin": continue
        loc = _loc(e.get("loc"))
        if loc is None: continue
        a = {x.get("name"): (x.get("val") if x.get("val") is not None else (x.text or "")) for x in e.findall("a")}
        (raw_out if a.get("output", "false") == "true" else raw_in).append((loc[1], loc[0], a))
    for i, (_, _, a) in enumerate(sorted(raw_in, key=lambda t: t[:2])): ins.append((unique((a.get("label") or "").strip() or f"In{i + 1}"), max(1, _int(a.get("width"), 1))))
    for i, (_, _, a) in enumerate(sorted(raw_out, key=lambda t: t[:2])): outs.append((unique((a.get("label") or "").strip() or f"Out{i + 1}"), max(1, _int(a.get("width"), 1))))
    appear = next((x.get("val") for x in ckt.findall("a") if x.get("name") == "appearance"), "classic")
    return {"ins": ins, "outs": outs, "appearance": appear}


def _sub_offsets(plan, x, y, facing, wire_pts):
    """Pin offsets of a subcircuit part: Logisim's classic box is computed exactly; the newer box depends on text widths, so its width is
    taken from where the wires of the file actually end."""
    nin, nout = len(plan["ins"]), len(plan["outs"])
    if plan["appearance"] != "evolution" and plan["appearance"] != "custom":
        gi, go, _ = PRJ.classic_geometry(nin, nout); return gi, go
    cands = []
    for dy in (10, 20):
        for W in (range(60, 600, 10) if nout else [0]):
            gi = [(-W if nout else 0, dy * i) for i in range(nin)]
            go = [(0, dy * j) for j in range(nout)]
            cands.append((dy, W, gi, go))

    def score(c):
        return sum((x + q[0], y + q[1]) in wire_pts for q in (rot(p, facing) for p in c[2] + c[3]))
    best = min(cands, key=lambda c: (-score(c), (c[0] != 10) * 1000 + abs(c[1] - 100)))
    return best[2], best[3]


def parse_circ(text):
    """Returns (circuit, notes) from the text of a .circ file (the main circuit; use parse_project for all of them)."""
    circs, main, notes = parse_project(text)
    return circs[main], notes


def parse_project(text):
    """Returns ({name: Circuit}, main name, notes). Subcircuits used by other circuits come first, so they are known when needed."""
    circuits, main, libs = _read(text)
    plans = {n: _plan(c, libs) for n, c in circuits.items()}
    out, notes = {}, []
    for n, ckt in circuits.items():
        c, nts = _parse_one(ckt, libs, plans)
        out[n] = c
        notes += [(f"[circuit {n}] " if n != main and len(circuits) > 1 else "") + t for t in nts]
    for n, p in plans.items():
        if p["appearance"] == "custom": notes.append(f"Circuit '{n}' has a custom appearance: connections to its instances may be misplaced, so check them.")
    return out, main, notes


def _parse_one(ckt, libs, plans):
    notes = []
    wires = []
    for w in ckt.findall("wire"):
        a, b = _loc(w.get("from")), _loc(w.get("to"))
        if a and b: wires.append((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
    wire_pts = {(w[0], w[1]) for w in wires} | {(w[2], w[3]) for w in wires}
    comps, unsupported, ignored = [], {}, {}
    known = {cl.logisim_name for cl in R._classes.values()}
    for e in ckt.findall("comp"):
        name = e.get("name", ""); loc = _loc(e.get("loc"))
        if loc is None: continue
        attrs = {a.get("name"): (a.get("val") if a.get("val") is not None else (a.text or "")) for a in e.findall("a")}
        comps.append(dict(name=name, x=loc[0], y=loc[1], attrs=attrs, lib=libs.get(e.get("lib", ""), ""), haslib=e.get("lib") is not None))
    nets = _Net()
    for i, w in enumerate(wires): nets.find(("w", i))
    for i in range(len(wires)):
        for j in range(i):
            if touch(wires[i], wires[j]): nets.join(("w", i), ("w", j))
    ends_at = {}

    def add_end(rec, pos, **info):
        node = ("e", len(rec["ends"]), id(rec)); e = dict(pos=pos, node=node, **info); rec["ends"].append(e)
        for i, w in enumerate(wires):
            if on_seg(w, pos): nets.join(node, ("w", i))
        key = ends_at.setdefault(pos, node); nets.join(node, key)
        return e

    pins_in, pins_out, tunnels = [], [], []
    live = []
    for c in comps:
        n = c["name"]; c["ends"] = []; x, y = c["x"], c["y"]
        eff = dict(DEFAULTS.get(n, {})); eff.update(c["attrs"]); c["eff"] = eff
        facing = c["attrs"].get("facing", "east")
        if n == "Pin":
            c["is_out"] = c["attrs"].get("output", "false") == "true"
            add_end(c, (x, y), kind="pin"); (pins_out if c["is_out"] else pins_in).append(c); live.append(c)
        elif n == "Button":                  # a button is a switch you press: here, an input that is 1 while "pressed"
            c["is_out"] = False; add_end(c, (x, y), kind="pin"); pins_in.append(c); live.append(c)
            c["eff"]["width"] = "1"; ignored["Button (imported as an input pin)"] = ignored.get("Button (imported as an input pin)", 0) + 1
        elif n == "Tunnel":
            add_end(c, (x, y), kind="tunnel"); tunnels.append(c); live.append(c)
        elif n in GATES:
            ys = gate_inputs(n, c["attrs"])
            add_end(c, (x, y), kind="out", port="Out")
            for k, p in enumerate(ys): add_end(c, (x + p[0], y + p[1]), kind="in", port=f"In{k + 1}")
            live.append(c)
        elif n == "Splitter":
            k = max(1, _int(eff.get("fanout"), 2)); incoming = max(1, _int(eff.get("incoming"), 2))
            appear = c["attrs"].get("appear", "left")
            if facing not in ("east", "west"):
                unsupported[n + f" facing {facing}"] = unsupported.get(n + f" facing {facing}", 0) + 1; continue
            bits = []
            for b in range(incoming):
                v = c["attrs"].get(f"bit{b}")
                bits.append(_int(v, b * k // incoming) if v not in (None, "none") else -1)
            widths = [bits.count(i) for i in range(k)]
            seq = [b for b in bits if b >= 0]
            if any(w == 0 for w in widths) or seq != sorted(seq) or len(seq) != incoming:
                unsupported["Splitter with an unusual bit order or unused bits"] = unsupported.get("Splitter with an unusual bit order or unused bits", 0) + 1; continue
            c["widths"] = widths
            add_end(c, (x, y), kind="bus")
            for i in range(k):
                p = splitter_part_pos(i, k, appear, facing); add_end(c, (x + p[0], y + p[1]), kind="part", index=i)
            live.append(c)
        elif n in plans and not c["haslib"]:                 # another circuit of the project, used as a part
            pl = plans[n]; gi, go = _sub_offsets(pl, x, y, facing, wire_pts)
            comp = R.create("Circuit", f"c{len(live)}", {"circuit": n}); comp.facing = facing if facing in ("east", "west", "north", "south") else "east"
            c["comp"] = comp
            for (pn, _), q in zip(pl["ins"], gi): p = rot(q, facing); add_end(c, (x + p[0], y + p[1]), kind="in", port=pn)
            for (pn, _), q in zip(pl["outs"], go): p = rot(q, facing); add_end(c, (x + p[0], y + p[1]), kind="out", port=pn)
            live.append(c)
        elif n in IGNORED:
            ignored[n] = ignored.get(n, 0) + 1
        elif n not in known:
            unsupported[n] = unsupported.get(n, 0) + 1
        else:
            cls = next(cl for cl in R._classes.values() if cl.logisim_name == n and cl.type_name != "Combiner")
            if n == "RAM":
                why = ("a bidirectional data bus" if str(eff.get("databus")) == "bidir" else "separate data pins with an output enable (controlled)" if str(eff.get("databus")) == "bibusControlled" else
                       "line enables" if str(eff.get("enables")) == "line" else "byte enables" if str(eff.get("byteenables")) == "byteEnables" and _int(eff.get("dataWidth"), 8) > 8 else "")
                if why:
                    unsupported[f"RAM with {why}"] = unsupported.get(f"RAM with {why}", 0) + 1; continue
            if facing != "east" and n not in ("Power", "Ground", "Constant", "Clock"):
                unsupported[f"{n} facing {facing}"] = unsupported.get(f"{n} facing {facing}", 0) + 1; continue
            try: comp = cls(f"c{len(live)}", _attr_inverse(cls, eff))
            except ValueError as e:
                unsupported[f"{n} ({e})"] = 1; continue
            if n == "Counter" and "max" not in c["attrs"]: comp.attrs["max"] = 0          # (Logisim's default maximum follows the width)
            if n == "Clock": comp.facing = facing                                    # same rotation as Logisim
            c["cls"], c["comp"] = cls, comp
            evo = comp.evolution_ports() if getattr(comp, "sequential", False) and str(eff.get("appearance", "logisim_evolution")) != "classic" else None
            for p in comp.all_ports():
                if p.name == "En" and str(eff.get("enable", "false")) != "true" and not getattr(comp, "sequential", False): continue
                dx, dy = (p.dx, p.dy)
                if evo is not None:
                    if p.name not in evo: continue          # this pin does not exist in that look
                    dx, dy = evo[p.name]
                add_end(c, (x + dx, y + dy), kind=p.direction, port=p.name)
            live.append(c)

    # ---- nets: members per root; tunnels with the same label join
    labels = {}
    for t in tunnels:
        lab = (t["attrs"].get("label") or "").strip()
        if lab: labels.setdefault(lab, []).append(t["ends"][0]["node"])
    for nodes in labels.values():
        for nd in nodes[1:]: nets.join(nodes[0], nd)
    members = {}
    for c in live:
        for e in c["ends"]: members.setdefault(nets.find(e["node"]), []).append((c, e))
    wired = {nets.find(("w", i)) for i in range(len(wires))}

    # ---- drivers; splitters work in whichever direction the wiring implies
    driven = set()
    for c in live:
        if c["name"] in ("Pin", "Button") and not c["is_out"]: driven.add(nets.find(c["ends"][0]["node"]))
        elif c["name"] in GATES or "comp" in c:
            for e in c["ends"]:
                if e["kind"] == "out": driven.add(nets.find(e["node"]))
    splits = [c for c in live if c["name"] == "Splitter"]
    for c in splits: c["dir"] = None
    changed = True
    while changed:
        changed = False
        for c in splits:
            if c["dir"]: continue
            bus = next(e for e in c["ends"] if e["kind"] == "bus"); parts = [e for e in c["ends"] if e["kind"] == "part"]
            if nets.find(bus["node"]) in driven:
                c["dir"] = "split"; driven.update(nets.find(e["node"]) for e in parts); changed = True
            elif any(nets.find(e["node"]) in driven for e in parts):
                c["dir"] = "join"; driven.add(nets.find(bus["node"])); changed = True
    for c in splits:
        if not c["dir"]: c["dir"] = "split"

    # ---- names
    names, used = {}, set()

    def unique(s):
        s = re.sub(r"\s+", "_", str(s).strip()) or "n"
        base, k = s, 1
        while s in used: k += 1; s = f"{base}_{k}"
        used.add(s); return s

    in_label, out_label = {}, {}
    for i, c in enumerate(sorted(pins_in, key=lambda c: (c["y"], c["x"]))):
        lab = (c["attrs"].get("label") or "").strip() or f"In{i + 1}"
        c["name_"] = unique(lab); names[nets.find(c["ends"][0]["node"])] = names.get(nets.find(c["ends"][0]["node"]), c["name_"])
    extra_out = []
    for i, c in enumerate(sorted(pins_out, key=lambda c: (c["y"], c["x"]))):
        lab = (c["attrs"].get("label") or "").strip() or f"Out{i + 1}"
        root = nets.find(c["ends"][0]["node"])
        if root in names:
            c["name_"] = unique(lab); extra_out.append((names[root], c["name_"], c))       # same wire as an input or another output: needs a buffer
        else:
            c["name_"] = unique(lab); names[root] = c["name_"]
    counter = [0]

    def net_name(node):
        root = nets.find(node)
        if root not in names: counter[0] += 1; names[root] = unique(f"n{counter[0]}")
        return names[root]

    def connected(node):
        root = nets.find(node)
        return root in wired or len(members.get(root, [])) > 1

    # ---- components
    circuit = Circuit(); k_gate = k_other = 0
    for c in sorted(pins_in, key=lambda c: (c["y"], c["x"])): circuit.inputs.append(IOPin(c["name_"], max(1, _int(c["eff"].get("width"), 1))))
    for c in sorted(pins_out, key=lambda c: (c["y"], c["x"])): circuit.outputs.append(IOPin(c["name_"], max(1, _int(c["eff"].get("width"), 1))))
    ids = set()

    def cid(prefix, label=""):
        nonlocal k_gate, k_other
        lab = re.sub(r"\s+", "_", (label or "").strip())
        if lab and lab not in ids and lab not in used:
            ids.add(lab); return lab
        while True:
            if prefix == "g": k_gate += 1; s = f"g{k_gate}"
            else: k_other += 1; s = f"u{k_other}"
            if s not in ids: ids.add(s); return s

    for c in sorted(live, key=lambda c: (c["x"], c["y"])):
        n = c["name"]; eff = c["eff"]
        if n in GATES:
            ins_pos = [e for e in c["ends"] if e["kind"] == "in"]; out_e = next(e for e in c["ends"] if e["kind"] == "out")
            single = n in ("NOT Gate", "Buffer")
            attrs = {"width": max(1, _int(eff.get("width"), 1))}
            if not single: attrs["inputs"] = len(ins_pos)
            if n in ("XOR Gate", "XNOR Gate") and len(ins_pos) > 2 and str(eff.get("xor", "1")) not in ("odd",):
                notes.append(f"{n} with {len(ins_pos)} inputs is set to 'exactly one' in Logisim; it was imported as odd parity, so check its results.")
            g = R.create(GATE_TYPE[n], cid("g", c["attrs"].get("label")), attrs)
            sigs = {}
            for k, e in enumerate(sorted(ins_pos, key=lambda e: (e["pos"][1], e["pos"][0]))):
                if not connected(e["node"]): continue
                sig = net_name(e["node"])
                if not single and str(eff.get(f"negate{k}", "false")) == "true":
                    inv = R.create("NOT", cid("g"), {"width": attrs["width"]}, {"In1": sig}, {"Out": unique(f"{sig}_inv")})
                    circuit.components.append(inv); sig = inv.outs["Out"]
                sigs[f"In{k + 1}"] = sig
            g.ins = sigs
            if connected(out_e["node"]): g.outs = {"Out": net_name(out_e["node"])}
            circuit.components.append(g)
        elif n == "Splitter":
            bus = next(e for e in c["ends"] if e["kind"] == "bus"); parts = sorted([e for e in c["ends"] if e["kind"] == "part"], key=lambda e: e["index"])
            comp = R.create("Splitter" if c["dir"] == "split" else "Combiner", cid("u"), {"widths": c["widths"]})
            if c["dir"] == "split":
                if connected(bus["node"]): comp.ins = {"In": net_name(bus["node"])}
                comp.outs = {f"Out{e['index']}": net_name(e["node"]) for e in parts if connected(e["node"])}
            else:
                comp.ins = {f"In{e['index']}": net_name(e["node"]) for e in parts if connected(e["node"])}
                if connected(bus["node"]): comp.outs = {"Out": net_name(bus["node"])}
            circuit.components.append(comp)
        elif "comp" in c:
            comp = c["comp"]; comp.id = cid("u", c["attrs"].get("label"))
            comp.ins, comp.outs = {}, {}
            for e in c["ends"]:
                if not connected(e["node"]): continue
                (comp.ins if e["kind"] == "in" else comp.outs)[e["port"]] = net_name(e["node"])
            circuit.components.append(comp)
    for src, dst, c in extra_out:
        circuit.components.append(R.create("BUFFER", cid("g"), {"width": 1}, {"In1": src}, {"Out": dst}))
    circuit.sync()
    if ignored: notes.append("Ignored (they do not change the logic): " + ", ".join(f"{v} x {k}" for k, v in ignored.items()) + ".")
    if unsupported: notes.append("Not imported (not supported yet, so the circuit may be incomplete): " + ", ".join(f"{k}" + (f" x{v}" if v > 1 else "") for k, v in unsupported.items()) + ".")
    return circuit, notes


def circ_to_json(text):
    """JSON text of the file: one circuit's JSON, or {"main": ..., "circuits": {...}} if the project has several."""
    import json
    circs, main, notes = parse_project(text)
    if len(circs) == 1: return dumps(circs[main]), notes
    body = ",\n".join(f'    {json.dumps(n)}: ' + dumps(c).rstrip("\n").replace("\n", "\n    ") for n, c in circs.items())
    return '{\n  "main": ' + json.dumps(main) + ',\n  "circuits": {\n' + body + "\n  }\n}\n", notes
