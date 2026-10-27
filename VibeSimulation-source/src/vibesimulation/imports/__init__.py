"""Open circuit files made in other programs (Logisim .circ, SPICE netlists exported from Multisim, our own JSON)."""
import json
import os

from ..analog.netlist import dumps as adumps, parse as aparse
from ..core.serializer import dumps, parse

MULTISIM_NATIVE = (".ms14", ".ms13", ".ms12", ".ms11", ".ms10", ".ms9", ".ms8", ".msm", ".ewprj")
LOGISIM_EXT = (".circ",)
SPICE_EXT = (".cir", ".sp", ".net", ".spice", ".ckt", ".cki", ".txt")


def classify(raw):
    """'digital' (Logisim), 'analog' (Multisim) or None, from circuit JSON."""
    if not isinstance(raw, dict): return None
    k = str(raw.get("kind", "")).lower()
    if k in ("analog", "multisim", "spice"): return "analog"
    if k in ("digital", "logic", "logisim"): return "digital"
    comps = raw.get("components")
    if isinstance(comps, list) and comps and all(isinstance(c, dict) and "nodes" in c for c in comps): return "analog"
    if isinstance(raw.get("circuits"), dict): return "digital"
    if "gates" in raw or "inputs" in raw or "outputs" in raw or isinstance(comps, list): return "digital"
    return None


def load_file(path):
    """Read a circuit file. Returns (kind, json_text, notes) with kind 'digital' or 'analog'; raises ValueError with a plain-language message."""
    ext = os.path.splitext(path)[1].lower(); name = os.path.basename(path)
    if os.path.getsize(path) > 30_000_000: raise ValueError("This file is too large to be a circuit.")
    data = open(path, "rb").read()
    if ext in MULTISIM_NATIVE or data[:2] == b"PK" or data[:4] == b"\xd0\xcf\x11\xe0" or b"\x00" in data[:2000]:
        raise ValueError(f"{name} is in Multisim's own file format, which is closed and cannot be read here. In Multisim export the circuit as a SPICE netlist "
                         "(a .cir file; look under the Transfer or File > Export menu), then open that file instead.")
    try: text = data.decode("utf-8-sig")
    except UnicodeDecodeError: text = data.decode("latin-1")
    head = text.lstrip()[:300].lower()
    if ext in LOGISIM_EXT or head.startswith("<?xml") or "<project" in head:
        from .logisim_in import circ_to_json
        js, notes = circ_to_json(text); return "digital", js, notes
    if head.startswith("{"):
        try: raw = json.loads(text)
        except ValueError as e: raise ValueError(f"{name} is not valid JSON ({e}).")
        kind = classify(raw)
        if kind == "analog":
            nl, errs = aparse(raw)
            if nl is None: raise ValueError("; ".join(errs))
            return "analog", adumps(nl), []
        if kind == "digital" and isinstance(raw.get("circuits"), dict): return "digital", text, []
        if kind == "digital":
            c, errs = parse(raw)
            if c is None: raise ValueError("; ".join(errs))
            return "digital", dumps(c), []
        raise ValueError("This JSON file is not a circuit.")
    from .spice_in import spice_to_json
    js, notes = spice_to_json(text); return "analog", js, notes
