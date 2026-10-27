"""One entry of the Settings page: category, label, explanation and a factory that makes the control."""


def D(cat, label, desc, make):
    return dict(cat=cat, label=label, desc=desc, make=make)
