"""SPICE netlist (.cir / .sp / .net, as exported by Multisim and other simulators) -> analog circuit JSON."""
import math
import re

from ..analog import components as C
from ..analog.netlist import Netlist, dumps
from ..analog.units import parse_value

_NUM = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(meg|mil|t|g|k|m|u|n|p|f)?[a-z%Ωµ]*$", re.I)
KINDS = {"R": "Resistor", "C": "Capacitor", "L": "Inductor", "V": "VoltageSource", "I": "CurrentSource", "D": "Diode",
         "E": "VCVS", "G": "VCCS", "H": "CCVS", "F": "CCCS"}
NAMES = {"X": "sub-circuit / IC", "B": "behavioural source", "S": "voltage-controlled switch", "W": "current-controlled switch", "T": "transmission line", "U": "IC", "Y": "device"}
SOURCE_WORDS = ("sin", "pulse", "pwl", "exp", "sffm", "am", "ac")


def value_text(tok):
    """'4.7K', '10uF', '1Meg', '5V' -> '4.7k', '10u', '1meg', '5' (None if it is not a plain number)."""
    t = tok.strip().strip("{}'\"")
    m = _NUM.match(t)
    if not m: return None
    num, suf = m.group(1), (m.group(2) or "").lower()
    if suf == "mil": return "%g" % (float(num) * 25.4e-6)
    return num + suf


def node(n):
    n = n.strip()
    return "0" if n.lower() in ("0", "gnd", "ground", "gnd!", "agnd") else n


def _logical_lines(text):
    out = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip(): continue
        if line.lstrip().startswith("+") and out and not out[-1].startswith("*"): out[-1] += " " + line.lstrip()[1:]
        else: out.append(line.strip())
    return out


def _strip_comment(line):
    for sep in (";", " $"):
        if sep in line: line = line.split(sep, 1)[0]
    return line.strip()


def parse_spice(text):
    """Returns (Netlist, notes)."""
    lines = _logical_lines(text); notes = []; parts = []; title = ""; skipped = {}; cards = set(); ids = set()
    in_sub = False; first = True; models = _models(lines); sweep = None; ac = tran = None; ks = []
    for line in lines:
        if line.startswith("*"):
            if first and not title: title = line.lstrip("* ").strip()
            first = False; continue
        line = _strip_comment(line)
        if not line: continue
        toks = line.replace("=", " = ").split()
        head = toks[0]
        if head.startswith("."):
            card = head.lower()
            if card == ".dc" and len(toks) >= 5 and not in_sub: sweep = sweep or _dc(toks, notes)
            if card == ".ac" and len(toks) >= 5 and not in_sub: ac = ac or _ac(toks)
            if card == ".tran" and len(toks) >= 3 and not in_sub: tran = tran or _tran(toks)
            if card == ".subckt": in_sub = True; cards.add(card)
            elif card == ".ends": in_sub = False
            elif card not in (".end", ".model", ".op", ".title"): cards.add(card)
            if card == ".title" and len(toks) > 1: title = " ".join(toks[1:])
            first = False; continue
        if in_sub: continue
        letter = head[0].upper()
        if first and not (any(ch.isdigit() for ch in head) or len(head) <= 2):     # SPICE: the first line is the title
            title = line; first = False; continue
        if letter in "QMJ" and len(toks) >= 5:
            ok = _active(letter, toks, parts, notes, ids, models)
            if ok is None: skipped[head] = {"Q": "bipolar transistor", "M": "MOSFET", "J": "JFET"}[letter]
            first = False; continue
        if letter == "K" and len(toks) >= 4:
            try: ks.append((toks[1], toks[2], parse_value(value_text(toks[3]))))
            except (TypeError, ValueError): skipped[head] = "coupled inductors"
            first = False; continue
        if letter in KINDS and len(toks) >= 3:
            ok = _element(letter, toks, parts, notes, ids, models)
            if ok is False and first:       # first line that is not a usable element is the title (SPICE convention)
                title = line; first = False; continue
            if ok is None: skipped[head] = KINDS[letter]
            first = False; continue
        if first and not (letter in NAMES and len(toks) >= 3): title = line; first = False; continue
        first = False
        if letter in NAMES: skipped[head] = NAMES[letter]
        else: skipped[head] = "unknown element"
    if skipped:
        notes.append("Not imported (the Multisim workspace has only resistors, capacitors, inductors, diodes, Zener diodes, DC sources and linear controlled sources, so the result may be incomplete): " +
                     ", ".join(f"{k} ({v})" for k, v in list(skipped.items())[:12]) + (" ..." if len(skipped) > 12 else "") + ".")
    for l1, l2, k in ks: _couple(parts, l1, l2, k, notes)
    if sweep and any(q.id == sweep["part"] for q in parts): analysis = {"sweep": sweep}
    else:
        analysis = {}
        if sweep: notes.append(f".dc sweeps {sweep['part']}, which is not in the imported circuit, so the sweep was ignored.")
    cards.discard(".dc") if analysis else None
    if ac: analysis["ac"] = ac; cards.discard(".ac")
    if tran: analysis["tran"] = tran; cards.discard(".tran")
    cards = {c for c in cards if c not in (".param", ".options", ".option", ".global", ".temp", ".save", ".print", ".probe", ".plot", ".control", ".endc", ".lib", ".include", ".inc")} | \
            {c for c in cards if c in (".tran", ".ac", ".dc", ".noise", ".tf", ".four")}
    if cards & {".tran", ".ac", ".dc", ".noise", ".tf", ".four"}:
        notes.append("Analysis commands (" + ", ".join(sorted(cards & {".tran", ".ac", ".dc", ".noise", ".tf", ".four"})) + ") were ignored: this program has DC, DC sweep, AC and transient analysis only.")
    if ".subckt" in cards: notes.append("Sub-circuit definitions were skipped.")
    nl = Netlist(parts, title); nl.analysis = analysis
    return nl, notes


def _models(lines):
    """{model name (lower): {param: text}} from .model cards."""
    out = {}
    for ln in lines:
        t = _strip_comment(ln)
        if t.lower().startswith(".model"):
            toks = t.replace("(", " ").replace(")", " ").replace("=", " = ").split()
            if len(toks) >= 3:
                kv = {}; rest = toks[3:]
                for i, w in enumerate(rest):
                    if w == "=" and 0 < i < len(rest) - 1: kv[rest[i - 1].lower()] = rest[i + 1]
                out[toks[1].lower()] = {"type": toks[2].lower(), **kv}
    return out


def _par(m, *names):
    for n in names:
        if n in m and value_text(m[n]) is not None: return value_text(m[n])
    return None


def _active(letter, toks, parts, notes, ids, models):
    """Q (bipolar), M (MOSFET) and J (JFET) lines with their .model cards -> NPN / PNP / NMOS / PMOS / NJFET / PJFET."""
    name = toks[0]; n3 = [node(t) for t in toks[1:4]]; rest = toks[4:]
    mname = next((t for t in reversed(rest) if t.lower() in models), None); m = models.get(mname.lower(), {}) if mname else {}
    if not m: notes.append(f"{name}: no .model card was found, so default parameters are used.")
    kind = m.get("type", "")
    extra = {}
    if letter == "Q":
        cls = "PNP" if kind.startswith("pnp") else "NPN"
        for k, names in (("is", ("is",)), ("bf", ("bf",)), ("br", ("br",)), ("vaf", ("vaf", "va")), ("cbe", ("cje",)), ("cbc", ("cjc",))):
            v = _par(m, *names)
            if v is not None: extra[k] = v
        if "bf" not in extra and m: extra["bf"] = "100"
    elif letter == "M":
        cls = "PMOS" if kind.startswith("pmos") else "NMOS"
        if len(toks) > 4 and node(toks[4]) != n3[2]: notes.append(f"{name}: the body terminal is ignored (the body is tied to the source).")
        extra = {"vto": _par(m, "vto") or "0", "kp": _par(m, "kp") or "2e-5", "lambda": _par(m, "lambda") or "0"}
        if kind.startswith("pmos") and extra["vto"] == "0": pass
        wl = {}
        for i, t in enumerate(rest):
            if t.lower() in ("w", "l") and i + 2 < len(rest) and rest[i + 1] == "=": wl[t.lower()] = _num(rest[i + 2])
        if wl.get("w") and wl.get("l"): extra["kp"] = "%g" % (parse_value(extra["kp"]) * wl["w"] / wl["l"])
        for k, names in (("cgs", ("cgso",)), ("cgd", ("cgdo",))):
            v = _par(m, *names)
            if v is not None: extra[k] = "%g" % (parse_value(v) * wl.get("w", 1e-4))                 # CGSO / CGDO are farads per metre of channel width
        if int(float(m.get("level", "1") or 1)) != 1 if m.get("level", "1").replace(".", "").isdigit() else False: notes.append(f"{name}: only the level-1 MOSFET model is supported; the other parameters are ignored.")
    else:
        cls = "PJFET" if kind.startswith("pjf") else "NJFET"
        extra = {"vto": _par(m, "vto") or ("2" if cls == "PJFET" else "-2"), "beta": _par(m, "beta") or "1e-4", "lambda": _par(m, "lambda") or "0"}
        for k, names in (("is", ("is",)), ("cgs", ("cgs",)), ("cgd", ("cgd",))):
            v = _par(m, *names)
            if v is not None: extra[k] = v
    pid = name
    while pid in ids: pid += "_"
    ids.add(pid)
    try: parts.append(C.lookup(cls)(pid, n3, None, **extra))
    except Exception: return None
    return True


def _couple(parts, l1, l2, k, notes):
    """K L1 L2 k: two inductors that are coupled become one Transformer."""
    a = next((p for p in parts if p.id == l1 and isinstance(p, C.Inductor)), None); b = next((p for p in parts if p.id == l2 and isinstance(p, C.Inductor)), None)
    if a is None or b is None or not 0 < k < 1: notes.append(f"K {l1} {l2}: coupled inductors could not be imported (both must be inductors in this circuit, 0 < k < 1)."); return
    L1, L2 = a.number(), b.number(); tid = l1[1:-1] if (l1.startswith("L") and l1.endswith("p") and l2 == l1[:-1] + "s") else a.id + "_" + b.id        # what our own export wrote
    t = C.Transformer(tid, list(a.nodes) + list(b.nodes), "%g" % L1, ratio="%g" % math.sqrt(L2 / L1), k="%g" % k)
    i = parts.index(a); parts[i] = t; parts.remove(b)


def _ac(toks):
    """.ac dec|oct|lin N f1 f2"""
    try:
        kind, n = toks[1].lower(), int(float(toks[2])); f1, f2 = parse_value(value_text(toks[3])), parse_value(value_text(toks[4]))
        if f1 <= 0 or f2 <= f1: return None
        pts = n if kind == "lin" else int(round(n * (math.log2(f2 / f1) if kind == "oct" else math.log10(f2 / f1)))) + 1
        return {"from": value_text(toks[3]), "to": value_text(toks[4]), "points": max(2, min(2000, pts)), "scale": "lin" if kind == "lin" else "log"}
    except (TypeError, ValueError): return None


def _tran(toks):
    """.tran tstep tstop [...]"""
    try:
        dt, stop = parse_value(value_text(toks[1])), parse_value(value_text(toks[2]))
        if dt <= 0 or stop <= 0: return None
        return {"stop": value_text(toks[2]), "steps": max(2, min(200000, int(round(stop / dt))))}
    except (TypeError, ValueError): return None


def _dc(toks, notes):
    """.dc SRC start stop step  ->  the saved sweep (a second source on the line is ignored)."""
    try:
        a, b, st = parse_value(value_text(toks[2])), parse_value(value_text(toks[3])), parse_value(value_text(toks[4]))
        if st == 0: return None
        n = max(2, min(2000, int(round((b - a) / st)) + 1))
    except (TypeError, ValueError): return None
    if len(toks) > 5: notes.append("Only the first source of the .dc sweep was kept.")
    return {"part": toks[1], "from": value_text(toks[2]), "to": value_text(toks[3]), "points": n}


def _num(t):
    v = value_text(t) if t is not None else None
    return None if v is None else parse_value(v)


def _source(name, rest, notes):
    """V / I source tokens (DC, AC, SIN, PULSE) -> (value text, extras dict); (None, {}) if nothing usable."""
    toks = " ".join(rest).replace("(", " ( ").replace(")", " ) ").split(); low = [t.lower() for t in toks]
    dc, acm, acp, wave, extra = None, None, 0.0, None, {}
    i = 0
    while i < len(toks):
        w = low[i]
        if w == "dc" and i + 1 < len(toks): dc = value_text(toks[i + 1]); i += 2
        elif w == "ac" and i + 1 < len(toks):
            acm = _num(toks[i + 1]); i += 2
            if i < len(toks) and _num(toks[i]) is not None and low[i] not in ("dc", "ac"): acp = _num(toks[i]); i += 1
        elif w in ("sin", "pulse", "pwl", "exp", "sffm", "am"):
            j = i + 1; args = []
            if j < len(toks) and toks[j] == "(": j += 1
            while j < len(toks) and toks[j] != ")": args.append(toks[j]); j += 1
            wave = (w, args); i = j + 1
        elif i == 0 and dc is None and _num(toks[0]) is not None: dc = value_text(toks[0]); i += 1
        else: i += 1
    if wave:
        kind, a = wave; n = [_num(x) for x in a]
        g = lambda k, d=0.0: n[k] if k < len(n) and n[k] is not None else d
        if kind == "sin" and len(n) >= 3 and g(2) > 0:
            if dc is None: dc = "%g" % g(0)
            extra = {"ac": "%g" % g(1), "freq": "%g" % g(2), "phase": "%g" % g(5), "wave": "sine"}
            if g(3) or g(4): notes.append(f"{name}: the delay / damping of the SIN source was ignored.")
        elif kind == "pulse" and len(n) >= 7 and g(6) > 0:
            v1, v2, td, tr, tf, pw, per = g(0), g(1), g(2), g(3), g(4), g(5), g(6); off, amp = (v1 + v2) / 2, abs(v2 - v1) / 2; sgn = 1 if v2 >= v1 else -1
            if tr + tf <= 0.05 * per and abs(pw + (tr + tf) / 2 - per / 2) <= 0.05 * per:
                extra = {"ac": "%g" % (sgn * amp), "freq": "%g" % (1 / per), "phase": "%g" % (-360 * td / per), "wave": "square"}
                if dc is None: dc = "%g" % off
            elif pw <= 0.05 * per and abs(tr - per / 2) <= 0.05 * per and abs(tf - per / 2) <= 0.05 * per:
                extra = {"ac": "%g" % (sgn * amp), "freq": "%g" % (1 / per), "phase": "%g" % (-90 - 360 * td / per), "wave": "triangle"}
                if dc is None: dc = "%g" % off
            else:
                notes.append(f"{name}: this PULSE is not a square or triangle wave, so only its starting level {v1:g} is used (DC).")
                if dc is None: dc = "%g" % v1
        else:
            notes.append(f"{name}: a {kind.upper()} source is not supported; it is imported as its DC value.")
        if acm is not None and extra and abs(acm - abs(float(extra["ac"]))) > 1e-12: notes.append(f"{name}: the AC magnitude {acm:g} was replaced by the waveform amplitude.")
    elif acm is not None:
        extra = {"ac": "%g" % acm, "phase": "%g" % acp}
    if dc is None: dc = "0" if extra else None
    return dc, extra


def _element(letter, toks, parts, notes, ids, models=None):
    """True: added; None: skipped with a reason; False: line is not an element at all."""
    name = toks[0]; cls = C.lookup(KINDS[letter])
    extra = {}
    if letter == "D":
        if len(toks) < 3: return False
        a, k = node(toks[1]), node(toks[2]); value = None
        m = (models or {}).get(toks[3].lower()) if len(toks) > 3 else None
        if m and "bv" in m and value_text(m["bv"]) is not None: cls = C.lookup("Zener"); extra["vz"] = value_text(m["bv"])
    elif letter in "EG":
        if len(toks) < 6: return False
        a, k = node(toks[1]), node(toks[2]); extra["control"] = [node(toks[3]), node(toks[4])]; value = value_text(toks[5])
        if value is None: return None
    elif letter in "HF":
        if len(toks) < 5: return False
        a, k = node(toks[1]), node(toks[2]); extra["control"] = toks[3]; value = value_text(toks[4])
        if value is None: return None
    else:
        if len(toks) < 4: return False
        a, k = node(toks[1]), node(toks[2]); rest = [t for t in toks[3:] if t != "="]
        value = None
        if letter in "VI":
            value, extra = _source(name, rest, notes)
            if value is None: return None
        else:
            cand = [t for t in rest if value_text(t) is not None and not re.match(r"^(ic|temp|tc|m|l|w)$", t, re.I)]
            if not cand: return None
            value = value_text(cand[0])
            if letter == "R" and parse_value(value) == 0: notes.append(f"{name}: 0 ohm resistor skipped."); return None
    pid = name
    while pid in ids: pid += "_"
    ids.add(pid)
    try: parts.append(cls(pid, [a, k], value, **extra))
    except Exception: return None
    return True


def spice_to_json(text):
    nl, notes = parse_spice(text)
    if not nl.parts: raise ValueError("No resistors, capacitors, inductors, diodes or sources were found in this netlist.")
    return dumps(nl), notes
