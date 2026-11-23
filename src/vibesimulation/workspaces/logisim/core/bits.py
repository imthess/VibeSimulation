"""Small helpers for working with bit widths and bus values."""


def mask(width):
    return (1 << width) - 1


def clog2(n):
    """Number of bits needed to count n things (ceil(log2(n)), at least 1)."""
    return max(1, (n - 1).bit_length())


def to_signed(value, width):
    return value - (1 << width) if value >> (width - 1) & 1 else value


def fmt(value, width):
    """Text for a value as Logisim shows it: 'E' for an error, 0/1 for one wire, binary digits for a bus."""
    if value is None:
        return "E"
    return str(value) if width == 1 else format(value, "b").zfill(width)
