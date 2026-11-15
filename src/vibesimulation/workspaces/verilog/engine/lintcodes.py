"""Warning codes in the style of Verilator (%Warning-WIDTH ...), so a message here can be matched with the one a professional tool prints.

`tag(message)` puts the code in front; `Config.off` is the set of codes the user switched off (like `verilator -Wno-WIDTH` / `// verilator lint_off WIDTH`)."""
import re

CODES = {
    "WIDTH": "A value is wider or narrower than where it is stored or compared",
    "UNUSED": "A signal or input is never used",
    "UNDRIVEN": "A signal is read but nothing drives it",
    "BLKSEQ": "Blocking assignment '=' in a clocked block",
    "COMBDLY": "Non-blocking assignment '<=' in a combinational block",
    "SENSITIVITY": "A signal read in an always block is missing from its sensitivity list (use @*)",
    "OTHER": "Anything else",
}
_RULES = (("WIDTH", re.compile(r"bit value is stored|comparing a|bit\(s\) but is connected|lost")), ("UNUSED", re.compile(r"never used|driven but never")),
          ("UNDRIVEN", re.compile(r"never driven|nothing drives|undriven")), ("BLKSEQ", re.compile(r"assigned with '=' in a clocked block")),
          ("COMBDLY", re.compile(r"'<=' in a combinational block")), ("SENSITIVITY", re.compile(r"sensitivity list")))


class Config:
    off = set()


def code_of(msg):
    return next((c for c, rx in _RULES if rx.search(msg)), "OTHER")


def tag(msg):
    return f"[{code_of(msg)}] {msg}"


def keep(msg):
    """False when the user switched this kind of warning off."""
    return code_of(msg) not in Config.off
