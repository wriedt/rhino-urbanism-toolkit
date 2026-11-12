# RUT beta hands-on tests — phase 5

Status: **ready for Rune; hands-on results pending**. Use the separate RUT
validation window, which runs the installed commands without source aliases.
Start with `work/phase5-validation/RUT-beta-hands-on.3dm` and save your changes
under another name. The drawing uses **metres** and has six numbered stations.
Select the station's geometry, excluding its explanatory text.

Codex has prepared the drawing and checked six measurement outcomes against the
installed library. Rune needs to judge mouse interaction and practical use.
Codex can reproduce reported problems, fix them and retest the affected tools.

## 1. Toolbar and layers

- [ ] The RUT container is named **RUT | Rhino Urbanism Toolkit**, with **Layers**,
  **Blocks**, **Floor Area** and **Curve Tools** tabs. Hover a button: its command
  starts with uppercase **RUT**. Rhino collapses tab text if the container is too
  narrow; widen it to see the category names. The full container name is shown
  in its Properties and gear menu; the tab strip shows category names.
- [ ] At station 1, select the parent square and run **RUTIsolateLayer**, then the
  child square and isolate again. **RUTUnisolateLayer** restores the first state:
  the initially hidden square stays hidden. Layer `0` stays visible/unlocked.
- [ ] Repeat with **RUTIsolateLockLayer / RUTUnisolateLockLayer**. The initially
  locked square stays locked after restoration. Check Undo/Redo.
- [ ] Try **RUTShowAllLayers**, **RUTUnlockAllLayers**,
  **RUTShowAndUnlockAllLayers** and **RUTToggleLayerExpansion**. Confirm their
  names match what happens in the layer panel.

## 2. Blocks

- [ ] Station 2 contains two `BetaHouse_v02` copies, one `BetaHouse_v04`, and an
  unused `BetaHouse_v06` definition. Select one v02 and run **RUTCreateBlockVersion**:
  the next version is **v07**; only that selected copy switches. Undo and Redo.
- [ ] Undo the version change before trying **RUTConsolidateBlockVersions**.
  Review v02/v04/v06 becoming v01/v02/v03 when starting at 1. Cancel once before
  applying; geometry and instance placement should stay unchanged.
- [ ] **RUTRenameBlockFamily** should preview a shared family rename and allow
  cancellation. Apply once and Undo.
- [ ] With **RUTAssignBlockLayer**, save the destination `02 Blocks::Block home
  destination`. Saving moves nothing. **RUTShowBlockLayers** shows the rule;
  **RUTApplyBlockLayers** previews the affected copies before moving them. Undo.

## 3. Floor area and Copy

- [ ] At station 3, **RUTQuickFloorArea** on the tall box gives **80.00 m²**;
  the short box gives **32.00 m²**; the nested block below gives **30.00 m²**.
- [ ] **RUTFloorArea** at its default 1.5 m height gives **80 m² base and section**
  for the tall box, and **30 m²** for the nested block. Selecting the short box
  warns instead of displaying a section total. Lower the height below 0.5 m:
  its base and section become **32 m²**.
- [ ] Include the open surface in a selection: all totals are withheld and coral
  outlines identify the problem. Deselect it and confirm the totals return.
- [ ] When ready to replace your current clipboard contents, try QuickFloorArea
  and the inspector's Copy buttons, then paste into a text field. Quick copies
  `80.00 m²`; the inspector copies the displayed numeric value. Check your chosen
  unit/precision. This is the remaining real clipboard check.
- [ ] Leave the inspector open while selecting, moving and undoing a box. Its
  values follow the selection and edits. Run it again: one window remains.
  Escape keeps it open; its header × closes it and removes overlays.

## 4. PushPullCurve — conditional inclusion

- [ ] At station 4, run **RUTPushPullCurve** on the rectangle: try a straight-edge
  move, typed distance, SplitSegment and Undo/Redo. Cancel a preview: the source
  remains unchanged.
- [ ] On the mixed outline, edit straight sections and check the semicircle stays
  curved and intact. On the nonplanar example, check Project/Cancel and finish
  only when the projected result is intended.

## 5. ShapeBuilder — conditional inclusion

- [ ] Select the overlapping curve, hatch and divider at station 5. Run
  **RUTShapeBuilder**, drag across regions to merge, then physically **hold Alt
  before starting a drag** to erase. Try Alt-click on an outside open tail.
- [ ] Undo a stroke inside the tool, then Escape: originals remain unchanged.
  Repeat and Finish: originals are replaced by default. Rhino Undo restores them.
  Repeat with KeepOriginals=Yes and confirm originals remain after Finish.
- [ ] Start a merge in the hatch's exclusive region, then in the curve's exclusive
  region on a fresh run. The starting region determines the output type/style.
- [ ] At station 6 select only the 22 grid lines (100 enclosed regions). Try a
  long merge stroke, erase and Undo. Record whether the response feels usable.

## 6. Representative drawings

- [ ] In this validation window, open **copies** of one small and one realistically
  large studio drawing. Repeat the tools you actually use; check orbit/pan/zoom,
  snapping, selection, nested blocks and drawing units. For the two conditional
  tools, record input size and any noticeable delay or confusing feedback.

## Feedback and release decision

Report: **command · package/Rhino versions · drawing units · steps · expected
result · actual result**. A small reproducible drawing is useful. Mention crashes,
incorrect totals, unintended edits or broken Undo first.

| Decision | Rune's result |
| --- | --- |
| Core tools usable on normal work | Pending |
| PushPullCurve included / deferred | Pending |
| ShapeBuilder included / deferred | Pending |
| Remaining limitations acceptable | Pending |

Once Rune reports these results, Codex can complete phase 6: resolve issues,
prepare final release notes and the invited-tester handoff. Sharing waits for
Rune's acceptance of the final command list and authorization to share.
