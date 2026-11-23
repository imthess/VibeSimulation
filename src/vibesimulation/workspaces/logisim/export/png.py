"""PNG picture of a digital circuit (for "download as picture" and for the training pictures in ``dev/finetune``)."""
from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas
from vibesimulation.workspaces.logisim.layout.painter import CircuitPainter, extent


def digital_png(circuit, layout=None, scale=1.5, pad=30, palette=LIGHT, bg="#ffffff", invals=None):
    """Picture of a digital circuit (``core.model.Circuit``). Returns a Pillow image."""
    from vibesimulation.workspaces.logisim.layout.engine import LayoutEngine
    layout = layout or LayoutEngine().build(circuit)
    invals = invals or {}
    im, d, tf = canvas(extent(layout), scale, pad, bg)
    CircuitPainter(PilRenderer(d, tf, scale, palette)).paint(layout, circuit, circuit.simulate(invals), invals)
    return im
