---
name: rhino-script-ui
description: Design, implement, and test consistent Rhino 8 script dialogs, result panels, and viewport feedback using the user's aqua drawing-office conventions. Use for Rhino script UI work, not geometry-only scripting or web interfaces.
---

# Rhino Script UI

Create a consistent experience across script prompts, settings, diagnostics, and
results. The user's approved direction is an architectural drawing office with a
subtle blue-to-aqua gradient, rounded information containers, and restrained type.
These are their defaults; follow new explicit design directions when supplied.

## Reuse the toolkit

In `C:/Projects/rhino-urbanism`, inspect `urbanism_ui.py` before building controls.
Extend shared components when appropriate. `QuickArea.py` and `QuickArea.md`
demonstrate accepted behavior; inspect current files rather than assuming they
never change. Use `rhino3d-scripts` for geometry/scripting guidance when relevant.

Read [references/appearance.md](references/appearance.md) for styling, and
[references/rhino-runtime.md](references/rhino-runtime.md) for native Windows
controls, overlays, and live verification. These describe the design independently
of the repository; reuse its live helper rather than maintaining a copied version.

## Interaction conventions

- Skip opening confirmation dialogs for commands without settings to enter.
  Accept compatible preselection immediately; otherwise start Rhino's native picker.
  Show settings only when there are meaningful inputs to supply.
- Use native command-line input/picking for spatial or numeric input when helpful.
  Temporarily hide the dialog during picking; cancellation retains the result.
  Keep results available while users navigate and inspect viewports.
- Label actions precisely: **Copy section area**, **Copy base plane area**,
  **Change height**, **Close**. Use one clear primary action.
- Copy the numeric value at the displayed precision and unit, then close after
  successful copying. If copying fails, retain the dialog and show feedback.
- For small fixed choices such as three area units, prefer visible buttons with
  a distinct active state to dropdowns. This does not apply to long option lists.
  Use compact notation: `m²`, `km²`, `ha`.
- Separate full-precision calculations from display formatting. QuickArea uses a
  decimal slider 0–6 defaulting to 2, without redundant integer-rounded rows.
  Apply precision controls only where the task needs them.
- Preserve useful session settings. QuickArea's height is positive, entered in
  metres, remembered for the Rhino session, and recalculates the original selection.
  Inspection selection must not replace the inputs during recalculation.

## Partial results and actionable diagnostics

Do not imply every selected volume contributed when some failed. Keep an inline
warning below measurement context even after the issues dialog closes, e.g.
“6 of 8 selected objects excluded from totals.” Explain the height only when the
failure actually concerns missing sections; do not mislabel other geometry failures.

Count successful solids in the summary, separately from selected objects. A block
may contain both counted and failed solids; describe it as partly counted rather
than entirely excluded. Preserve originating object identity through extraction,
measurement, diagnostics, and preview.

Clicking an issue entry selects that exact object while keeping the issues dialog
open. Group reasons by object; show name and short ID where available. Missing,
hidden, or locked objects get feedback without silently clearing prior selection.

Use text plus spatial feedback when useful: aqua for counted section loops,
muted coral for failed solid wires. Draw actual measured/excluded geometry,
including world-transformed block contents. Use temporary overlays, not document
recolouring or added curves. Clear previews on Close, Escape, X, successful Copy,
recalculation, and errors. Persistent warning tags remain a separate user choice.

## Verify the experience

Use Rhino MCP in the intended open document when available. Capture and inspect
the actual dialog; a mockup or syntax check does not prove runtime behavior.
Check changed interactions, partial-result counts, cancellation, clipboard values
and failures, and preview cleanup. Inspect borders, real outer corners, scrolling,
and readable layout at the user's display scaling.

Use small relevant fixtures, remove them, and restore selection, clipboard, camera,
and session settings affected by testing. Preserve user geometry. State what was
tested and any unavailable live validation. This skill does not authorize migrating
every script, publishing, or changing Rhino configuration.
