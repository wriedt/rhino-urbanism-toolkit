# Shape Builder

Rhino 8 Python 3 tool for editing regions enclosed by coplanar curves
and hatches, including mixed selections.

## Run it

Run **RUTShapeBuilder** in Rhino, or open `ShapeBuilder.py` in Rhino's Script Editor.
Select curves or hatches before running the command, or select them when prompted.
If nothing is selected, the script opens Rhino's picker. Curves may be closed or
collectively enclose regions. All inputs must share one plane. Block contents,
reference objects, and locked objects are excluded.

- A fixed, rounded aqua viewport panel matches PushPullCurve's style and location.
  It shows the region counts, curve/hatch result counts, and whether originals will
  be replaced. During dragging it shows the pending result type.
- Separate regions have pale fills and thin grey boundaries. Merged shapes have
  continuous aqua fills and thick outlines; shared edges vanish. There are no tags.
- Hover to highlight a region or an already merged shape in gold. Erase targets
  highlight coral. The pending combined outline also updates during a drag.
- Drag with the left mouse button across regions to merge them.
- Hold Alt while starting a drag to erase crossed regions or remaining open-curve
  edges. Alt-click also erases a targeted open edge. There is no erase toggle.
- **Undo** or Ctrl+Z restores the previous stroke, including its hatch master.
- **Enter**, **Space**, or the command-line **Finish** option accepts the result.
- **KeepOriginals=No** replaces selected originals on Finish. Set it to **Yes** to
  retain them alongside the results. No originals are deleted before Finish.
- The drag-start region determines each merged shape's output type. Start in a
  curve-only area to produce a curve, or in a hatch to produce a hatch. One command
  can produce both types. There is no global output toggle.
- **KeepOriginals** is a native command-line option, mirrored in the panel.
  **Cancel** or Escape discards the preview.

Separate strokes produce separate shapes. Disconnected regions and regions touching
only at a point remain independently selectable. Inner and outer loops of a result
with holes are grouped together. Finishing is one Rhino Undo operation, with Redo.
When a drag leaves its viewport, it ends at the last sampled point.

The operation owns Rhino's native input loop until Finish or Cancel. Other commands,
including transparent commands, are disabled during editing. `SelLast` cannot select
other geometry; Undo is handled internally and cannot reach document history. An
explicit cancellation releases the input loop and removes all previews and hooks.

Original inputs are suppressed by the temporary display conduit during editing,
so their hatch patterns and obsolete internal edges cannot obscure the preview.
Cancel restores their normal display without changing object visibility flags.
Other unselected drawing objects remain visible.

Hatch-only inputs preserve empty holes. Adding open dividing curves does not fill
those holes; closed regions explicitly enclosed by additional curves can contribute
new area. The region where a drag starts is the master: it supplies the output type,
layer, color, and copied object attributes. A hatch master also supplies its pattern,
scale, rotation, plane, base point, and gradient. Starting from an existing merged shape reuses that
shape's stored master, even when the cursor is over a different original hatch's
part. Reversing the drag can therefore change the output type and inherited style.
In an overlap shared by a curve and a hatch, the region initially uses the hatch;
in a hatch/hatch overlap it uses the first selected contributing hatch. Starting in
either shape's exclusive area makes the choice unambiguous. Separate untouched
regions retain their own types and styles. Regions enclosed collectively by open
curves use curve output with the attributes of the open curve contributing the longest
boundary; selection order breaks ties. This includes object/layer color settings,
layer, print settings, material settings, name, and user text. An untouched potential
region still stays open until acted on. Only the originally selected objects are
eligible for replacement. An internal integrity check also guards external/API edits.

## Leftover open curves

Open curves are trimmed only where their spans bound initial regions that a merge,
extraction, or erase gesture actually affects. Unused ends and outside excursions
stay open curves. The calculation uses the affected initial regions, so removed
internal dividers cannot reappear as leftovers after merging.

An untouched region enclosed solely by open curves remains open source geometry;
it is not automatically emitted as a closed curve or hatch. Click or drag through
that potential region explicitly to create a closed result. Inactive potential
regions have no filled preview until hovered or acted on.

Leftovers appear in the preview using their source colors. Output pieces preserve
exact geometry, layer, color, linetype, print properties, name, and user text. An
entirely untouched document curve keeps its original object ID. Partially consumed
curves are replaced by their remaining open fragments. With **KeepOriginals=Yes**,
the whole originals already remain, so no duplicate leftovers are added. Stroke
Undo restores consumption state and preview; document Undo/Redo includes all pieces.

Alt can erase enclosed regions or remaining open-curve edges. Hovering an open edge
with Alt highlights it in coral. Clicking it or dragging across it removes that edge
up to its intersections with other selected geometry (or the source endpoints).
Polyline corners alone do not split an edge. The remaining parts preserve their
source attributes. One stroke can erase multiple crossed edges, and stroke Undo
restores them. Seven screen pixels of hover tolerance makes targeting independent
of document units and zoom. A fast stroke tests the full cursor path between samples.

A dangling curve that never bounds an affected region stays intact unless explicitly
targeted for edge erasing. Only surviving open-source edges are direct edge targets;
closed result outlines are still edited through their regions.

## Limits

No automatic gap closing, nonplanar editing, or restoration of erased
regions except Undo. Model tolerance governs region detection
and output accuracy; Rhino may approximate curved boundaries within that tolerance.
Large architectural drawings have not been performance tested.


## Installation and testing

Keep `ShapeBuilder.py`, `shape_builder_leftovers.py`, and `viewport_ui.py` together.
For an alias or toolbar button, use this Rhino 8 Python 3 macro (adjust the path if needed):

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\ShapeBuilder.py"
```

The old `ShapeBuilderPrototype.py` filename remains as a compatibility launcher.
See [the test guide](tests/shape_builder/README.md) for regression tests and validation.
