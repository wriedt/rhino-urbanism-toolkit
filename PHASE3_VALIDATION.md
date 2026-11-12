# Phase 3 reliability results

Validated on 2026-11-11 in Windows / Rhino 8.36.26296.17001 (Python 3.9.10).
Automated source-code reliability checks are complete. Installation, deployed
library loading, toolbar appearance and restart/update behavior belong to phase 4.
Conditional-tool admission still requires the manual checks below.

## Passing checks

| Suite | Passing checks |
| --- | ---: |
| Layer visibility, current-layer recovery and Undo/Redo | 50 |
| Layer lock isolation and restoration | 27 |
| Root layer 0 exception | 20 |
| Block naming conventions | 13 |
| Block operations in isolated documents | 38 |
| Visible block dialogs, protection and native Undo/Redo | 94 |
| Floor-area geometry, events, UI and cleanup | 32 |
| PushPullCurve projection and partial-segment workflow | 81 |
| PushPullCurve exact mixed-curve geometry and commits | 140 |
| PushPullCurve picker, previews, cancellation and cleanup | 240 |
| ShapeBuilder: seven geometry/attribute/leftover/erase suites | 368 |
| **Total** | **1,103** |

The live layer preselection workflow also passed all four isolate/restore entry
points. It does not report a numeric check count and is not included in the total.
No archived-source comparison is claimed for PushPullCurve's optional baseline.

The final floor-area suite uses real native button events but captures copied
values at the clipboard boundary. It also simulates clipboard unavailability to
check visible failure feedback. It does not verify the operating system clipboard.

Current area and block-dialog captures were inspected. The block overview shows
the expected sorting/selection and assignment controls. The area warning state
withholds totals and disables Copy while keeping the warning list visible.

## Synthetic ShapeBuilder performance

| Intersecting grid lines | Regions | Prepare | Merge all | Stroke Undo |
| ---: | ---: | ---: | ---: | ---: |
| 22 | 100 | 0.112 s | 0.029 s | <0.001 s |
| 42 | 400 | 0.699 s | 0.171 s | 0.001 s |
| 62 | 900 | 3.716 s | 0.902 s | 0.002 s |

These are synthetic planar grids in disposable documents, not real production
drawings or viewport frame-rate measurements. Preparation has a visible pause at
900 regions. Treat larger/complex drawings as unverified, not as a supported size
limit. Runner: `packaging/benchmark_shape_builder_rhino.py`.

## Problems found and corrected

The original floor-area test harness retained a live OLE clipboard object for
later restoration. Restoration failed with OpenClipboard error 0x800401D0 after
the functional checks. Its error path attempted timer cleanup twice, causing an
unhandled ObjectDisposedException and crashing the empty test session. A later
attempt to restore the same clipboard object hung that session.

The harness now avoids reading or replacing the system clipboard, captures Copy
values at the boundary, guards late timer callbacks, and makes cleanup idempotent.
The final run deliberately calls cleanup twice and passes all 32 checks. The
dialog harness also detaches timer handlers before disposal. The final Rhino
session remains responsive. This identified a test-harness failure; no production
command code change was needed for it. Actual OS clipboard behavior remains an
explicit installed-package check.

An older PushPullCurve input stub lacked AddOption/OptionIndex after SplitSegment
was introduced. The stub and its legacy source path were updated; the workflow
then passed 240 checks.

## Drawing and session preservation

The connected test documents were empty, separate from Rune's landscape drawing.
Disposable documents were used for the geometry suites. Live fixtures were removed
after tests. The final snapshot matches the starting objects, attributes,
selection, layers/current layer, definitions, units, camera and modified flag.
There are zero active objects and no remaining floor-area controller, validation
timer or ShapeBuilder controller. The separate landscape document was not targeted.

The clipboard content from the interrupted runs is not claimed to be restored;
the successful final run leaves the system clipboard untouched.

## Remaining gates

- Phase 4: install the package in an isolated profile, verify actual command and
  library loading without the source folder, toolbar light/dark icons, document
  switching/closing, OS clipboard, restart, update and removal.
- The read-only audit found 17 aliases pointing to source scripts, including the
  old `RutShapeBuilder` spelling. Their exact macros are saved in
  `work/phase3-validation/aliases.json`. No alias was changed. Back up and resolve
  conflicts during installed-package testing; all packaged commands use `RUT`.
- ShapeBuilder remains conditional until a real physical Alt-drag gesture is
  checked. The available Windows input tools do not support holding Alt during a
  drag. Programmatic erase callbacks and geometry checks do not replace that test.
- Rune's phase 5 real-drawing and workflow checks remain required, especially for
  both conditional modeling tools. Synthetic performance is preliminary evidence.

Detailed reports are in `work/phase3-validation/`, with current UI captures in
`work/floor-area-validation/` and `work/block-command-validation/`. The headless
suite runner is `packaging/run_phase3_rhino.py`; run it with the intended live doc
as its `doc` argument or with Rhino's injected `__rhino_doc__`.
