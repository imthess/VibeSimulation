"""SystemVerilog support: the text is *lowered* to the Verilog subset that the rest of the program already understands.

Why lowering: the Verilog elaborator, simulator, circuit drawing and testbench runner stay the single place where hardware meaning
is decided; SystemVerilog is a front end that rewrites its conveniences (``logic``, ``always_ff``, ``enum``, packed ``struct``,
packages, ``++`` ...) into plain Verilog. Lowering keeps every token on its original line, so an error found later is reported
on the line the user wrote.

Design patterns and where they live
- Facade ............ ``compiler.py``   ``lower(text)`` is the one call the rest of the program makes.
- Pipeline / Chain .. ``pipeline.py``   the features run one after another over a shared Context.
- Registry .......... ``feature.py``    a feature registers itself with ``@feature``; ``features/__init__`` finds every file, so adding
                                          a file is the only step needed to add a feature (Open/Closed).
- Template Method ... ``feature.py``    ``Feature.run`` = ``applies`` + ``apply``; each feature fills in ``apply``.
- Builder ........... ``editor.py``     ``TokenEditor`` collects edits, then builds the new token list (no feature edits a list while walking it).
- Flyweight table ... ``typetable.py``  one table of user-defined types shared by the enum, struct and typedef features.
- Verifier .......... ``features/leftover.py``  the last feature refuses anything that is still SystemVerilog.

Files (one feature per file in ``features/``)
  lexer.py scan.py editor.py consteval.py analysis.py context.py feature.py typetable.py pipeline.py compiler.py
  features/: preprocess, unsupported, end_labels, qualifiers, unique_priority, typed_params, packages, enums, structs, typedefs,
             always_blocks, logic_types, for_decl, compound_ops, inside_op, casts, fill_literals, functions, severity_tasks,
             assertions, port_shorthand, leftover
"""
