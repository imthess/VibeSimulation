"""PNG picture of an analog schematic."""
from vibesimulation.common.png_writer import LIGHT, PilRenderer, canvas


def analog_png(netlist, layout=None, scale=1.5, pad=30, palette=LIGHT, bg="#ffffff"):
    """Picture of an analog schematic (``analog.netlist.Netlist``). Returns a Pillow image."""
    from vibesimulation.workspaces.multisim.layout.schematic_layout import SchematicBuilder
    from vibesimulation.workspaces.multisim.layout.painter import paint_schematic
    layout = layout or SchematicBuilder().build(netlist)
    im, d, tf = canvas(layout.extent(), scale, pad, bg)
    paint_schematic(PilRenderer(d, tf, scale, palette), layout, None, 4, tagged=False)
    return im
