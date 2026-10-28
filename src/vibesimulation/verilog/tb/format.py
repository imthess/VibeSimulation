"""Text for $display, $write, $strobe and $monitor: the format rules of Verilog (%d %b %h %o %c %s %t %m ...).

An argument is an Arg: a number with its width and signedness, or a piece of text.
"""
import re
from ..lexer import VError


class Arg:
    __slots__ = ("val", "width", "signed", "text")

    def __init__(self, val=0, width=32, signed=False, text=None): self.val, self.width, self.signed, self.text = val, width, signed, text

    def sval(self):
        return self.val - (1 << self.width) if self.signed and self.val >> (self.width - 1) & 1 else self.val


_SPEC = re.compile(r"%([-0]*)(\d*)(?:\.(\d+))?([a-zA-Z%])")
_ESC = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "r": "\r", "v": "\v", "f": "\f", "a": "\a"}


def unescape(s):
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            d = s[i + 1]
            if d in _ESC: out.append(_ESC[d]); i += 2; continue
            if d in "01234567":
                j = i + 1
                while j < len(s) and j < i + 4 and s[j] in "01234567": j += 1
                out.append(chr(int(s[i + 1:j], 8) & 255)); i = j; continue
            out.append(d); i += 2; continue
        out.append(c); i += 1
    return "".join(out)


def digits_dec(a):
    """Width the %d field takes when no width is given: the digits of the biggest value, plus a place for the sign."""
    if a.signed: return len(str(1 << (a.width - 1))) + 1
    return len(str((1 << a.width) - 1))


def render_number(a, conv, minimal):
    if a.text is not None and conv in "dbho": a = Arg(int.from_bytes(a.text.encode("latin-1", "replace"), "big"), max(8, 8 * len(a.text)), False)
    w = a.width
    if conv in "di":
        s = str(a.sval()); return s if minimal else s.rjust(digits_dec(a))
    if conv == "t":
        s = str(a.sval()); return s if minimal else s.rjust(len(str((1 << w) - 1)))
    if conv == "b": s = format(a.val, "b"); return s if minimal else s.zfill(w)
    if conv == "o": s = format(a.val, "o"); return s if minimal else s.zfill((w + 2) // 3)
    if conv in "hx": s = format(a.val, "x"); return s if minimal else s.zfill((w + 3) // 4)
    raise VError(f"the format %{conv} is not supported")


def pad(s, width, left, zero=False):
    if width and len(s) < width: return s.ljust(width) if left else (s.rjust(width, "0") if zero else s.rjust(width))
    return s


def one(conv, flags, width, prec, a, top):
    left = "-" in flags; zero = "0" in flags and width != ""; minimal = ("0" in flags and width == "") or width != ""
    w = int(width) if width else 0
    if conv in "di" or conv in "bohxt":
        return pad(render_number(a, conv, minimal), w, left, zero)
    if conv == "c":
        v = a.val if a.text is None else (ord(a.text[-1]) if a.text else 0)
        return pad(chr(v & 255), w, left)
    if conv == "s":
        if a.text is not None: return pad(a.text, w, left)
        b = a.val.to_bytes((a.width + 7) // 8, "big").lstrip(b"\0")
        return pad(b.decode("latin-1"), w, left)
    if conv in "efg":
        v = float(a.sval()); p = int(prec) if prec != "" and prec is not None else 6
        return pad(format(v, f".{p}{conv}"), w, left)
    if conv == "m": return pad(top, w, left)
    raise VError(f"the format %{conv} is not supported")


def default_text(a, radix="d"):
    if a.text is not None: return a.text
    return render_number(a, radix, False)


def format_args(args, top="top", radix="d"):
    """Text for a list of Args, the first one being the format string when it is text."""
    if not args: return ""
    out = []; rest = list(args)
    first = rest[0]
    if first.text is not None:
        fmt = unescape(first.text); rest = rest[1:]; pos = 0
        for m in _SPEC.finditer(fmt):
            out.append(fmt[pos:m.start()]); pos = m.end()
            flags, width, prec, conv = m.groups(); conv = conv.lower() if conv != "%" else conv
            if conv == "%": out.append("%"); continue
            if conv == "m": out.append(one("m", flags, width, prec, Arg(), top)); continue
            if not rest: raise VError(f"the format '{m.group()}' has no value to show")
            out.append(one(conv, flags, width, prec, rest.pop(0), top))
        out.append(fmt[pos:])
    for a in rest: out.append(default_text(a, radix))
    return "".join(out)
