# FloorArea

Run **RUTFloorArea** in Rhino 8, or run `FloorArea.py` in the Python 3 Script Editor.
The floating aqua window follows the current selection and allows normal Rhino
modeling and navigation. It refreshes after selection changes, edits, transforms,
deletion, Undo/Redo, block-definition changes and document-unit changes. During an
edit, old totals and Copy actions are cleared until recalculation finishes.
With nothing selected, it clears all measurements and asks you to select solids
or blocks. Running the command again brings the existing window forward.

The window shows horizontal section area above each solid's local base, base
plane area, percentage reduction, and solid/base-face/section-loop counts. The
section height starts at 1.5 metres. Use the −/+ buttons to change it by 0.1 m,
or click the number to type a value. The height label uses normal body-size type.
Units are m², km² or ha; precision ranges from 0–6 decimal places, initially 2.
The selection summary describes valid, closed solids and distinguishes contents
of selected blocks. Copy buttons copy the numeric value at the displayed unit and precision, and
keep the window open. Copy success or failure appears in the footer.

If any selected geometry cannot be measured fully, **all totals are withheld**
and both Copy buttons are disabled. Reasons appear in a scrollable coral list
with object/block names and short IDs. Temporary coral outlines mark the actual
faulty geometry, including transformed block contents. For valid selections,
aqua outlines show the counted section loops. A solid too short to reach the
section height is an error here, even if QuickFloorArea can measure its base.

Only the header **×** closes the window during normal use. Copy, Enter and Escape
keep it open. Closing its Rhino document also closes it. Closing removes temporary
overlays, event subscriptions and the refresh timer. Settings last only while the
window is open; reopening resets them. Nothing is shared with QuickFloorArea.

The geometry scope and base-area method match [QuickFloorArea](QuickFloorArea.md).
Each solid contributes separately, without merging overlapping bases. Blocks may
be nested; non-Brep decoration is ignored, while open/invalid Breps invalidate
the selection. No document geometry, attributes, colours or layers are changed.

Alias/toolbar macro:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\FloorArea.py"
```

Keep `floor_area.py`, `urbanism_ui.py` and `viewport_ui.py` alongside the script.

## Validation

On 2026-11-10, 31 checks in `test_floor_area_rhino.py` passed in Rhino 8,
covering base-only measurement, short/open/no-base solids, nested nonuniform
block transforms, millimetre conversion, warning cleanup, native Copy/Escape/×,
selection and geometry updates, definition edits, default resets and window sizing.
The height controls were checked through native −/+ button clicks and typed
numeric input using the current locale's decimal separator.
Five further live checks verified the FloorArea alias, repeated invocation,
clipboard failure feedback and cleanup. Results and actual window captures are
in `work/floor-area-validation/`.

The quick alias was also run directly in Rhino. Warning cancellation was checked
at the native prompt, and selected faulty geometry was visually checked for coral
outlines. Test geometry was removed; selection, clipboard and camera were restored.
