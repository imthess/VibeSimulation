"""Warnings found while a module is built (they never stop the build): lost bits, unconnected outputs, unused signals ...

Each warning is (line, text) and is collected in `ctx.warnings`. A warning means "this is legal but probably not what you meant".
"""
from ..core.bits import mask


class LintMixin:
    def lint(self, msg, line=None):
        key = (line or self.line, msg)
        if key not in self.ctx.warning_set: self.ctx.warning_set.add(key); self.ctx.warnings.append(key)

    def const_fits(self, e, w):
        """True if e is a plain number (or a parameter / constant expression) whose value fits in w bits."""
        try: v = self.ci(e)
        except Exception: return False
        return -(1 << (w - 1)) <= v < (1 << w) if w > 0 else False

    def check_assign_width(self, rhs, L, target, line):
        """A value wider than what it is stored in loses its upper bits."""
        w, s, free = self.info(rhs)
        if w <= L: return
        if self.is_const(rhs) and self.const_fits(rhs, L): return
        if rhs.kind == "num" and rhs.num.width is None: return
        if rhs.kind in ("bin", "cond", "paren", "un") and not self.expr_really_wide(rhs, L): return
        self.lint(f"a {w}-bit value is stored in {L}-bit '{target}': the upper {w - L} bit(s) are lost", line)

    def expr_really_wide(self, e, L):
        """Binary operations on unsized constants are 32 bits wide in Verilog but usually not meant that way: only warn when a real signal makes it wide."""
        from .astutil import walk
        for n in walk(e):
            if n.kind == "id" and n.name not in self.params:
                nt = self.nets.get(n.name)
                if nt is not None and nt.w > L: return True
            if n.kind == "num" and n.num.width and n.num.width > L: return True
        return False

    def check_compare(self, e, wa, wb):
        if wa != wb and not self.is_const(e.a) and not self.is_const(e.b):
            self.lint(f"comparing a {wa}-bit value with a {wb}-bit value: the shorter one is padded with zeros", e.line)

    def check_port_width(self, inst, port, expr_w, port_w, direction):
        if expr_w != port_w:
            self.lint(f"port '{port}' of '{inst.name}' is {port_w} bit(s) but is connected to {expr_w} bit(s)", inst.line)

    def report_unused(self):
        """Signals nobody reads."""
        for n in self.nets.values():
            if n.kind == "input" and not getattr(n, "used", False) and n.dir == "input":
                self.lint(f"input '{n.name}' is never used", n.line)
            elif n.kind not in ("input",) and n.dir != "output" and n.drivers and not getattr(n, "used", False) and getattr(n, "is_declared", True):
                self.lint(f"'{n.name}' is driven but never used", n.line)
