"""One folder per workspace of the app. Each has its engine (the model and the maths) and the pieces of its window, sorted by what they are:

- ``logisim/``        digital logic: ``circuit/`` (the drawing), ``json_view/``, ``truth_table/``, ``circ_file/`` (Logisim .circ files)
- ``multisim/``        analog circuits: ``engine/`` (solver), ``schematic/``, ``json_view/``, ``results/`` (DC, AC, transient, sweeps ...), ``spice_file/``
- ``verilog/``         Verilog: ``engine/`` (language), ``project/`` (document), ``editor/``, ``circuit/``, ``truth_table/``, ``simulation/`` (Run, waveforms, settings)
- ``systemverilog/``   SystemVerilog: ``engine/`` (lowering to Verilog), ``editor/``; reuses the Verilog window
- ``ai_import/``       picture to circuit: ``engine/`` (providers, prompt, key detection), ``ui/``, ``settings/``

Shared by all of them: ``core/`` (digital model), ``components/``, ``layout/``, ``export/``, ``imports/`` (opens any file), ``product/``, ``ui/`` (window shell)."""
