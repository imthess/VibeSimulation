"""Evaluate a constant expression of whole numbers (sizes of vectors, enum values). Returns None when it cannot."""
import math
import re

_NUM = re.compile(r"(?:([0-9][0-9_]*))?'[sS]?([bBoOdDhH])([0-9a-fA-F_]+)$")


def literal(text):
    t = text.replace("_", "")
    if t.isdigit(): return int(t)
    m = _NUM.match(text)
    if m and not re.search(r"[xXzZ?]", m.group(3)): return int(m.group(3).replace("_", ""), {"b": 2, "o": 8, "d": 10, "h": 16}[m.group(2).lower()])
    return None


class _P:
    def __init__(self, toks, env): self.t, self.i, self.env = [x for x in toks if x.kind != "comment"], 0, env

    def peek(self): return self.t[self.i].text if self.i < len(self.t) else None

    def take(self): self.i += 1; return self.t[self.i - 1]

    def binary(self, level):
        ops = [("<<", ">>"), ("+", "-"), ("*", "/", "%"), ("**",)]
        if level == len(ops): return self.unary()
        v = self.binary(level + 1)
        while self.peek() in ops[level]:
            op = self.take().text; r = self.binary(level + 1)
            if v is None or r is None: v = None; continue
            try: v = {"<<": lambda: v << r, ">>": lambda: v >> r, "+": lambda: v + r, "-": lambda: v - r, "*": lambda: v * r, "/": lambda: v // r, "%": lambda: v % r, "**": lambda: v ** r}[op]()
            except (ZeroDivisionError, ValueError, OverflowError): v = None
        return v

    def unary(self):
        if self.peek() == "-": self.take(); v = self.unary(); return None if v is None else -v
        if self.peek() == "+": self.take(); return self.unary()
        return self.primary()

    def primary(self):
        t = self.take() if self.i < len(self.t) else None
        if t is None: return None
        if t.text == "(":
            v = self.binary(0)
            if self.peek() == ")": self.take()
            else: return None
            return v
        if t.kind == "num": return literal(t.text)
        if t.kind == "sys" and t.text == "$clog2" and self.peek() == "(":
            self.take(); v = self.binary(0)
            if self.peek() == ")": self.take()
            return None if v is None or v < 1 else max(0, math.ceil(math.log2(v)))
        if t.kind == "id": return self.env.get(t.text)
        return None


def evaluate(tokens, env=None):
    p = _P(tokens, env or {}); v = p.binary(0)
    return v if p.i == len(p.t) else None


def range_width(tokens, env=None):
    """Width of a packed range given as tokens `[hi:lo]` (the brackets included): None when unknown."""
    inner = tokens[1:-1]
    for k, t in enumerate(inner):
        if t.text == ":" and t.kind == "op":
            hi, lo = evaluate(inner[:k], env), evaluate(inner[k + 1:], env)
            return None if hi is None or lo is None else abs(hi - lo) + 1
    return None
