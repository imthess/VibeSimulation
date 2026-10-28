"""TokenEditor (Builder): features describe their edits against the original token list; ``build`` applies them all at once.

``replace(i, j, new)`` swaps tokens i..j-1, ``insert(i, new)`` adds before token i, ``delete(i, j)`` removes. Edits may not overlap."""
from ..verilog.lexer import VError
from .lexer import Tok, lex


def toks(text, line):
    """Tokens of a snippet of text, all placed on `line` (used to write the replacement for something)."""
    out = [t for t in lex(text) if t.kind != "eof"]
    for t in out: t.line = line
    return out


class TokenEditor:
    def __init__(self, tokens): self.tokens, self.edits = tokens, []

    def replace(self, i, j, new): self.edits.append((i, j, list(new)))

    def insert(self, i, new): self.edits.append((i, i, list(new)))

    def delete(self, i, j): self.edits.append((i, j, []))

    def __bool__(self): return bool(self.edits)

    def build(self):
        out, pos = [], 0
        for k, (i, j, new) in sorted(enumerate(self.edits), key=lambda e: (e[1][0], e[1][1], e[0])):
            if i < pos: raise VError("two rewrites of SystemVerilog overlap here; split the statement in two", self.tokens[min(i, len(self.tokens) - 1)].line)
            out.extend(self.tokens[pos:i]); out.extend(new); pos = j
        out.extend(self.tokens[pos:])
        return out
