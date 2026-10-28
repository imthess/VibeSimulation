"""The circuits of one project. Like Logisim, a project holds several circuits and one can be placed inside another
(a *subcircuit*). The Document keeps the JSON text of every circuit here so that a subcircuit part can look up the
pins of the circuit it stands for."""

DEFS = {}          # circuit name -> JSON text
CURRENT = ""       # the circuit being edited
_cache = {}        # JSON text -> parsed Circuit


def set_project(defs, current):
    global DEFS, CURRENT
    DEFS, CURRENT = dict(defs), current


def lookup(name):
    """The parsed circuit called name (pins and parts, no layout), or None if there is none / its JSON is broken."""
    text = DEFS.get(name)
    if text is None: return None
    c = _cache.get(text)
    if c is None:
        from .serializer import parse
        if not text.strip():
            from .model import Circuit
            c = Circuit()
        else:
            c, _ = parse(text)
        if len(_cache) > 200: _cache.clear()
        _cache[text] = c
    return c


def uses(name, seen=None):
    """Names of every circuit that circuit `name` contains, directly or through other circuits."""
    seen = set() if seen is None else seen
    c = lookup(name)
    for comp in (c.components if c else []):
        n = getattr(comp, "is_sub", False) and comp.attrs.get("circuit")
        if n and n not in seen:
            seen.add(n); uses(n, seen)
    return seen


def placeable(current=None):
    """Circuits that may be placed in `current` (not itself, nothing that already contains it)."""
    cur = CURRENT if current is None else current
    return [n for n in DEFS if n != cur and cur not in uses(n)]


def classic_geometry(nin, nout):
    """Logisim's default (classic) look of a subcircuit: pin offsets from the part's location and the body rectangle.
    Inputs are on the west edge, outputs on the east edge; the location is on the east edge (west if there are no outputs)."""
    mh = max(nin, nout)
    w = 30
    h = 30 if mh < 3 else 10 * mh

    def off(nf, no):
        mt = max(nf, no)
        return (15 if mt <= 1 else 10 if mt == 2 else 5) + 10 * ((mt - nf) // 2)
    ow, oe = off(nin, nout), off(nout, nin)
    if nout > 0: ax, ay = w, oe
    elif nin > 0: ax, ay = 0, ow
    else: ax, ay = 0, 0
    ins = [(0 - ax, ow + 10 * i - ay) for i in range(nin)]
    outs = [(w - ax, oe + 10 * i - ay) for i in range(nout)]
    return ins, outs, (-ax, -ay, w - ax, h - ay)
