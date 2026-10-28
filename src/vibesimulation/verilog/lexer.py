"""Verilog tokens. Comments are kept apart (a comment like `// @g1` names the part made by the statement on that line)."""
import re


class VError(Exception):
    """A problem in the Verilog text, with the line it is on."""
    def __init__(self, msg, line=0):
        super().__init__(msg); self.msg, self.line = msg, line


class Tok:
    __slots__ = ("kind", "val", "line")

    def __init__(self, kind, val, line): self.kind, self.val, self.line = kind, val, line

    def __repr__(self): return f"{self.kind}:{self.val!r}@{self.line}"


class Num:
    """A number literal. bits/xmask/zmask are unsigned ints; width None = unsized."""
    def __init__(self, bits, width, signed, based, xmask=0, zmask=0):
        self.bits, self.width, self.signed, self.based, self.xmask, self.zmask = bits, width, signed, based, xmask, zmask


OPS = ["<<<", ">>>", "===", "!==", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "~&", "~|", "~^", "^~", "**", "+:", "-:", "->",
       "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "<", ">", "=", "?", ":", ";", ",", ".", "(", ")", "[", "]", "{", "}", "#", "@"]
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
_SYS = re.compile(r"\$[A-Za-z_][A-Za-z0-9_$]*")
_DEC = re.compile(r"[0-9][0-9_]*")
_BASED = re.compile(r"[ \t]*'([sS]?)([bBoOdDhH])[ \t]*([0-9a-fA-FxXzZ_?]+)")
_UNSIZED = re.compile(r"'([sS]?)([bBoOdDhH])[ \t]*([0-9a-fA-FxXzZ_?]+)")


def _based(sign, base, digits, width, line):
    base = base.lower(); digits = digits.replace("_", "").lower().replace("?", "z")
    bpd = {"b": 1, "o": 3, "h": 4}.get(base)
    if base == "d":
        if any(c in "xz" for c in digits):
            if len(digits) != 1: raise VError(f"'{digits}': a decimal number cannot mix x/z with digits", line)
            n = width if width else 32
            return Num(0, width, bool(sign), True, (1 << n) - 1 if digits == "x" else 0, (1 << n) - 1 if digits == "z" else 0)
        return Num(int(digits), width, bool(sign), True)
    bits = x = z = 0
    for c in digits:
        bits <<= bpd; x <<= bpd; z <<= bpd
        if c == "x": x |= (1 << bpd) - 1
        elif c == "z": z |= (1 << bpd) - 1
        else:
            try: v = int(c, 16)
            except ValueError: raise VError(f"'{c}' is not a digit of base {base}", line)
            if v >= (1 << bpd): raise VError(f"'{c}' is not a digit of base {base}", line)
            bits |= v
    n = len(digits) * bpd
    width_eff = width if width else max(32, n)
    # a number whose leftmost digit is x or z extends that digit to the full width
    if (x or z) and digits[0] in "xz" and width_eff > n:
        fill = ((1 << (width_eff - n)) - 1) << n
        if digits[0] == "x": x |= fill
        else: z |= fill
    return Num(bits, width, bool(sign), True, x, z)


def lex(text):
    """-> (tokens, comments {line: [text]})"""
    toks, comments, i, line, n = [], {}, 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n": line += 1; i += 1; continue
        if c in " \t\r\f": i += 1; continue
        if text.startswith("//", i):
            j = text.find("\n", i); j = n if j < 0 else j
            comments.setdefault(line, []).append(text[i + 2:j].strip()); i = j; continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0: raise VError("unterminated /* comment", line)
            body = text[i + 2:j]; comments.setdefault(line, []).append(" ".join(body.split()))
            line += body.count("\n"); i = j + 2; continue
        if text.startswith("(*", i) and not text.startswith("(*)", i):       # attributes (* ... *) are ignored
            j = text.find("*)", i + 2)
            if j < 0: raise VError("unterminated (* attribute", line)
            line += text[i:j].count("\n"); i = j + 2; continue
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\": j += 1
                if j < n and text[j] == "\n": line += 1
                j += 1
            toks.append(Tok("str", text[i + 1:j], line)); i = j + 1; continue
        if c == "`":                                                            # `timescale / `default_nettype are skipped; other directives are not supported
            j = text.find("\n", i); j = n if j < 0 else j; word = text[i:j].split()[0] if text[i:j].split() else "`"
            if word not in ("`timescale", "`default_nettype", "`resetall"): raise VError(f"the compiler directive {word} is not supported", line)
            i = j; continue
        if c == "\\":                                                           # escaped identifier: up to white space
            j = i + 1
            while j < n and not text[j].isspace(): j += 1
            toks.append(Tok("id", text[i + 1:j], line)); i = j; continue
        if c == "$":
            m = _SYS.match(text, i)
            if not m: raise VError("stray $", line)
            toks.append(Tok("sys", m.group(), line)); i = m.end(); continue
        if c.isdigit():
            m = _DEC.match(text, i); size = int(m.group().replace("_", ""))
            mb = _BASED.match(text, m.end())
            if mb:
                if size < 1 or size > 4096: raise VError(f"bad size {size} in a number", line)
                toks.append(Tok("num", _based(mb.group(1), mb.group(2), mb.group(3), size, line), line)); i = mb.end(); continue
            if text[m.end():m.end() + 1] == "." and text[m.end() + 1:m.end() + 2].isdigit(): raise VError("real numbers are not supported", line)
            toks.append(Tok("num", Num(size, None, True, False), line)); i = m.end(); continue
        if c == "'":
            mu = _UNSIZED.match(text, i)
            if mu:
                toks.append(Tok("num", _based(mu.group(1), mu.group(2), mu.group(3), None, line), line)); i = mu.end(); continue
            raise VError("unexpected '", line)
        m = _ID.match(text, i)
        if m: toks.append(Tok("id", m.group(), line)); i = m.end(); continue
        for op in OPS:
            if text.startswith(op, i): toks.append(Tok("op", op, line)); i += len(op); break
        else: raise VError(f"unexpected character {c!r}", line)
    toks.append(Tok("eof", None, line))
    return toks, comments
