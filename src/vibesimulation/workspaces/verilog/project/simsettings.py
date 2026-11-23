"""Simulation settings of the Verilog / SystemVerilog sections, modelled on what Icarus Verilog, Verilator and Vivado's xsim ask for.

The settings object is plain data (`to_dict` / `from_dict`); `commands()` writes the command lines a professional tool would be given for the same
settings, so someone moving on to those tools sees the same options under their usual names."""
from dataclasses import dataclass, field


@dataclass
class SimSettings:
    top: str = ""                     # -s / --top-module : simulate this module ("" = automatic: the written testbench or a generated one)
    standard: str = "auto"            # auto | 2001 | 2005 | 2012   (-g2005 / -g2012, --language 1800-2017)
    defines: dict = field(default_factory=dict)       # -DNAME[=value]
    incdirs: list = field(default_factory=list)       # -I folder
    timescale: str = "1ns/1ps"        # `timescale for the VCD and for the commands
    max_time: int = 200000            # stop after this many time units (like  $finish  that never came)
    cycles: int = 64                  # clock cycles of a generated testbench
    period: int = 10                  # clock period of a generated testbench
    stimulus: str = "random"          # generated testbench: random | count
    dump_vcd: bool = True             # write dump.vcd after a run (like $dumpfile / $dumpvars)
    lint_off: list = field(default_factory=list)      # warning codes switched off (-Wno-CODE)

    def to_dict(self): return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, d):
        s = cls()
        for k, v in (d or {}).items():
            if k in cls.__dataclass_fields__ and v is not None: setattr(s, k, v)
        return s

    def problems(self):
        out = []
        if self.max_time < 1: out.append("the time limit must be at least 1")
        if self.cycles < 1: out.append("the number of cycles must be at least 1")
        if self.period < 2: out.append("the clock period must be at least 2")
        if self.standard not in ("auto", "2001", "2005", "2012"): out.append("choose a language standard")
        if self.stimulus not in ("random", "count"): out.append("stimulus must be random or count")
        return out

    def commands(self, files=("design.v",), sv=False, tb_top=None):
        """{'Icarus Verilog': [...], 'Verilator': [...], 'Vivado xsim': [...]} the same run as shell commands."""
        std = self.standard if self.standard != "auto" else ("2012" if sv else "2005")
        defs = [f"-D{k}" + (f"={v}" if v not in ("", None) else "") for k, v in self.defines.items()]
        inc = [f"-I{d}" for d in self.incdirs]; top = self.top or tb_top or "tb"; f = " ".join(files)
        iv = ["iverilog -g" + std + " " + " ".join(defs + inc + ["-s", top, "-o", "sim.vvp", f]).replace("  ", " "), "vvp sim.vvp" + (" -lxt2" if False else "")]
        ver = ["verilator --binary --trace --timing " + " ".join([f"--top-module {top}"] + [f"-D{k}" + (f"={v}" if v not in ("", None) else "") for k, v in self.defines.items()] + inc
               + ["--language 1800-2017" if std == "2012" else "--language 1364-2005"] + [f"-Wno-{c}" for c in self.lint_off] + [f]),
               f"./obj_dir/V{top}"]
        vv = ["xvlog " + ("-sv " if sv or std == "2012" else "") + " ".join(defs and [f"-d {x[2:]}" for x in defs] + [f]), f"xelab {top} -s sim -timescale {self.timescale}", "xsim sim -runall"]
        return {"Icarus Verilog (iverilog + vvp)": iv, "Verilator": ver, "Vivado xsim": vv}

    def commands_text(self, **kw):
        out = []
        for tool, cmds in self.commands(**kw).items(): out += [f"# {tool}"] + cmds + [""]
        return "\n".join(out).rstrip() + "\n"


def parse_defines(text):
    """'WIDTH=8' / 'FAST' per line (or separated by spaces / commas, with an optional leading -D) -> {name: value}"""
    out = {}
    for tok in text.replace(",", " ").split():
        tok = tok[2:] if tok.startswith("-D") else tok
        if not tok: continue
        k, _, v = tok.partition("=")
        if not k.replace("_", "a").replace("$", "a").isalnum() or k[0].isdigit(): raise ValueError(f"'{k}' is not a valid macro name")
        out[k] = v
    return out


def format_defines(d): return "\n".join(k + (f"={v}" if v not in ("", None) else "") for k, v in d.items())
