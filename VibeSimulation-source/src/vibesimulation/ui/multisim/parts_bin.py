"""The Multisim component database as Multisim shows it: Group > Family > Component.

The groups and families follow Multisim's master database naming (Sources, Basic, Diodes, Transistors, Analog, Indicators); the
parts are the ones VibeSimulation can simulate. Used by the side bar tree, the Place menu and the components toolbar."""
from ...analog import components as AC

BIN = [
    ("Sources", [("POWER_SOURCES", [AC.VoltageSource]), ("SIGNAL_CURRENT_SOURCES", [AC.CurrentSource]),
                 ("CONTROLLED_VOLTAGE_SOURCES", [AC.VCVS, AC.CCVS]), ("CONTROLLED_CURRENT_SOURCES", [AC.VCCS, AC.CCCS])]),
    ("Basic", [("RESISTOR", [AC.Resistor]), ("POTENTIOMETER", [AC.Potentiometer]), ("CAPACITOR", [AC.Capacitor]), ("INDUCTOR", [AC.Inductor]), ("TRANSFORMER", [AC.Transformer]), ("SWITCH", [AC.Switch])]),
    ("Diodes", [("DIODE", [AC.Diode]), ("ZENER", [AC.Zener]), ("LED", [AC.LED])]),
    ("Transistors", [("BJT_NPN", [AC.NPN]), ("BJT_PNP", [AC.PNP]), ("MOS_3TEN", [AC.NMOS]), ("MOS_3TEP", [AC.PMOS]),
                     ("JFET_N", [AC.NJFET]), ("JFET_P", [AC.PJFET]), ("IGBT", [AC.IGBT])]),
    ("Analog", [("OPAMP", [AC.OpAmp])]),
    ("Indicators", [("AMMETER", [AC.Ammeter]), ("VOLTMETER", [AC.Voltmeter])]),
]
LABEL = {"VoltageSource": "Voltage source (DC / AC)", "CurrentSource": "Current source (DC / AC)", "NMOS": "NMOS (N-channel MOSFET)", "PMOS": "PMOS (P-channel MOSFET)",
         "NJFET": "N-channel JFET", "PJFET": "P-channel JFET", "OpAmp": "Op-amp", "NPN": "NPN transistor", "PNP": "PNP transistor", "VCVS": "VCVS", "CCVS": "CCVS", "VCCS": "VCCS", "CCCS": "CCCS"}


def label(cls): return LABEL.get(cls.type_name, cls.type_name)


def fill_group_menu(menu, ctx, group, place):
    """Put the families and parts of one group into a tk menu."""
    fams = dict(BIN)[group]
    for i, (fam, classes) in enumerate(fams):
        if len(fams) > 1 and (len(classes) > 1 or i == 0 and False):
            menu.add_command(label=fam, state="disabled")
        for cls in classes: menu.add_command(label=label(cls), command=lambda c=cls: place(c))
        if len(classes) > 1 and i < len(fams) - 1: menu.add_separator()


def fill_place_menu(menu, ctx, place):
    for g, _ in BIN:
        sub = ctx.menu(); fill_group_menu(sub, ctx, g, place); menu.add_cascade(label=g, menu=sub)
