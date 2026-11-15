"""$random and friends, with the algorithm of the Verilog standard (rtl_dist_uniform), so the numbers match other simulators."""
import math
import struct

_D = 0.00000011920928955078125            # 2 ** -23


def step(seed):
    """One draw: (new seed, signed 32-bit value). A seed of 0 starts from the standard's constant."""
    if seed == 0: seed = 259341593
    seed = (69069 * seed + 1) & 0xFFFFFFFF
    f = struct.unpack("<f", struct.pack("<I", (seed >> 9) | 0x3F800000))[0]       # a float in [1, 2) made from the top bits
    c = f + f * _D
    r = (2147483648.0 - (-2147483648.0)) * (c - 1.0) + (-2147483648.0)
    v = math.floor(r)
    return seed, max(-2147483648, min(2147483647, v))


class Random:
    def __init__(self, seed=0): self.seed = seed & 0xFFFFFFFF; self.useed = 0

    def random(self, seed=None):
        """$random; with a seed given, returns (value, new seed) for the caller to store back."""
        if seed is not None:
            s, v = step(seed & 0xFFFFFFFF); return v, (s - (1 << 32) if s >> 31 else s)
        self.seed, v = step(self.seed); return v, None

    def urandom(self):
        self.useed, v = step(self.useed); return v & 0xFFFFFFFF

    def urandom_range(self, hi, lo=0):
        if hi < lo: hi, lo = lo, hi
        return lo + self.urandom() % (hi - lo + 1)
