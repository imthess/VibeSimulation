"""Compiler directives: `define (with arguments), `undef, `ifdef / `ifndef / `elsif / `else / `endif, and `NAME uses. Lines keep their numbers."""
import re

from ...verilog.lexer import VError
from ..feature import Feature, feature

_DEF = re.compile(r"`define\s+([A-Za-z_]\w*)(\([^)]*\))?[ \t]*(.*)")
_USE = re.compile(r"`([A-Za-z_]\w*)")
IGNORED = ("`timescale", "`default_nettype", "`resetall", "`celldefine", "`endcelldefine", "`line", "`pragma")


@feature
class Preprocess(Feature):
    name = "preprocess"
    summary = "`define / `ifdef / `include-free macro expansion"
    order = 10
    stage = "text"
    triggers = ("`",)

    def apply(self, ctx):
        macros, out, stack = {}, [], []                  # stack: [(active, taken_any, parent_active)]
        lines = ctx.text.split("\n"); k = 0
        def active(): return all(s[0] for s in stack)
        while k < len(lines):
            raw, n = lines[k], k + 1; extra = 0
            while raw.rstrip().endswith("\\") and k + 1 + extra < len(lines):          # a macro body may continue on the next line
                extra += 1; raw = raw.rstrip()[:-1] + " " + lines[k + extra]
            s = raw.strip()
            if s.startswith("`"):
                word = s.split()[0] if s.split() else "`"
                if word in IGNORED: out.append(""); out.extend([""] * extra); k += 1 + extra; continue
                if word == "`include": raise VError("`include is not supported: put the code in the same file (or use a package)", n)
                if word in ("`ifdef", "`ifndef"):
                    name = s.split()[1] if len(s.split()) > 1 else ""
                    cond = (name in macros) == (word == "`ifdef"); stack.append([cond and active(), cond, active()])
                elif word == "`elsif":
                    if not stack: raise VError("`elsif without `ifdef", n)
                    name = s.split()[1] if len(s.split()) > 1 else ""; st = stack[-1]
                    cond = (name in macros) and not st[1]; st[0] = cond and st[2]; st[1] = st[1] or cond
                elif word == "`else":
                    if not stack: raise VError("`else without `ifdef", n)
                    st = stack[-1]; st[0] = (not st[1]) and st[2]; st[1] = True
                elif word == "`endif":
                    if not stack: raise VError("`endif without `ifdef", n)
                    stack.pop()
                elif word == "`undef":
                    if active(): macros.pop(s.split()[1], None) if len(s.split()) > 1 else None
                elif word == "`define":
                    m = _DEF.match(s)
                    if not m: raise VError("a `define needs a name", n)
                    if active(): macros[m.group(1)] = ([a.strip() for a in m.group(2)[1:-1].split(",")] if m.group(2) else None, re.sub(r"//.*", "", m.group(3)).strip())
                else:
                    out.append(self.expand(raw, macros, n) if active() else ""); out.extend([""] * extra); k += 1 + extra; continue
                out.append(""); out.extend([""] * extra); k += 1 + extra; continue
            out.append(self.expand(raw, macros, n) if active() else ""); out.extend([""] * extra); k += 1 + extra
        if stack: raise VError("an `ifdef is never closed with `endif", len(lines))
        ctx.text = "\n".join(out)

    def expand(self, line, macros, n):
        """Replace every `NAME (and `NAME(args)) in one line, repeatedly, so a macro may use another."""
        for _ in range(200):
            m = _USE.search(line)
            if not m: return line
            name = m.group(1)
            if name not in macros: raise VError(f"the macro `{name} is not defined", n)
            params, body = macros[name]
            if params is None: line = line[:m.start()] + body + line[m.end():]; continue
            args, used = self.arguments(line, m.end(), name, n)
            if len(args) != len(params): raise VError(f"the macro `{name} takes {len(params)} argument(s)", n)
            text = body
            for p, a in zip(params, args): text = re.sub(rf"\b{re.escape(p)}\b", lambda _m, a=a: a, text)
            line = line[:m.start()] + text + line[m.end() + used:]
        raise VError("macros use each other in a loop", n)

    @staticmethod
    def arguments(line, start, name, n):
        """The comma separated arguments of a macro use whose '(' is at `start`; -> (args, characters used)."""
        if not line[start:].startswith("("): raise VError(f"the macro `{name} needs arguments", n)
        depth, cur, args = 0, "", []
        for j in range(start, len(line)):
            ch = line[j]
            if ch == "(":
                depth += 1
                if depth > 1: cur += ch
            elif ch == ")":
                depth -= 1
                if depth == 0: args.append(cur.strip()); return args, j + 1 - start
                cur += ch
            elif ch == "," and depth == 1: args.append(cur.strip()); cur = ""
            else: cur += ch
        raise VError(f"the macro `{name}( is never closed", n)
