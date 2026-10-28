"""x and z values.

  * `assign y = en ? a : 8'bz;` (and `en ? 8'bz : a`) is a tri-state driver. Several of them may drive one net (a bus);
    the values are OR-ed together, which is right as long as at most one driver is on. A bus nobody drives reads 0.
  * x or z written as the whole right-hand side of an assignment (or as a branch of ?:) means "don't care": it becomes 0.
    A warning is given. In any other place x/z is an error, because a circuit cannot compute with unknown values.
"""
from ..core.bits import mask


class TriStateMixin:
    def warn(self, msg, line=None):
        self.lint(msg, line)

    def is_z(self, e):
        while e.kind == "paren": e = e.x
        if e.kind != "num": return False
        n = e.num; w = n.width or 32
        return n.zmask != 0 and n.xmask == 0 and n.bits == 0 and n.zmask == mask(w)

    def tri_split(self, rhs):
        """(enable expr, data expr, enable is inverted) if rhs is `c ? data : z` or `c ? z : data`, else None."""
        while rhs.kind == "paren": rhs = rhs.x
        if rhs.kind != "cond": return None
        if self.is_z(rhs.b) and not self.is_z(rhs.a): return rhs.c, rhs.a, False
        if self.is_z(rhs.a) and not self.is_z(rhs.b): return rhs.c, rhs.b, True
        return None

    def dont_care_nodes(self, rhs):
        """Ids of x/z literals that sit where a don't-care is allowed."""
        out = set()
        def walk(e):
            while e.kind == "paren": e = e.x
            if e.kind == "num" and (e.num.xmask or e.num.zmask): out.add(id(e))
            elif e.kind == "cond": walk(e.a); walk(e.b)
        walk(rhs); return out

    def add_tri(self, n, lo, hi, v):
        n.tri.setdefault((lo, hi), []).append(v)

    def merge_tri(self, n):
        b = self.b
        for key, vs in n.tri.items():
            if key in n.parts or any(not (key[1] < l2 or key[0] > h2) for (l2, h2) in n.parts): self.err(f"'{n.name}' is driven by a tri-state driver and by something else", n.line)
            n.parts[key] = vs[0] if len(vs) == 1 else b.gate("OR", vs)
        n.tri = {}
