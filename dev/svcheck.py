"""SystemVerilog source: iverilog (-g2012) runs the SystemVerilog itself, we run its lowering; every output must agree."""
import sys
sys.path.insert(0, "dev"); sys.path.insert(0, "src")
from vcheck import compare
from vibesimulation.systemverilog.compiler import lower


def check(sv, top, nvec=80, seed=1, **kw):
    """-> (mismatches, values compared)"""
    return compare(lower(sv).verilog, top, nvec, seed, ref_src=sv, std="2012", **kw)
