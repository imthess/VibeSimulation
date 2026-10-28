"""Style checks on the syntax tree (before anything is built): problems that a real simulator would show as wrong behaviour.

  * an `always @(a or b)` block that also reads `c`: it would not re-run when `c` changes (use `@*`)
  * `=` (blocking) used for a register in a clocked block: other blocks may see the old or the new value (use `<=`)
  * `<=` used inside a combinational `@*` block
"""
from .astutil import walk
from .lexer import VError


def _reads(body):
    """Names read by statements (everything except the base name of what is assigned)."""
    out = set()
    def expr(e):
        for n in walk(e):
            if n.kind == "id": out.add(n.name)
    def stmt(s):
        if s is None: return
        k = s.kind
        if k == "block":
            for x in s.stmts: stmt(x)
        elif k == "assign":
            expr(s.rhs)
            lv = s.lhs
            while lv.kind in ("index", "slice", "islice"):          # a[i] = ...  reads i
                for sub in ([lv.idx] if lv.kind == "index" else [lv.msb, lv.lsb] if lv.kind == "slice" else [lv.start, lv.width]): expr(sub)
                lv = lv.base
        elif k == "if": expr(s.cond); stmt(s.then); stmt(s.els)
        elif k == "case":
            expr(s.expr)
            for labels, b in s.items:
                for l in labels: expr(l)
                stmt(b)
            stmt(s.default)
        elif k in ("for", "while", "repeat"):
            if k == "for": stmt(s.init); stmt(s.step)
            expr(getattr(s, "cond", None) or getattr(s, "count", None)); stmt(s.body)
        elif k in ("delay", "event", "wait"): stmt(s.body)
    stmt(body); return out


def _assigned_blocking(body, out):
    for n in walk(body):
        if n.kind == "assign" and n.blocking:
            lv = n.lhs
            while lv.kind in ("index", "slice", "islice"): lv = lv.base
            if lv.kind == "id": out.append((lv.name, n.line))
    return out


def lint_modules(mods):
    """-> [(line, text)]"""
    out = []
    for m in mods:
        integers = {nm for it in m.items if it.kind == "net" and it.netkind == "integer" for nm, _, _ in it.names}
        for it in m.items:
            if it.kind != "always" or it.events is None: continue
            clocked = any(ed for ed, _ in it.events)
            if clocked:
                seen = set()
                for name, ln in _assigned_blocking(it.body, []):
                    if name in integers or name in seen: continue
                    seen.add(name)
                    out.append((ln, f"'{name}' is assigned with '=' in a clocked block: use '<=' for registers"))
            elif not it.star and it.events:
                listed = {n.name for _, e in it.events for n in walk(e) if n.kind == "id"}
                for name in sorted(_reads(it.body) - listed - integers):
                    if name in {p for p in _locals(m)}: continue
                    out.append((it.line, f"'{name}' is read in this block but is not in its sensitivity list: a simulator would not re-run it when '{name}' changes (write @* instead)"))
            if it.star or (it.events and not clocked):
                for n in walk(it.body):
                    if n.kind == "assign" and not n.blocking: out.append((n.line, "'<=' in a combinational block: use '=' here")); break
    return out


def _locals(m):
    return {nm for it in m.items if it.kind == "param" for nm in [it.name]} | {p.name for p in m.params}
