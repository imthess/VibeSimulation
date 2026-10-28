"""The state shared by the features of one lowering run."""
from ..verilog.lexer import VError
from .editor import TokenEditor
from .typetable import TypeTable


class Context:
    def __init__(self, text, known=None):
        self.text, self.tokens = text, []
        self.known = known or {}       # module name -> port names, for modules that are not in this text (other circuits of the project)
        self.warnings = []             # [(line, message)]
        self.types = TypeTable()
        self.used = []                 # names of the features that changed something (shown in the output)

    def warn(self, line, msg):
        if (line, msg) not in self.warnings: self.warnings.append((line, msg))

    def fail(self, line, msg): raise VError(msg, line)

    def editor(self): return TokenEditor(self.tokens)

    def commit(self, editor):
        """Apply the collected edits; returns True when anything changed."""
        if not editor: return False
        self.tokens = editor.build(); return True
