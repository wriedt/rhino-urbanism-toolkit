# RUT beta quick start

**Rhino Urbanism Toolkit 0.1.0-beta1 — review candidate.** Use the approved
release kit only after Rune accepts the release notes and authorizes sharing.
Windows / Rhino 8.36 or later is required. Earlier Rhino releases and macOS are
outside this beta. Read [the release notes](BETA_RELEASE_NOTES.md), including the
unresolved toolbar-setup crash and tested platform.

## Install or update

1. Extract the entire release ZIP to a normal folder. Keep its files together.
2. Save your drawings and close **all Rhino windows**.
3. Double-click **Install-RUT.cmd**. It installs the included package for your
   Windows user; it does not upload anything or change your aliases. Wait for
   the success message, then start Rhino 8.
4. Type **RUTShowAllLayers** in a new empty drawing to check the commands load.

To update this beta, repeat these steps with the newer approved kit. Keep your
previous kit if you need to go back. To roll back, close Rhino, remove the current
beta with its Remove helper, then install the previous approved kit.

The helpers expect Rhino 8 in `C:\Program Files\Rhino 8`. If it is installed
elsewhere, use that installation's `System\Yak.exe` to install the supplied
`.yak` file, or ask Rune for assistance. The helpers pause when Rhino is open.
You can also remove the plugin in Rhino's **PackageManager → Installed**, then
restart Rhino. There is no need to log in to a package server for a local kit.

## Toolbar

All 18 tools share one **RUT | Rhino Urbanism Toolkit** tab, with native separators
between **Layers**, **Blocks**, **Floor Area** and **Curve Tools**, in that order.
The toolbar supports Rhino's light and dark appearance.

If it is hidden or an older tabbed layout remains:

1. Close the old RUT floating containers with their × buttons.
2. In **Window → Toolbars**, use **File → Open** and choose the kit's **RUT.rui**.
   This opens only the toolbar, without replacing the rest of your workspace.

For this beta, avoid maximizing floating toolbars or importing custom container
layouts: that setup path had an unresolved crash during automation testing.
This is a workaround, not a confirmed fix. Report any recurrence to Rune.

## Commands

| Group | Commands | Help |
| --- | --- | --- |
| Layer visibility | RUTIsolateLayer, RUTUnisolateLayer, RUTShowAllLayers | [Layer tools](LayerTools.md) |
| Layer locks | RUTIsolateLockLayer, RUTUnisolateLockLayer, RUTUnlockAllLayers | [Layer tools](LayerTools.md) |
| Layer panel | RUTShowAndUnlockAllLayers, RUTToggleLayerExpansion | [Layer tools](LayerTools.md) |
| Block versions | RUTCreateBlockVersion, RUTConsolidateBlockVersions, RUTRenameBlockFamily | [Block commands](BlockCommands.md) |
| Block home layers | RUTAssignBlockLayer, RUTApplyBlockLayers, RUTShowBlockLayers | [Block commands](BlockCommands.md) |
| Floor area | RUTQuickFloorArea, RUTFloorArea | [Quick measurement](QuickFloorArea.md), [Live inspector](FloorArea.md) |
| Curves | RUTPushPullCurve, RUTShapeBuilder | [Push/pull](PushPullCurve.md), [Shape Builder](ShapeBuilder.md) |

Try copies of drawings. Use compatible preselection or follow the selection
prompt. Escape cancels interactive modeling operations. FloorArea is a persistent
inspector: its header × closes it; Escape keeps it open. Copy replaces the system
clipboard contents. See individual help for geometry scope and other limits.

## Existing source shortcuts

If you already use RUT source-script aliases, they can override the installed
commands. Ask Rune to help audit/back up those aliases and temporarily disable
only the conflicts when checking the packaged version. Installation and removal
do not rewrite aliases or remove your source scripts.

## Remove

Close the RUT toolbar, save your drawings and close all Rhino windows. Double-click
**Remove-RUT.cmd**, then reopen Rhino. You can alternatively uninstall through
PackageManager and restart. Removal affects the installed toolkit, not your
drawings. Ordinary curves, solids, blocks and hatches remain Rhino geometry;
there are no custom RUT document objects that need the plugin to display.

## Help and feedback

The kit's **Help** folder contains the offline guides, release notes and
[feedback form](BETA_FEEDBACK.md). Installed help is also in the package's
`shared` folder. Online command Help pages may not be published yet.
Send feedback to Rune through your agreed studio channel. Include the command,
exact package/Rhino versions, drawing units, steps, expected and actual result.
