# QuickArea

Run `QuickArea.py` in Rhino 8's ScriptEditor using Python 3. Keep
`urbanism_ui.py` beside it; this shared module supplies the aqua drawing-office
appearance and can also be used by the other scripts.

## Interaction

- Compatible preselected objects are measured immediately. With nothing
  preselected, the command starts Rhino's normal viewport selection directly.
  There is no opening confirmation or settings window. This is the interaction
  convention for toolkit commands that have no configurable settings.
- Section height defaults to 1.5 metres above each local base. **Change height**
  temporarily hides the result and asks for a positive height in metres on
  Rhino's command line. Accepting recalculates the same objects and updates the
  preview. Cancelling retains the current result. The height is remembered for
  the rest of the Rhino session, including subsequent invocations.
- If open/invalid geometry is present, choose whether to tag skipped objects in
  the model. Tagging is off by default. Cancel stops the calculation.
- The result shows section area, base area, reduction, solid count, base-face
  count and loop count. Area units can be **m²**, **km²** or **hectares (ha)**;
  conversion accounts for the document's model units, including millimetres.
  Three directly accessible buttons replace the unit dropdown; the active unit
  uses the aqua accent fill.
  Rounded integer rows are omitted. The **Decimal places**
  slider ranges from 0 to 6 and starts at 2 each time. It formats section/base
  areas and the percentage from the full-precision calculation.
- **Copy section area** and **Copy base plane area** copy their respective
  numeric values at the selected precision and area unit. **Close** dismisses
  the result. Copying closes the result after a successful copy; clipboard errors
  keep it open with feedback. The footer is hidden
  until there is feedback to display.
- While the result is open, the exact counted section loops are highlighted in
  the aqua palette's accent colour in model viewports. The result allows viewport navigation. The highlight
  includes courtyard loops and is an overlay, not document geometry. It is
  disabled and its curves released on Close, Escape, the header close button, or
  an exception.
- Enter activates the default action; Escape cancels/closes the dialog.
- In the section-issues window, click an object's button to select that object
  in Rhino while keeping the window open. Entries use the object/block name
  when available and group multiple reasons under one entry. Missing, hidden
  or locked objects produce feedback without clearing the prior selection.

The native Eto controls share the approved reference's light and dark palettes,
selected from Rhino's appearance when each command runs. In dark mode the
surface gradients from `#223138` to `#294944`, panels use `#263b43`, and primary
actions use `#b1e4df`. The light palette uses paper and pale aqua surfaces with
teal actions. Information panels have 8-pixel corners; buttons have 6-pixel
corners. Windows buttons retain their native keyboard and accessibility behavior
through a WPF template; other platforms retain native button styling.

Typography uses Segoe UI with consistent caption, body, heading and result-value
roles (12, 14, 24 and 32 effective pixels). Labels use sentence case and regular
weight. Section and comparison values occupy separate rounded information
panels. This follows the hierarchy and casing guidance in
[Fluent typography](https://fluent2.microsoft.design/typography).

Dialogs use a frameless window with 12-pixel outer corners and an in-panel close button. Drag the header
to move the window; Close, Escape and the header close button remain available. Closing
a warning via the header is equivalent to Cancel. The default action receives
keyboard focus on opening. Windows information panels use native rounded
borders with layout rounding so the complete outline remains visible at
fractional display scaling.
The native Windows window region is also rounded, cutting off the rectangular
backing outside the corners rather than only clipping the painted content.

## Validation

Live checks were run via MCP in the user's open Rhino 8.36 instance on
2026-10-23. The integration scripts are `work/test_quickarea_ui_rhino.py` and
`work/test_quickarea_pick_rhino.py`; they require the MCP-injected
`__rhino_doc__`. They create and remove their own fixtures and restore the
previous selection. Clipboard testing snapshots and restores clipboard formats.

Verified a box (80 m²), a tapered volume (68 m² section, 80 m² base, 15% reduction),
mixed open/closed selection, warning cancellation, warning choices,
clipboard output/confirmation, and direct viewport selection with no opening
dialog. Updated checks cover 0/2/4 decimal display and clipboard output, actual
viewport drawing, overlay cleanup on Done and header close, and rounded window
transparency. Further checks cover model-unit-aware area conversion, both copy
buttons, changing height through the actual command-line prompt, recalculating
the same selection, and remembering that height on the next invocation.
Test fixtures, selection, viewport and prior height preference are restored.
`work/test_quickarea_window_region_rhino.py` additionally checks that the native
window region excludes all four corner pixels and that cancelling a height
prompt keeps the existing result open.
The user's selected block also returned 12 m² without modifying its geometry.
Live dialog renderings are saved in `work/quickarea-ui/` for visual inspection.

Only the source scripts were updated; no package was published or rebuilt.

The issues list uses a slim, rounded aqua scrollbar on Windows, matching the
rest of the interface while retaining native scrolling behavior.

When geometry is excluded, the result keeps a warning below the section height:
for example, “6 of 8 selected objects excluded from totals.” If all section
failures are missing sections, it also reports the current height. Blocks with
both counted and uncounted contents are described as partly counted. The footer
counts successful solids only. Uncounted solids have temporary coral wire outlines
while the result is open; aqua still marks the counted section loops. Both overlays
clear on Close, either Copy action, or recalculation, without changing object colours.
