"""What a testbench run gives back."""
from dataclasses import dataclass, field


@dataclass
class TBResult:
    lines: list = field(default_factory=list)       # everything $display / $write / $monitor / $strobe printed
    waves: dict = field(default_factory=dict)       # signal -> [(time, value)] , one entry per change
    widths: dict = field(default_factory=dict)      # signal -> bits
    order: list = field(default_factory=list)       # signals in the order they were declared
    kinds: dict = field(default_factory=dict)       # signal -> "input" (testbench drives the circuit) | "output" | "variable"
    end_time: int = 0
    finished: bool = False                          # $finish was reached
    truncated: str = ""                             # why the run was cut short (time limit / step limit), "" if it ended by itself
    warnings: list = field(default_factory=list)    # [(line, text)] from building the circuit part
    error: object = None                            # VError, when the run stopped on a mistake

    @property
    def text(self): return "\n".join(self.lines)
