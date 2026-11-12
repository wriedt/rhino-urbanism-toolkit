# Rhino Urbanism Toolkit — 0.1.0-beta1

Prepared 2026-11-12 for a few invited testers, after Rune's hands-on test pass.
**Review candidate: final acceptance and authorization to share are pending.**
The release kit's `release-info.json` identifies the exact build and checksums.

## Included

Windows Rhino 8.36 or later; validated on Rhino **8.36.26296.17001**. Earlier
Rhino service releases and macOS are outside this beta. Newer Rhino releases
have not been individually validated. License: GPL version 3; source is supplied.

All 18 commands use uppercase **RUT**. One **RUT | Rhino Urbanism Toolkit** tab
groups the tools with three native separators:

| Category | Commands |
| --- | --- |
| Layers | RUTIsolateLayer, RUTUnisolateLayer, RUTIsolateLockLayer, RUTUnisolateLockLayer, RUTShowAllLayers, RUTUnlockAllLayers, RUTShowAndUnlockAllLayers, RUTToggleLayerExpansion |
| Blocks | RUTCreateBlockVersion, RUTConsolidateBlockVersions, RUTRenameBlockFamily, RUTAssignBlockLayer, RUTApplyBlockLayers, RUTShowBlockLayers |
| Floor area | RUTQuickFloorArea, RUTFloorArea |
| Curves | RUTPushPullCurve, RUTShapeBuilder |

PushPullCurve and ShapeBuilder are retained following Rune's reported test pass.
TopDetailFrame, PlaceScaledPaperRectangle, RebuildCurveByDistance, ToggleWireframe
and compatibility launchers are not additional beta commands.

## Validation and limits of the evidence

- Phase 3: 1,103 automated checks plus a live layer workflow.
- Phase 4: installed command dispatch, document/window cleanup, restart,
  automatic Package Manager discovery, update and removal were checked.
- Phase 5: Rune reports his tests passed. Detailed individual results and
  representative-drawing timings were not supplied.
- The revised single-toolbar layout was visually checked in Rhino. The package
  includes a standalone `RUT.rui` for workspaces that retain old toolbar tabs.
- The test machine uses Windows build **26300.9974** (26H2). This is one
  workstation, with other machine-wide Rhino plugins present, not a clean-PC test.

## Known issues and behavior

**Unresolved toolbar setup crash.** Rhino crashed once in a separate automation
session while placing/maximizing a floating toolbar, after a container-import
experiment. No RUT modeling command was active. Windows retained crash summaries,
but no dump/stack trace establishing the cause. The container-import experiment
and automated maximizing are excluded from the release workflow. This exclusion
is a precaution, not proof of a fix. Acceptance of this limitation remains a
release decision; report any recurrence before continuing work.

- Existing workspaces can retain older toolbars. Close the old RUT containers
  and open the supplied `RUT.rui` through Window → Toolbars → File → Open.
  This opens just the toolbar; no workspace reset is needed.
- Existing source aliases with RUT names can override packaged commands. They
  are not changed automatically; see the quick start before testing the package.
- Root layer `0` stays visible and unlocked. Isolation snapshots last only in
  the current document/session; restoration preserves the first snapshot.
- Floor-area tools sum individual solid areas, including overlaps. Faulty inputs
  withhold totals. QuickFloorArea measures bases; the inspector also needs solids
  to reach its section height. Copy intentionally replaces clipboard contents.
- Saving a block's home layer does not move its instances; Apply is separate.
  Linked/reference and protected content follow the documented exclusions.
- PushPullCurve edits straight curve sections; projection is explicit.
  ShapeBuilder needs coplanar inputs; Finish replaces originals by default.
- ShapeBuilder's synthetic 100/400/900-region preparation took approximately
  0.11/0.70/3.72 seconds on the test machine. These are examples, not size limits
  or a performance guarantee for real drawings.
- Offline help is included. Online command Help links may point to repository
  pages that have not yet been published; use the kit's `Help` folder meanwhile.

Use the [quick start](BETA_QUICK_START.md) for installation, updating and removal,
and the [feedback form](BETA_FEEDBACK.md) when reporting a problem. Try copies of
representative drawings first. No public upload or colleague distribution has
been performed as part of preparing this candidate.
