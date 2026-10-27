"""Engineering-notation numbers: '4.7k' -> 4700, 0.0033 -> '3.3 m'."""
import math
import re

SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12}
_NUM = re.compile(r"^\s*([+-]?\d*\.?\d+(?:e[+-]?\d+)?)\s*([a-zµ]*)\s*(?:ohm|ohms|Ω|v|a|f|h|hz)?\s*$", re.I)


def parse_value(v):
    """Number, or a string with an SI suffix (k, meg, m, u, n, p...). Raises ValueError."""
    if isinstance(v, bool): raise ValueError("not a number")
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    m = _NUM.match(s)
    if m:
        num, suf = float(m.group(1)), m.group(2).lower()
        if suf == "": return num
        if suf in SUFFIX: return num * SUFFIX[suf]
        if suf.startswith("meg"): return num * 1e6
        if suf[0] in SUFFIX and suf[0] != "m": return num * SUFFIX[suf[0]]
        if suf[0] == "m": return num * 1e-3
    raise ValueError(f"'{v}' is not a number (examples: 100, 4.7k, 10meg, 220n)")


def fmt_si(x, unit="", digits=4):
    if x is None: return "?"
    if x == 0 or abs(x) < 1e-18: return f"0 {unit}".strip()
    exp = max(-4, min(4, math.floor(math.log10(abs(x)) / 3)))
    pre = {-4: "p", -3: "n", -2: "µ", -1: "m", 0: "", 1: "k", 2: "M", 3: "G", 4: "T"}[exp]
    return f"{x / 10 ** (3 * exp):.{digits}g} {pre}{unit}".strip()
