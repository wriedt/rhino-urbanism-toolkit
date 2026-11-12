# First beta release plan

Scope agreed on 2026-11-11. Steps 1 and 2 of the release roadmap are complete.
Automated phase 3 and isolated phase 4 package checks have passed. Rune reported
his hands-on tests passed on 2026-11-12. The single-toolbar correction is built
and visually checked. Phase 6's release materials and final package checks are
prepared. The toolbar crash remains unresolved after investigation; Rune's
acceptance of the final candidate/limitations and sharing approval are pending.

## Phase 6 status

Candidate **0.1.0-beta1+20601** has release notes, quick-start and feedback guides,
offline command help, a matching source archive, GPL license, install/remove
helpers and checksums. The final build passed 113 content checks and five
packaging tests. Automatic normal-folder discovery, installed measurement,
standalone toolbar opening and test installation removal passed. See
[the release review](PHASE6_RELEASE_REVIEW.md) for evidence and the remaining
acceptance decision. No upload, commit or distribution was performed.

## Phase 5 status

Prepared on 2026-11-12: a six-station practice drawing in
`work/phase5-validation/RUT-beta-hands-on.3dm` and the
[hands-on test sheet](BETA_HANDS_ON_TESTS.md). Six installed-library measurement
outcomes and saved test-object preservation were checked. Rune subsequently
reported that his tests passed; no individual timings or per-item results were
supplied. Keep both conditional tools in the candidate. His requested toolbar
correction replaces four category tabs with one **RUT | Rhino Urbanism Toolkit**
tab and three native separators between the four categories. Phase 6 preparation
can follow this correction; final release acceptance and sharing remain separate.
The corrected layout passed 94 package checks and was visually verified in Rhino
using an installed-RUI review copy; see the phase 4 follow-up for caching limits.
An unresolved Rhino crash occurred during automated floating-toolbar placement;
see the phase 4 follow-up. Investigate it before approving the beta for sharing.

## Phase 4 status

The isolated local Yak installation, fresh-process loading, all 18 command
launches, light/dark toolbar, area-window document lifecycle, update and removal
checks passed on 2026-11-11. Installed testing found and corrected the library
import layout; the runtime now contains 30 files including its package initializer.
See [the phase 4 record](PHASE4_VALIDATION.md) for evidence and limits, including
the custom-root checks plus successful normal-root automatic discovery, the
preserved geometry clipboard and unchanged normal-profile aliases. The corrected candidate
can proceed to Rune's phase 5 tests in the separate validation profile.

## Phase 3 status

Automated reliability checks completed on 2026-11-11: 1,103 passing checks plus
the live layer workflow. See [the validation record](PHASE3_VALIDATION.md) for
coverage, the corrected test-harness timer/clipboard failure and remaining limits.
Final drawing/session preservation checks passed. The 16 core tools can proceed
to installed-package testing. PushPullCurve and ShapeBuilder continue as
conditional candidates; physical Alt-drag and real-drawing checks remain open.

## Phase 2 preparation record

Prepared on 2026-11-11: all 18 command entries, stable command IDs, approved
light/dark SVG icons, generated toolbar, command Help URLs, packaged Markdown
help and license, and an explicit 29-file Python runtime library. The original
plugin ID is retained. Existing source scripts and Rhino aliases are unchanged.

A trial build succeeded with RhinoCode 8.36 using target `8.36-win`, producing
a Windows-tagged Yak, RHP and RUI. Five packaging tests and 80 build-content
checks passed. The content checks cover all toolbar actions, exact approved
light/dark SVGs, embedded command/runtime inventories and the package allowlist.

At phase 2, no Rhino session was available; launching through the connector was denied by
the host. Live toolbar appearance, actual alias conflicts, deployed library
loading, installation/restart and modeling behavior remain to be checked in
phases 3 and 4. A read-only alias audit is supplied in `packaging/audit_aliases.py`;
no local alias has been disabled or rewritten. These local build artifacts are
preparation outputs, not an approved beta for colleagues.

## Audience and platform

- First tester: Rune, using representative drawings and normal studio workflows.
- Next testers: a few invited colleagues, after Rune accepts the candidate.
- Initial target: Windows, Rhino 8, Python 3.
- Record the minimum supported Rhino 8 service release after build and installation testing.
- Public Package Manager distribution and macOS support are outside this first release.
- No release date is set; the first packaged candidate will establish the remaining work.

## Command scope

The beta targets 16 core commands and two conditional additions. Inclusion still
requires passing the release checklist; existing scripts and aliases are not proof
that an installed package works.

| Group | Proposed packaged command | Source |
| --- | --- | --- |
| Layers | RUTIsolateLayer | IsolateLayer.py |
| Layers | RUTUnisolateLayer | UnisolateLayer.py |
| Layers | RUTIsolateLockLayer | IsolateLockLayer.py |
| Layers | RUTUnisolateLockLayer | UnisolateLockLayer.py |
| Layers | RUTShowAllLayers | ShowAllLayers.py |
| Layers | RUTUnlockAllLayers | UnlockAllLayers.py |
| Layers | RUTShowAndUnlockAllLayers | ShowAndUnlockAllLayers.py |
| Layers | RUTToggleLayerExpansion | ToggleLayerExpansion.py |
| Blocks | RUTCreateBlockVersion | CreateBlockVersion.py |
| Blocks | RUTConsolidateBlockVersions | ConsolidateBlockVersions.py |
| Blocks | RUTRenameBlockFamily | RenameBlockFamily.py |
| Blocks | RUTAssignBlockLayer | AssignBlockLayer.py |
| Blocks | RUTApplyBlockLayers | ApplyBlockLayers.py |
| Blocks | RUTShowBlockLayers | ShowBlockLayers.py |
| Floor area | RUTQuickFloorArea | QuickFloorArea.py |
| Floor area | RUTFloorArea | FloorArea.py |
| Conditional | RUTPushPullCurve | PushPullCurve.py |
| Conditional | RUTShapeBuilder | ShapeBuilder.py |

Every packaged command must begin with the uppercase prefix `RUT`. Use the same
spelling in toolbar actions and user documentation. Resolve existing local alias collisions and
toolbar naming during package preparation without breaking direct script use.

PushPullCurve and ShapeBuilder join only after regression and interaction checks
pass, including projection/splitting/cancellation for PushPullCurve and physical
Alt-drag plus representative drawing performance for ShapeBuilder. Unresolved
failures can defer either tool; they need not hold back the core release. Record
any deferral in the release notes and have Rune accept the final command list.

## Supporting files and deferred tools

Bundle the supporting modules used by included commands: layer_tools,
block_actions, block_dialogs, block_layers, block_versions, floor_area,
urbanism_ui and viewport_ui. Include pushpull_mixed and shape_builder_leftovers
when their corresponding commands are included. Verify the complete dependency
set during preparation.

QuickArea.py and ShapeBuilderPrototype.py remain source compatibility launchers;
they are not additional advertised beta commands. Verify that package installation
does not break existing source-based shortcuts.

Defer TopDetailFrame, PlaceScaledPaperRectangle, RebuildCurveByDistance and
ToggleWireframe. Keep development files, test scripts, test drawings, screenshots,
backups and the work directory outside the distributed package.

## Remaining roadmap and responsibility

| Stage | Codex can handle | Rune needs to handle | Exit condition |
| --- | --- | --- | --- |
| 2. Prepare plugin | Register commands; bundle libraries; resolve paths and alias conflicts; prepare toolbar and help | Resolve any material workflow or scope choices that emerge | Complete buildable project with the agreed commands |
| 3. Check reliability | Run appropriate regression checks; reproduce failures; fix problems; record results | Supply representative workflow examples if needed | Included tools pass checks; remaining limits are documented |
| 4. Build candidate | Build package; exercise installation and restart; test installed commands, update and removal | Complete any installation prompt requiring direct interaction | Candidate works in a clean Rhino profile without the source checkout |
| 5. Test normal work | Prepare a short test sheet; investigate feedback; fix and retest | Test real drawings, mouse interactions and everyday use; judge usability | Rune accepts normal workflows and any remaining limitations |
| 6. Prepare release | Finalize package, quick-start guide, release notes, known limits and feedback instructions | Accept final command list and authorize sharing | Approved beta candidate ready for invited testers |
| 7. Share beta | Prepare the handoff and carry out authorized distribution where tools permit | Choose and invite colleagues; provide any required destination or account sign-in | Invited testers receive the approved package and instructions |

Actual tool availability and account access determine which installation or
distribution actions Codex can execute directly. Preparing the package does not
authorize contacting colleagues or publishing it publicly.

## Release acceptance checklist

All boxes below start unchecked. Earlier recorded source tests inform the work;
they do not count as completed installed-package checks.

- [x] Build the agreed commands and their dependencies into an installable package.
- [x] Confirm command names and toolbar entries in an alias-free test profile; preserve normal source aliases.
- [x] Install in a clean Rhino settings profile with source-script access blocked; restart and launch every included command.
- [x] Record tested Windows build 26300.9974 / Rhino 8.36.26296.17001; minimum beta target Rhino 8.36.
- [x] Run relevant existing regression checks against the release code and record results.
- [ ] Verify preselection, cancellation, invalid input and documented failure behavior where applicable.
- [ ] Verify Undo/Redo and preservation of geometry, transforms and attributes where applicable.
- [ ] Verify nested/linked block protections, home-layer persistence and supported document units.
- [ ] Verify layer restore behavior, session-only snapshots and the root-layer 0 exception.
- [ ] Verify floor-area totals, warning overlays, clipboard behavior and window lifecycle.
- [ ] Verify repeated invocation, document switching/closing and cleanup of temporary displays and event handlers where applicable.
- [x] Retain both conditional tools after automated checks and Rune's reported hands-on pass.
- [x] Record Rune's reported test pass, synthetic timings and deferred issues; detailed real-drawing timings were not supplied.
- [x] Verify package update/removal behavior and that existing source shortcuts are unchanged.
- [x] Prepare toolbar, quick-start guide, command list, known limitations, license and versioned release notes.
- [x] Prepare invited-tester installation/removal steps and a structured feedback form.
- [ ] Rune accepts the final command list, real-workflow results and remaining limitations.
- [ ] Rune authorizes sharing the approved package with the invited testers.

A crash, incorrect result, unintended document change, broken Undo or failed
installation blocks the affected command from release. Smaller issues may remain
only when documented and accepted by Rune. New features and broad UI redesigns
are outside this beta unless needed to resolve a release-blocking issue.
