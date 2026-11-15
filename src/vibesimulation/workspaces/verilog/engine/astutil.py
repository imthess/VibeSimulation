"""Small helpers for working with the syntax tree: copying a piece of it while replacing names (used by generate blocks)."""
from .lexer import Num
from .parser import N


def num_node(v, line):
    """A plain decimal number node (negative values become a unary minus)."""
    if v < 0: return N("un", line, op="-", x=N("num", line, num=Num(-v, None, True, False)))
    return N("num", line, num=Num(v, None, True, False))


def clone(x, subst=None, rename=None, suffix=""):
    """Deep copy of a tree piece.
    subst  {name: int}   - every use of the name becomes that number (genvars, localparams of a generate block)
    rename {name: name}  - uses and declarations of the name are renamed (nets declared inside a generate block)
    suffix               - appended to instance / gate names so repeated blocks stay distinct
    """
    subst = subst or {}; rename = rename or {}
    if isinstance(x, N):
        if x.kind == "id":
            if x.name in subst: return num_node(subst[x.name], x.line)
            return N("id", x.line, name=rename.get(x.name, x.name))
        d = {}
        for k, v in x.__dict__.items():
            if k in ("kind", "line"): continue
            d[k] = clone(v, subst, rename, suffix)
        if x.kind == "net":
            d["names"] = [(rename.get(nm, nm), clone(init, subst, rename, suffix), ln) for nm, init, ln in x.names]
            d["arrays"] = {rename.get(k, k): clone(v, subst, rename, suffix) for k, v in x.arrays.items()}
        elif x.kind in ("inst", "gate") and suffix and d.get("name"):
            d["name"] = d["name"] + "_" + suffix if x.kind == "gate" else d["name"] + "_" + suffix
        elif x.kind == "fcall" or x.kind == "taskcall": d["name"] = x.name
        return N(x.kind, x.line, **d)
    if isinstance(x, list): return [clone(v, subst, rename, suffix) for v in x]
    if isinstance(x, tuple): return tuple(clone(v, subst, rename, suffix) for v in x)
    if isinstance(x, dict): return {k: clone(v, subst, rename, suffix) for k, v in x.items()}
    return x


def walk(x):
    """Every syntax-tree node inside x (x itself included), depth first."""
    if isinstance(x, N):
        yield x
        for k, v in x.__dict__.items():
            if k not in ("kind", "line"): yield from walk(v)
    elif isinstance(x, (list, tuple)):
        for v in x: yield from walk(v)
    elif isinstance(x, dict):
        for v in x.values(): yield from walk(v)
