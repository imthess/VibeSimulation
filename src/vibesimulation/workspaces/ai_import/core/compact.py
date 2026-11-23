"""A short answer format for circuits: the AI writes a few short lines instead of JSON, which saves answer tokens (a circuit is often 40% smaller).
``to_json_text`` turns such an answer into the JSON the rest of the program reads; real JSON passes through unchanged, so a model that ignores
the short format still works.

Logic circuit:                         Analog circuit:
    D                                      A  Voltage divider
    in A B                                 V1 VoltageSource 5 n1 0
    out Y                                  R1 Resistor 1k n1 n2
    g1 NAND A B > n1                       R2 Resistor 2k n2 0
    g2 NOT n1 > Y                          D1 Diode n2 0 vz=5.1
Anything the short format cannot say (buses, blocks with named pins) stays JSON."""
import json

GATES = ("AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR")

FORMAT_HELP = """ANSWER FORMAT: do not write JSON. Write short lines, no other text:
- First line: D for a logic circuit, or A followed by a title for an analog circuit.
- Logic: "in A B C" (inputs), "out Y" (outputs), then one line per gate: id TYPE inputs... > output   e.g.  g1 NAND A B > n1
  (gate types as listed above; for a bus input or a block with named pins write the whole answer as JSON instead).
- Analog: one line per part: id Type value node1 node2 [key=value ...]   (leave the value out for parts without one; the ground node is 0)
  e.g.  R1 Resistor 1k n1 n2     V1 VoltageSource 5 n1 0 ac=2 freq=1k     Q1 NPN n1 n2 0     Z1 Zener n2 0 vz=5.1
  Three- and four-node parts list all their nodes in the order given in the rules."""

_NO_VALUE = {"Diode", "Zener", "LED", "Ammeter", "Voltmeter", "NPN", "PNP", "NMOS", "PMOS", "NJFET", "PJFET", "IGBT", "OpAmp", "Transformer", "Switch"}


def looks_compact(text):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip() and not l.strip().startswith("```")]
    return bool(lines) and lines[0][:1] in "DA" and (lines[0] == "D" or lines[0].upper().startswith(("A ", "D ")) or lines[0] == "A") and not text.lstrip().startswith(("{", "["))


def _digital(lines):
    ins, outs, gates = [], [], []
    for l in lines:
        t = l.split()
        if t[0] == "in": ins += t[1:]
        elif t[0] == "out": outs += t[1:]
        else:
            if ">" not in t or len(t) < 5: raise ValueError(f"cannot read the line: {l}")
            i = t.index(">"); ins_ = t[2:i]; out = t[i + 1]
            gates.append({"id": t[0], "type": t[1].upper(), "in": ins_, "out": out})
    return {"kind": "digital", "inputs": ins, "outputs": outs, "gates": gates}


def _num(v):
    try: float(v); return True
    except ValueError: return False


def _analog(lines, title):
    comps = []
    for l in lines:
        t = l.split(); extra = {}
        base = []
        for w in t:
            if "=" in w: k, v = w.split("=", 1); extra[k] = v
            else: base.append(w)
        if len(base) < 4: raise ValueError(f"cannot read the line: {l}")
        cid, typ, rest = base[0], base[1], base[2:]
        value = None
        if typ not in _NO_VALUE and len(rest) >= 3: value, rest = rest[0], rest[1:]
        elif typ in ("Switch",) and rest and rest[0] in ("open", "closed"): extra.setdefault("state", rest[0]); rest = rest[1:]
        c = {"id": cid, "type": typ}
        if value is not None: c["value"] = value
        c["nodes"] = rest
        for k, v in extra.items(): c[k] = float(v) if k in ("ac", "freq", "phase") and _num(v) else v
        comps.append(c)
    d = {"kind": "analog", "components": comps}
    if title: d["title"] = title
    return d


def parse(text):
    """The circuit dict for a short-format answer (ValueError when it cannot be read)."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip() and not l.strip().startswith("```")]
    head = lines[0]
    if head == "D" or head.startswith("D "): return _digital(lines[1:])
    if head == "A" or head.startswith("A "): return _analog(lines[1:], head[1:].strip())
    raise ValueError("not the short format")


def to_json_text(text):
    """JSON text for the answer: JSON stays as it is; a short-format answer is converted; on any problem the text is returned unchanged."""
    if not text or not looks_compact(text): return text
    try: return json.dumps(parse(text))
    except (ValueError, IndexError): return text
