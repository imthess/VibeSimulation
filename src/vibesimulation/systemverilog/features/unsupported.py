"""Says plainly which SystemVerilog constructs are not available yet (instead of failing with a confusing Verilog message)."""
from ..feature import Feature, feature

MESSAGES = {
    "interface": "interfaces are not supported yet: declare the ports of the module directly",
    "modport": "modports are not supported yet",
    "class": "classes are not supported (VibeSimulation draws hardware)",
    "program": "program blocks are not supported",
    "covergroup": "coverage groups are not supported",
    "clocking": "clocking blocks are not supported",
    "property": "properties and concurrent assertions are not supported (immediate `assert (cond)` is)",
    "sequence": "sequences are not supported",
    "checker": "checkers are not supported",
    "randomize": "randomisation is not supported",
    "constraint": "constraints are not supported",
    "fork": "fork / join is not supported",
    "mailbox": "mailboxes are not supported",
    "semaphore": "semaphores are not supported",
    "string": "the string type is not supported",
    "chandle": "DPI handles are not supported",
    "import \"DPI-C\"": "DPI imports are not supported",
    "bind": "bind is not supported",
    "alias": "alias is not supported",
    "foreach": "foreach is not supported yet: use a for loop",
    "break": "break is not supported yet",
    "continue": "continue is not supported yet",
    "do": "do ... while is not supported yet: use a while loop",
}


@feature
class Unsupported(Feature):
    name = "unsupported"
    summary = "a clear message for the SystemVerilog parts that are not available"
    order = 5
    triggers = tuple(MESSAGES)

    def apply(self, ctx):
        for t in ctx.tokens:
            if t.kind == "id" and t.text in MESSAGES: ctx.fail(t.line, f"SystemVerilog: {MESSAGES[t.text]}")
