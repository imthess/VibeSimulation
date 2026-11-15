"""The Verilog / SystemVerilog preprocessor, as in iverilog, Verilator and Vivado: `define, `undef, `ifdef / `ifndef / `elsif / `else / `endif,
`include and macro use (`NAME, `NAME(args)), plus the -D and -I settings of the simulation settings.

Line numbers never change (a `define line becomes a blank line, a skipped block becomes blank lines, an included file is put on the line of its `include),
so every message and every highlighted line still points at the text the user typed. `timescale, `default_nettype and `resetall pass through untouched."""
import os
import re

from .lexer import VError

PASS = {"timescale", "default_nettype", "resetall", "celldefine", "endcelldefine", "pragma", "line"}
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


class Config:
    """-D NAME[=value] and -I dir (set from the simulation settings; empty by default)."""
    defines = {}
    incdirs = []
    base_dir = ""

    @classmethod
    def set(cls, defines=None, incdirs=None, base_dir=""):
        cls.defines = dict(defines or {}); cls.incdirs = list(incdirs or []); cls.base_dir = base_dir


class Macro:
    def __init__(self, body, params=None): self.body, self.params = body, params


def preprocess(text, defines=None, incdirs=None, _depth=0, _macros=None):
    if "`" not in text: return text
    if _depth > 8: raise VError("`include nested too deeply (a file includes itself?)", 1)
    macros = _macros if _macros is not None else {k: Macro(str(v)) for k, v in (Config.defines if defines is None else defines).items()}
    dirs = list(Config.incdirs if incdirs is None else incdirs)
    lines = text.split("\n"); out = []; stack = []      # stack of [this branch active, some branch already taken, parent active]
    active = lambda: all(s[0] for s in stack)
    i = 0; in_block = False
    while i < len(lines):
        raw, ln = lines[i], i + 1; i += 1
        s = raw.strip()
        if not in_block and s.startswith("`"):
            m = _ID.match(s, 1); word = m.group() if m else ""
            if word == "define":
                body = raw
                while body.rstrip().endswith("\\") and i < len(lines): body = body.rstrip()[:-1] + " " + lines[i]; i += 1; out.append("")
                if active(): _define(body, macros, ln)
                out.append(""); continue
            if word == "undef":
                if active(): macros.pop(s[6:].strip().split()[0] if s[6:].strip() else "", None)
                out.append(""); continue
            if word in ("ifdef", "ifndef"):
                name = (s[len(word) + 1:].split() or [""])[0]; cond = (name in macros) == (word == "ifdef")
                stack.append([cond and active(), cond, active()]); out.append(""); continue
            if word == "elsif":
                if not stack: raise VError("`elsif without `ifdef", ln)
                name = (s[6:].split() or [""])[0]; top = stack[-1]; cond = (name in macros) and not top[1]
                top[0] = cond and top[2]; top[1] = top[1] or cond; out.append(""); continue
            if word == "else":
                if not stack: raise VError("`else without `ifdef", ln)
                top = stack[-1]; top[0] = (not top[1]) and top[2]; top[1] = True; out.append(""); continue
            if word == "endif":
                if not stack: raise VError("`endif without `ifdef", ln)
                stack.pop(); out.append(""); continue
            if word == "include":
                if not active(): out.append(""); continue
                mm = re.match(r'`include\s+"([^"]+)"', s)
                if not mm: raise VError("`include needs a file name in quotes", ln)
                out.append(_include(mm.group(1), dirs, macros, ln, _depth)); continue
            if word in PASS: out.append(raw if active() else ""); continue
        if not active(): out.append(""); continue
        res, in_block = _expand(raw, macros, ln, in_block); out.append(res)
    if stack: raise VError("`ifdef without a matching `endif", len(lines))
    return "\n".join(out)


def _define(body, macros, ln):
    m = re.match(r"\s*`define\s+([A-Za-z_][A-Za-z0-9_$]*)(\(([^)]*)\))?\s*(.*)$", body)
    if not m: raise VError("`define needs a name", ln)
    name, params, rest = m.group(1), m.group(3), m.group(4)
    rest = re.sub(r"//.*$", "", rest).strip()
    macros[name] = Macro(rest, [p.strip() for p in params.split(",")] if params is not None else None)


def _include(name, dirs, macros, ln, depth):
    cands = [name] if os.path.isabs(name) else [os.path.join(d, name) for d in [Config.base_dir] + dirs if d is not None]
    for p in cands + [name]:
        if os.path.isfile(p):
            try: txt = open(p, encoding="utf-8").read()
            except OSError as e: raise VError(f"cannot read '{name}': {e}", ln)
            body = preprocess(txt, None, dirs, depth + 1, macros)          # same macro table: what the file defines is known afterwards
            return " ".join(re.sub(r"//.*$", "", l) for l in body.split("\n")).strip()      # one line, so the numbers after it stay right
    raise VError(f"`include file '{name}' not found (add its folder under 'Include folders' in the simulation settings)", ln)


def _expand(raw, macros, ln, in_block):
    """Replace `NAME uses outside strings and comments."""
    out, i, n = [], 0, len(raw)
    while i < n:
        if in_block:
            j = raw.find("*/", i)
            if j < 0: out.append(raw[i:]); return "".join(out), True
            out.append(raw[i:j + 2]); i = j + 2; in_block = False; continue
        c = raw[i]
        if raw.startswith("//", i): out.append(raw[i:]); break
        if raw.startswith("/*", i): in_block = True; out.append("/*"); i += 2; continue
        if c == '"':
            j = i + 1
            while j < n and raw[j] != '"': j += 2 if raw[j] == "\\" else 1
            out.append(raw[i:j + 1]); i = j + 1; continue
        if c == "`":
            m = _ID.match(raw, i + 1)
            if not m: out.append(c); i += 1; continue
            name = m.group()
            if name in PASS or name in ("define", "undef"): out.append(raw[i:]); break
            if name == "__LINE__": out.append(str(ln)); i = m.end(); continue
            if name == "__FILE__": out.append('"design.v"'); i = m.end(); continue
            mac = macros.get(name)
            if mac is None: raise VError(f"macro `{name} is not defined (use `define {name} ... or -D{name} in the simulation settings)", ln)
            i = m.end()
            if mac.params is not None:
                j = i
                while j < n and raw[j] == " ": j += 1
                if j >= n or raw[j] != "(": raise VError(f"macro `{name} needs {len(mac.params)} argument(s)", ln)
                depth, k, args, cur = 0, j, [], ""
                while k < n:
                    ch = raw[k]
                    if ch == "(":
                        depth += 1
                        if depth > 1: cur += ch
                    elif ch == ")":
                        depth -= 1
                        if depth == 0: break
                        cur += ch
                    elif ch == "," and depth == 1: args.append(cur); cur = ""
                    else: cur += ch
                    k += 1
                if depth != 0: raise VError(f"`{name}( is missing its closing )", ln)
                args.append(cur); args = [a.strip() for a in args]
                if len(args) != len(mac.params): raise VError(f"macro `{name} needs {len(mac.params)} argument(s), got {len(args)}", ln)
                body = mac.body
                for p, a in zip(mac.params, args): body = re.sub(r"\b" + re.escape(p) + r"\b", lambda _m, a=a: a, body)
                i = k + 1
            else: body = mac.body
            body, _ = _expand(body, macros, ln, False); out.append(body); continue
        out.append(c); i += 1
    return "".join(out), in_block
