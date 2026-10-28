"""Running testbenches: Verilog with `initial` blocks, delays, $display and friends.

    from vibesimulation.verilog.tb import run_testbench, find_testbenches
    result = run_testbench(text)             # TBResult: result.text, result.waves, ...

A testbench is a module with processes (see split.py). Its circuit part is built like any other module and run by the
normal simulator; its program part is interpreted (interp.py) in time order (scheduler.py).
"""
from ..lexer import VError
from ..parser import parse_modules
from .result import TBResult
from .scheduler import Simulation
from .split import has_processes


def find_testbenches(text):
    """Names of the modules of `text` that are testbenches."""
    mods, _ = parse_modules(text)
    return [m.name for m in mods if has_processes(m)]


def run_testbench(text, top=None, max_time=100000, max_steps=2000000):
    """Parse, build and run. A mistake in the text comes back as result.error (never raised)."""
    try:
        mods, _ = parse_modules(text)
        tbs = [m.name for m in mods if has_processes(m)]
        if top is None:
            if not tbs: raise VError("there is no testbench in this text: a testbench is a module with an `initial` block, or an `always` block with a delay (#) or a $display", 1)
            top = tbs[-1]
        elif top not in [m.name for m in mods]: raise VError(f"there is no module '{top}'", 1)
        return Simulation(mods, top, max_time, max_steps).run()
    except VError as e:
        r = TBResult(); r.error = e; return r
