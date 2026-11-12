# RUT beta quick start

This is the guide for the upcoming private Windows / Rhino 8 beta. A prepared
project or successful build is not yet an approved release. Wait for the tested
candidate and its release notes before sharing it with colleagues.

## Installation and toolbar

Use the approved package and the installation steps supplied with that candidate.
Restart Rhino after installation. The package is intended to provide a toolbar
with light/dark icons and the RUT commands listed below. Installed commands run by
name; they do not require C:\Projects\rhino-urbanism-toolkit or source-file macros.
The current candidate targets Windows / Rhino 8.36 or later. Validation has been
performed on Rhino 8.36; earlier service releases and macOS are not supported.

If the toolbar is hidden, run `Toolbar` and look for the
`rhino-urbanism-toolkit` toolbar library. Its visible title is **RUT | Rhino Urbanism
Toolkit**; tools are grouped into **Layers**, **Blocks**, **Floor Area** and
**Curve Tools** tabs. The toolbar has been inspected with the
installed candidate in both light and dark modes.

Rhino shortens tabs to icons when the container is narrow; widen it to see the
category names. The full container name appears in Properties and its gear menu.
The package also supplies `RUT.rhc`: import it through **Containers → Import
container definition** to restore the RUT container without replacing your whole
workspace. It is an optional layout file, not a second plugin.

For the current hands-on test, use the separate RUT validation window. Your normal
Rhino profile retains its source-script aliases. This candidate was installed in
a dedicated local test folder and loaded explicitly. Automatic Package Manager
discovery also passed in a separate temporary normal-folder installation. The packaged `shared` folder contains
offline command help; new online help pages will be published with the release.

## Commands

For phase 5, follow the [hands-on test sheet](BETA_HANDS_ON_TESTS.md). Its practice
drawing supplies known measurements; finish with copies of representative work.

| Group | Commands | Help |
| --- | --- | --- |
| Layer visibility | RUTIsolateLayer, RUTUnisolateLayer, RUTShowAllLayers | [Layer tools](LayerTools.md) |
| Layer locks | RUTIsolateLockLayer, RUTUnisolateLockLayer, RUTUnlockAllLayers | [Layer tools](LayerTools.md) |
| Layer panel | RUTShowAndUnlockAllLayers, RUTToggleLayerExpansion | [Layer tools](LayerTools.md) |
| Block versions | RUTCreateBlockVersion, RUTConsolidateBlockVersions, RUTRenameBlockFamily | [Block commands](BlockCommands.md) |
| Block home layers | RUTAssignBlockLayer, RUTApplyBlockLayers, RUTShowBlockLayers | [Block commands](BlockCommands.md) |
| Floor area | RUTQuickFloorArea, RUTFloorArea | [Quick measurement](QuickFloorArea.md), [Live inspector](FloorArea.md) |
| Conditional beta tools | RUTPushPullCurve, RUTShapeBuilder | [Push/pull](PushPullCurve.md), [Shape Builder](ShapeBuilder.md) |

Use compatible preselection or follow the command's selection prompt. Escape
cancels interactive modeling operations. FloorArea is a persistent inspector:
its header X closes it; Escape keeps it open.

## Existing source shortcuts

Older aliases with the same RUT names may still point at source files. Before
testing installed commands, ask Rune to run the developer alias audit. No aliases
are changed automatically.
Back up the reported definitions before disabling conflicts for package testing.
Direct source-file toolbar macros and compatibility launchers remain available.

## Known scope limits

- Layer restore snapshots last only for the current document/session. Root layer
  `0` stays visible and unlocked by design.
- Floor-area totals sum individual solids, including overlaps; they are not a
  union. Unsupported or faulty solids withhold the total. Units are converted.
- Assigning a block home layer saves a rule; Apply is a separate reviewed action.
  There is no background enforcement.
- PushPullCurve edits straight sections. ShapeBuilder requires coplanar inputs;
  performance on large drawings is still a release check.
- TopDetailFrame and the other deferred utilities are outside this beta.

## Feedback

For a problem, record the RUT command, package version, Rhino version, document
units, steps, expected result and actual result. Include a small reproducible
drawing when possible. Send feedback to Rune through the agreed studio channel.
The release notes will identify any additional accepted limitations.
