"""Questions the features ask about a token list: where the modules are, what is assigned in procedural code."""
from dataclasses import dataclass

from .consteval import evaluate
from .scan import block_end, group_end, semi_end, stmt_end

PROC_STARTS = {"always", "always_comb", "always_ff", "always_latch", "initial", "final"}
ASSIGN_OPS = {"=", "<=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>=", "++", "--"}
STMT_PREV = {"begin", ";", "else", "end", ":", ")", "*"}


@dataclass
class Module:
    name: str
    kw: int            # index of the 'module' keyword
    body: int          # index just after the ';' that ends the header
    end: int           # index of 'endmodule'


def modules(toks):
    out = []; i = 0
    while i < len(toks):
        t = toks[i]
        if t.kind == "id" and t.text in ("module", "macromodule"):
            j = i + 1
            while toks[j].kind == "comment": j += 1
            name = toks[j].text; k = j + 1; seg = k             # `module m import p::*; (ports);` has two ';' in its header
            while k < len(toks):
                if toks[k].kind == "op" and toks[k].text == ";":
                    if toks[seg].text == "import": seg = k + 1; k += 1; continue
                    break
                k = group_end(toks, k) if toks[k].kind == "op" and toks[k].text in ("(", "[", "{") else k + 1
            e = i
            while e < len(toks) and not (toks[e].kind == "id" and toks[e].text == "endmodule"): e += 1
            out.append(Module(name, i, k + 1, e)); i = e
        i += 1
    return out


def procedural_regions(toks, lo, hi):
    """[(start, end)] of every always / initial / final statement between lo and hi."""
    out = []; i = lo
    while i < hi:
        t = toks[i]
        if t.kind == "id" and t.text in PROC_STARTS:
            e = stmt_end(toks, i); out.append((i, e)); i = e; continue
        i += 1
    return out


def at_statement_start(toks, i, lo=0):
    """True when the token at i can begin a statement (after begin, ';', else, ')' of an if / event control, a case label ...)."""
    j = i - 1
    while j >= lo and toks[j].kind == "comment": j -= 1
    if j < lo: return True
    p = toks[j]
    if p.kind == "op" and p.text in STMT_PREV or (p.kind == "id" and p.text in ("begin", "else", "end")): return True
    if p.text == "(" and toks[j - 1].text == "for": return True
    if p.kind == "num" and toks[j - 1].text == "#": return True
    return False


def assignments_in(toks, lo, hi):
    """[(name, start, op)] for every statement between lo and hi that assigns (=, <=, op=, ++, --): the target's name, the index
    of its first token and the index of the assignment operator."""
    found = []; i = lo
    prev_ok = lambda k: at_statement_start(toks, k, lo)
    while i < hi:
        t = toks[i]
        if t.kind == "op" and t.text in ("++", "--") and toks[i + 1].kind == "id" and prev_ok(i): found.append((toks[i + 1].text, i + 1, i)); i += 2; continue
        if t.kind == "op" and t.text == "{" and prev_ok(i):
            e = group_end(toks, i)
            if e < hi and toks[e].text in ASSIGN_OPS:
                for k in range(i + 1, e - 1):
                    if toks[k].kind == "id" and toks[k + 1].text in (",", "}", "[") and toks[k - 1].text not in (".",): found.append((toks[k].text, i, e))
            i = e; continue
        if t.kind == "id" and prev_ok(i) and t.text not in ("if", "for", "while", "case", "begin", "end", "else", "return", "assign", "repeat", "forever"):
            j = i + 1
            while j < hi and toks[j].kind == "op" and toks[j].text in ("[", "."):
                j = group_end(toks, j) if toks[j].text == "[" else j + 2
            if j < hi and toks[j].kind == "op" and toks[j].text in ASSIGN_OPS: found.append((t.text, i, j))
        i += 1
    return found


def targets_in(toks, lo, hi):
    """Names assigned between lo and hi, with the index of each target."""
    found = {}
    for name, start, _ in assignments_in(toks, lo, hi): found.setdefault(name, start)
    return found


def procedural_targets(toks, m):
    """Names that are assigned inside always / initial blocks of module m (they must be `reg`)."""
    names = set()
    for a, b in procedural_regions(toks, m.body, m.end): names |= set(targets_in(toks, a, b))
    return names


TYPE_NOISE = {"signed", "unsigned", "integer", "int", "logic", "bit", "byte", "shortint", "longint", "reg"}


def parameter_env(toks, lo=0, hi=None):
    """{name: integer} of the parameters and localparams between lo and hi whose values are constant expressions."""
    env = {}; hi = len(toks) if hi is None else hi; i = lo
    while i < hi:
        t = toks[i]
        if t.kind == "id" and t.text in ("parameter", "localparam"):
            j = i + 1
            while j < hi:
                if toks[j].kind == "op" and toks[j].text == "[": j = group_end(toks, j); continue
                if toks[j].kind == "id" and toks[j].text in TYPE_NOISE and toks[j + 1].text != "=": j += 1; continue
                break
            while j < hi and toks[j].kind == "id" and toks[j + 1].text == "=":              # NAME = value {, NAME = value}
                k = j + 2; depth = 0
                while k < hi and not (depth == 0 and toks[k].text in (",", ";", ")") and toks[k].kind == "op"):
                    depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(toks[k].text, 0) if toks[k].kind == "op" else 0; k += 1
                v = evaluate(toks[j + 2:k], env)
                if v is not None: env[toks[j].text] = v
                j = k + 1 if toks[k].text == "," and toks[k + 1].kind == "id" and toks[k + 2].text == "=" else k
                if j == k: break
            i = j
        i += 1
    return env
