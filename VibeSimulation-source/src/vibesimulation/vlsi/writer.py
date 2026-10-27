"""Circuit -> Verilog text for the VLSI section, with a small cache so the editor can ask on every change."""
from ..core.model import Circuit
from ..core.serializer import dumps, parse
from ..verilog.emit import circuit_to_verilog


def canonical(text):
    """Canonical JSON of a circuit's text (layout left out), or None if the text is not a valid circuit."""
    c, errs = parse(text) if text.strip() else (Circuit(), [])
    return dumps(c) if c is not None and not errs else None


class VerilogWriter:
    def __init__(self): self._cache = {}

    def write(self, name, text, others):
        """Verilog of circuit `name` whose JSON is `text`; `others` = {name: json text} of the other circuits (they may be used inside)."""
        canon = canonical(text)
        if canon is None: return None
        key = (name, canon, tuple(sorted((n, canonical(t)) for n, t in others.items())))
        hit = self._cache.get(key)
        if hit is None:
            c, _ = parse(text) if text.strip() else (Circuit(), [])
            hit = circuit_to_verilog(name, c) if c is not None else ""
            if len(self._cache) > 60: self._cache.clear()
            self._cache[key] = hit
        return hit
