"""Walking a token list: matching brackets, matching begin/end, and finding where a statement ends."""
from ..verilog.lexer import VError

PAIRS = {"(": ")", "[": "]", "{": "}", "'{": "}"}
BLOCKS = {"begin": "end", "case": "endcase", "casez": "endcase", "casex": "endcase", "fork": "join", "function": "endfunction", "task": "endtask",
          "module": "endmodule", "generate": "endgenerate", "package": "endpackage", "interface": "endinterface"}


def is_(t, *texts): return t.kind in ("id", "op") and t.text in texts


def group_end(toks, i):
    """Index just after the bracket group that opens at i."""
    close = PAIRS[toks[i].text]; depth = 0
    for j in range(i, len(toks)):
        t = toks[j]
        if t.kind != "op": continue
        if t.text in PAIRS: depth += 1
        elif t.text in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                if t.text != close: raise VError(f"'{toks[i].text}' is closed by '{t.text}'", t.line)
                return j + 1
    raise VError(f"'{toks[i].text}' is never closed", toks[i].line)


def block_end(toks, i):
    """Index just after the keyword block (begin..end, case..endcase ...) that opens at i."""
    opener = toks[i].text; closer = BLOCKS[opener]; same = {"case", "casez", "casex"} if opener.startswith("case") else {opener}; depth = 0
    for j in range(i, len(toks)):
        t = toks[j]
        if t.kind != "id": continue
        if t.text in same: depth += 1
        elif t.text == closer:
            depth -= 1
            if depth == 0: return j + 1
    raise VError(f"'{opener}' is never closed (missing '{closer}')", toks[i].line)


def semi_end(toks, i):
    """Index just after the next ';' that is not inside brackets."""
    j = i
    while j < len(toks):
        t = toks[j]
        if t.kind == "op" and t.text in PAIRS: j = group_end(toks, j); continue
        if t.kind == "op" and t.text == ";": return j + 1
        if t.kind == "eof": break
        j += 1
    raise VError("a ';' is missing", toks[min(i, len(toks) - 1)].line)


def skip_comments(toks, i):
    while toks[i].kind == "comment": i += 1
    return i


def stmt_end(toks, i):
    """Index just after the statement that starts at i (if/else, loops, begin..end, case, event controls and plain statements)."""
    i = skip_comments(toks, i); t = toks[i]
    if t.kind == "id":
        w = t.text
        if w == "begin": return block_end(toks, i)
        if w in ("case", "casez", "casex"): return block_end(toks, i)
        if w == "if":
            j = stmt_end(toks, group_end(toks, i + 1)); k = skip_comments(toks, j)
            return stmt_end(toks, k + 1) if toks[k].kind == "id" and toks[k].text == "else" else j
        if w in ("for", "while", "repeat", "foreach"): return stmt_end(toks, group_end(toks, i + 1))
        if w in ("forever", "initial", "always", "always_comb", "always_ff", "always_latch", "final"): return stmt_end(toks, i + 1)
    if t.kind == "op" and t.text == "@":
        j = i + 1
        if toks[j].text == "*": return stmt_end(toks, j + 1)
        if toks[j].text == "(": return stmt_end(toks, group_end(toks, j))
        return stmt_end(toks, j + 1)
    if t.kind == "op" and t.text == "#":
        j = i + 1
        if toks[j].text == "(": return stmt_end(toks, group_end(toks, j))
        return stmt_end(toks, j + 1)
    return semi_end(toks, i)
