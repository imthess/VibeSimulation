"""After a SystemVerilog text is lowered and compiled, the pieces the document keeps must be pieces of what the *user wrote*.

The compiler cuts the text it was given (lowered Verilog) into one piece per module; here the same cuts are made in the original
text. Declarations outside every module (packages, file-level typedefs and parameters) are put at the top of each piece, so a module can
be edited and compiled alone. Part lines (the Verilog line that made each part) are moved to the lines of those pieces."""
from ..verilog.lexer import VError
from .analysis import modules
from .lexer import lex


class Slicer:
    def __init__(self, original, lowered):
        self.lines = original.split("\n"); toks = lex(lowered); self.mods = []
        for m in modules(toks):
            name = toks[m.kw + 1].text if toks[m.kw + 1].kind != "comment" else toks[m.kw + 2].text
            self.mods.append((name, toks[m.kw].line, toks[min(m.end, len(toks) - 1)].line))
        self.prelude = self._prelude()

    def _prelude(self):
        inside = set()
        for _, a, b in self.mods: inside.update(range(a, b + 1))
        out = [ln for k, ln in enumerate(self.lines, 1) if k not in inside]
        text = "\n".join(out).strip("\n")
        code = [ln for ln in text.split("\n") if ln.strip() and not ln.strip().startswith("//")]
        return text + "\n" if code else ""

    def piece(self, name):
        """(text, number of lines put above the module) of module `name`; the whole text when it is the only module."""
        if len(self.mods) == 1: return "\n".join(self.lines).rstrip("\n") + "\n", 0
        a, b = next((a, b) for n, a, b in self.mods if n == name)
        body = "\n".join(self.lines[a - 1:b]).rstrip() + "\n"
        return self.prelude + body, (self.prelude.count("\n"))

    def apply(self, result):
        """Replace the pieces of a vlsi.compiler.Compiled result by the user's own text; move its part lines to match."""
        known = {n for n, _, _ in self.mods}
        for table in (result.slices, result.testbenches):
            for name in list(table):
                if name in known: table[name] = self.piece(name)[0]
        if len(self.mods) > 1:
            for name, lines in result.partlines.items():
                if name not in known: continue
                start = next(a for n, a, _ in self.mods if n == name); above = self.piece(name)[1]
                result.partlines[name] = {pid: (ln - start + 1 + above if ln else ln) for pid, ln in lines.items()}
