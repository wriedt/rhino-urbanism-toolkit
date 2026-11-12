# Phase 4 installed-package validation

Validated on 2026-11-11 in Windows / Rhino 8.36.26296.17001, using the
`RUTBetaValidation` settings scheme and a dedicated local Yak installation root
at `work/phase4-validation/packages/`. Normal Rhino drawings, aliases and the
normal Package Manager installation root has been restored to its initial state
after the temporary automatic-discovery check described below.

## Packaging correction

The initial installed command failed with `ModuleNotFoundError: rut_bootstrap`.
The library was embedded, but its modules were deployed inside a package folder,
not exposed as top-level imports. The corrected project includes an explicit
`rut_runtime/__init__.py`, and every command imports
`rut_runtime.rut_bootstrap`. The library now contains 30 files. The original
plugin ID, all 18 command IDs and uppercase RUT command names are retained.

The corrected package passed the five packaging tests and 80 build-content
checks, then loaded successfully in fresh Rhino processes.

## Installed behavior checked

- The actual Yak client installed and updated local packages in the isolated root.
  Its active manifest advanced from the initial build to the corrected build.
- An empty fresh settings profile had no RUT aliases. All 18 native commands
  registered with the uppercase RUT prefix.
- A Python audit hook blocked reads of source checkout scripts while allowing
  the validation harness and installed package. The deliberate source-file read
  failed, and installed commands still worked. Runtime modules came from the
  installed library or Rhino's deployed library cache, not source files.
- All 16 core commands passed native dispatch checks. Layer operations verified
  visibility/lock effects and restoration. All six block dialogs opened and
  cancelled normally. QuickFloorArea supplied `80.00 m²` for the test solid, and
  FloorArea opened with a valid measurement.
- Both conditional commands reached their native selection prompts. Physical
  Escape returned each to the command prompt without edits or tracebacks. This
  verifies installed launch/cancellation, not full interactive geometry editing.
- The actual generated toolbar was inspected in Rhino's light and dark modes.
  All 18 approved icons were visible and legible at the current display scaling.
- Repeated FloorArea invocation reused its controller. Events/closure from a
  different document were ignored. Closing its own document through New closed
  the inspector, removed its sticky controller and detached its subscriptions.
- All live smoke-test fixtures were removed; no active geometry remained.
- The Yak client removed the isolated installation. A subsequent fresh process
  had no RUT commands, no installed RHP files and no active RUT package manifest.
- A final temporary install in Rhino's normal Package Manager folder was tested
  in a new `RUTBetaPackageDiscovery` profile. All 18 commands were discovered
  automatically without explicitly loading the plugin. RUTShowAllLayers ran and
  its modules loaded from the normal package folder. The discovery process was
  closed and the test-owned package removed; its folder is absent again.

Reports are in `work/phase4-validation/`: `probe.json`, `command-smoke.json`,
`registered-commands.json`, `module-paths.json`, `lifecycle-probe.json`,
`document-lifecycle.json`, `owner-close.json`, `uninstall.json`,
`automatic-discovery.json` and `temporary-standard-install.json`.

## Limits and phase 5 handoff

The main command/lifecycle tests use a dedicated install root outside Rhino's
normal package root and explicitly load its RHP. A separate temporary normal-root
installation verifies automatic Package Manager discovery. This record does not
claim a clean Windows installation or the absence of other machine-wide plugins.
The isolated settings profile
separates aliases and toolbar layout, not machine-wide third-party plugins.

The system clipboard currently contains drawing/vector data. It was preserved.
Copy values and unavailable-clipboard feedback were checked at the copy boundary;
an actual OS clipboard write still needs the user's normal-use check.

Use the separate RUT validation window for the installed candidate: the normal
profile's 17 source aliases remain unchanged. In that validation window:

1. Try the core tools on copies of representative drawings, including Copy from
   the floor-area tools, and confirm normal modeling/navigation feels right.
2. Try PushPullCurve on actual outlines: preview, typed distance, SplitSegment,
   cancellation and Undo/Redo.
3. Try ShapeBuilder on actual curves/hatches: merge, physical Alt-drag erasing,
   Finish/Cancel and Undo/Redo. Assess the delay on realistic drawing sizes.

Both modeling tools remain conditional until those hands-on checks pass. Help
Markdown files and the license are bundled under the installed package's `shared`
folder. Online command Help URLs refer to the matching repository pages; newly
added pages must be published with the release before those URLs are dependable.

No package was uploaded or shared. This candidate is for Rune's phase 5 test,
not yet an approved colleague/public beta.

## Toolbar layout follow-up — 2026-11-12

The native container name is **RUT | Rhino Urbanism Toolkit**. Its category tabs
were visually checked in order: Layers (8 icons), Blocks (6), Floor Area (2),
Curve Tools (2). Increasing the floating width exposes the category names;
at narrow widths Rhino collapses these labels to icons. The full container name
is visible in its Properties and gear menu. The obsolete ungrouped preview was
closed in the validation profile.

During a separate native-container import/window-placement experiment, Rhino
process 13708 crashed at 10:41:58 on 2026-11-12. Windows Application event 1000
records KERNELBASE.dll, exception 0xc000041d, report
6086a4d6-ef9e-4f2f-adf4-c974f880156c. No RUT modeling command was active. The
last action was maximizing a floating toolbar during automated window placement.
The cause has not been isolated: this is an unresolved setup issue, not evidence
of a geometry-command defect or a successful layout-restoration test. The
experimental RUT.rhc is excluded from the beta package. The saved practice
drawing was reopened in the previously checked validation profile. Investigate
this crash before accepting the beta for sharing.

The [phase 5 test sheet](BETA_HANDS_ON_TESTS.md) and six-station practice drawing
are prepared. Six measurement expectations passed against the installed library;
the drawing was read back to verify units and authored object IDs. These checks
do not count as Rune's hands-on acceptance.

## Single-toolbar correction — 2026-11-12

Rune reported his hands-on tests passed and requested one toolbar with spacers
instead of category tabs. The release RUI now has one **RUT | Rhino Urbanism
Toolkit** toolbar: 8 layer tools, separator, 6 block tools, separator, 2 floor-area
tools, separator, 2 curve tools. Macro IDs, command names and approved icons are
unchanged. All 94 build-content checks passed, including the separator positions,
full tab title, exact command order and final RUI inside the Yak.

The installed RUI was inspected in Rhino 8.36's dark mode in a separate empty
validation window. Rhino retained old plugin-bound toolbar definitions, so a
review copy with only the plugin binding removed was opened to inspect the final
RUI. The one full-name tab, 18 icons and three visible dividers rendered correctly;
the old tabbed previews were closed in that test profile. The review copy uses
the installed RUI's actual buttons, macros and icons. No model objects or aliases
were changed. Evidence: `work/phase4-validation/single-toolbar.json`.

Existing Rhino workspaces may keep their old toolbar layout after updating; the
newly generated package and the checked running review are distinct. Native
container-import/maximizing remains excluded and the earlier setup crash remains
unresolved. Rune's reported modeling-test pass does not resolve that setup issue.
