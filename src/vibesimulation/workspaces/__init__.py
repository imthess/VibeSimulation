"""One folder per tab of the app. Each has its engine (the model and the maths) and the pieces of its window, sorted by what they are:

- ``home/``           the Home tab
- ``logisim/``        digital logic. Owns the circuit model (``core/``), parts (``components/``), drawing (``layout/``), ``imports/`` and ``export/``
- ``multisim/``       analog circuits: ``core/`` (model, solver), ``analysis/``, ``components/``, ``layout/``, ``imports/`` (SPICE), ``export/``, panes
- ``verilog/``        Verilog: ``core/`` (language), ``project/``, ``export/``, panes (reuses the Logisim model and drawing)
- ``systemverilog/``  SystemVerilog: ``core/`` (lowering to Verilog), ``editor/``; reuses the Verilog window
- ``ai_import/``      picture to circuit: ``core/`` (providers, prompt, key detection), ``imports/`` (opens any file), ``ui/``
- ``settings/``       the Settings tab: ``page.py``, ``registry.py`` and one folder per setting

Shared by all of them: ``common/`` (drawing interface, wire routing, PDF/PNG writers), ``product/`` (About, gallery, recovery), ``ui/`` (window shell).
"""
