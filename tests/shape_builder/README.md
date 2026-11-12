# Shape Builder tests

Run `run_rhino.py` in Rhino 8's Python 3 Script Editor or through Rhino MCP.
It runs all seven suites in disposable headless documents and checks that the
active drawing's objects, attributes, and selection remain unchanged. JSON
reports go to `work/`. Run the complete suite after changing the command or helpers.

The tests load `ShapeBuilder.py` directly; the old prototype launcher is not involved.

## Coverage


`tests/shape_builder/test_shape_builder_rhino.py` runs geometry tests in a disposable headless Rhino
document and writes `work/shape-builder-tests.json`. The latest run passed 73 checks:
overlaps, merge/erase/undo state, narrow regions, open line networks, holes, duplicate
and shared edges, tangent and overlapping circles, disconnected shapes, concave and
self-intersecting outlines, tilted planes, boundary accuracy, and invalid inputs.

`tests/shape_builder/test_shape_builder_hatches_rhino.py` adds 40 checks for hatch boundary extraction,
holes with dividing curves, mixed inputs, style preservation, tilted hatch planes,
unchanged curve/hatch types, original replacement, Keep originals, live drag outline
generation, changed-source rejection, and rollback after an injected deletion failure.
Results are written to `work/shape-builder-hatch-tests.json`.

`tests/shape_builder/test_shape_builder_masters_rhino.py` adds 17 checks for drag direction, layer,
pattern, rotation, scale, existing merged masters, chained merges, and Undo after
merging or erasing.

`tests/shape_builder/test_shape_builder_types_rhino.py` adds 37 checks for curve-start and hatch-start
merges, selection-order independence, mixed output in one session, inherited layers,
chained type changes, and Undo.

`tests/shape_builder/test_shape_builder_leftovers_rhino.py` adds 49 checks for gesture-aware trimming,
untouched identity, external excursions, exact arcs, tilted planes, custom parameter
domains, preview updates, explicit extraction of open-only regions, attributes,
Keep originals, Undo, and rollback.

`tests/shape_builder/test_shape_builder_edge_erase_rhino.py` adds 33 checks for click/drag edge
targeting, intersection limits, polyline corners, exact arcs, coincident edges,
zoom-dependent hover tolerance, erasing without selecting regions, pending preview,
later edits, stroke Undo, and committed output.

`tests/shape_builder/test_shape_builder_attributes_rhino.py` adds 119 checks for open-curve master
provenance, object and layer colors, other copied attributes, unrelated inputs,
multiple boundary contributors, curve-start merging, and Undo. The seven suites
total 368 passing checks. The orange open curve in the user's actual drawing was
also checked through output preparation: its closed result inherited the source
color and layer, with all existing drawing objects and attributes unchanged.

The native command version was tested live on Windows/Rhino: fixed panel rendering,
command-line KeepOriginals, mouse dragging, Enter and Space completion,
SelLast rejection, Ctrl+Z stroke Undo, replacement, document Undo/Redo, and Escape.
A timer audit during the command recorded no document changes or selected objects
while clicking unrelated geometry and using Undo with no strokes to undo.
The revised output rule was tested live using two circle/hatch pairs: one curve-start
drag and one hatch-start drag produced a curve and a hatch together, on the correct
master layers. Document Undo/Redo restored both types correctly. Temporary test
objects were removed and the previous view and selection restored afterwards.
The leftover preview was also inspected live using an outside polyline excursion
like the user's example. Finish produced one hatch and two open fragments on the
correct source layer with user text intact. One Undo restored the full source
polyline; Redo restored the fragments. The temporary fixtures were removed and the
original drawing, view, and selection restored.
The real-viewport mouse callback was exercised with an erase-mode stroke across a
bent outside tail. The pending edge highlighted coral without selecting the hatch;
Finish removed it and retained the hatch and opposite tail. Document Undo/Redo and
cleanup were verified. The callback was driven in erase mode programmatically;
the physical Alt modifier was not independently driven by desktop automation.
Alt-drag's physical modifier has not been separately automated; erase geometry is
covered by the automated suites.
