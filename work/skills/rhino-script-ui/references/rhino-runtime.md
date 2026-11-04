# Rhino implementation and live verification

## Eto and Windows styling

Use Eto.Forms for Rhino 8 dialogs. The urbanism helper provides `AquaDialog`,
`InfoPanel`, `button`, `label`, `action_row`, `theme_scrollbars`, and theme refresh.
Keep it alongside importing scripts or follow the project's packaging arrangement.
Guard WPF customization by platform; retain native controls and their keyboard and
accessibility semantics. Do not promise Windows styling on macOS; state what was tested.

Lessons from the accepted implementation:

- A painted stroke on control bounds may be clipped and appear to disappear at
  fractional scaling. Inset it, or use a native WPF rounded Border with layout
  rounding and pixel snapping.
- Removing the system title bar requires replacement drag and close affordances.
  Supply a draggable header, accessible X, and Escape/Close. Header close on a
  decision dialog means cancel, not acceptance.
- Content clipping alone may leave rectangular backing at the outer corners.
  Windows uses transparent backing, a rounded content clip, and a rounded HWND
  region sized to physical window/DPI changes. Retain correct pointer-width
  ctypes signatures and Win32 region ownership. Inspect the actual outside corners.
- Scope scrollbar resources to the relevant control/descendants. Preserve
  `PART_Track`, native Thumb, repeat/page commands, and wheel/drag/page behavior,
  with horizontal orientation support where needed.
- Use document-owned semi-modal dialogs for viewport inspection. The existing
  `show_for_doc(..., picking=True)` and Rhino PushPickButton pattern support
  temporary native input while preserving cancellation behavior.

## Viewport feedback

Use a document-scoped DisplayConduit restricted to appropriate model space.
Draw exact counted curves in aqua and failed solid wires in coral; include both
in preview bounds. Duplicate preview geometry where ownership is ambiguous.
Disable the conduit, redraw, and dispose owned duplicates in `finally` on every
exit. Recalculation replaces the old overlay. Do not recolour model objects for
temporary diagnostics. For blocks, draw transformed contents but select the
originating instance; distinguish partly counted from fully excluded instances.

## Live checks

Discover current Rhino MCP tools and target the intended document. MCP injects
`__rhino_doc__`; bind `scriptcontext.doc` explicitly if existing helpers rely on
it. Do not trust the default context to target the intended document.

Choose tests relevant to the change:

- Preselection and direct native picking without an opening confirmation.
- Display units/precision match both Copy values; success closes and clears
  overlays; simulated clipboard failure keeps the dialog open.
- One good plus one too-short solid; all failed solids; a mixed-success block;
  correct retained warning/counts after closing issues. Other failure reasons
  must not receive a height explanation.
- Exact originating-object selection; missing/hidden/locked feedback.
- Height change reuses original inputs; cancellation retains results; intended
  session preference survives the next invocation.
- Actual dialog capture: complete borders, outer corners, focus/active states,
  scrolling, and layout at current DPI. Actual viewport capture: overlay drawing
  and cleanup, including transformed block contents.

Repository examples under `C:/Projects/rhino-urbanism/work/` include
`test_quickarea_ui_rhino.py`, `test_quickarea_scrollbar_rhino.py`, and
`test_quickarea_window_region_rhino.py`. Inspect before reusing; they are examples,
not bundled skill dependencies. Snapshot/restore affected clipboard formats,
selection, viewport, and sticky settings; delete only test-created fixtures.

Rhino ScriptEditor can cache helper imports during development. Verify the edited
code is loaded before interpreting repeated old UI as a design failure. Reload
or execute fresh source in a development harness when needed; keep this workaround
out of normal command UX.
