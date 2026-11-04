# Block layer assignment - Phase 4

Run these scripts in Rhino 8.9 or later using Python 3. Keep the three command
files, `block_layers.py`, `block_layer_ui.py`, and `urbanism_ui.py` together.
After updating the scripts, close any open assignment dialog and run the command
again. The commands reload their helpers on every run; no Rhino restart is needed.

## Assign a block's intended layer

Run `AssignBlockLayer.py` and select one or more top-level block instances.
Preselection is supported. Repeated copies of the same definition produce one
row in the assignment editor, initially selected.

**Include nested definitions** is off by default. Enable it to expose definitions
used inside the selected blocks, at any local nesting level. In the selection
workflow the added definitions are selected too, ready for bulk assignment.
The manager exposes all locally reachable nested definitions when enabled.
Linked contents and unused definitions are never included. Turning the toggle
off discards staged edits to the nested-only rows and reports that discard.

Select rows with Ctrl/Shift, then **Choose layer** to give them one existing
target layer. **Remove assignment** clears their rules; **Revert selected**
discards their pending edits. Changes remain staged until **Save assignments**.
Cancel, Escape, or the header X discards unsaved edits. Filtering the list retains
pending changes to rows outside the filter.

The assignment belongs to the **block definition**, so it applies to every
instance of that definition. Assignment does not move anything. Running Assign
again replaces the rule. The chooser starts on the first selected definition's
assigned layer when available. One Undo restores a saved batch of rules; Redo
restores the new rules.

Toolbar button or alias macro:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\AssignBlockLayer.py"
```

## Apply the rules

To review all used top-level definitions without picking instances, run
`ManageBlockLayers.py`. The editor lists block names, editable/total instance
counts, assigned layers, and rule status. Definitions with only hidden, locked,
or reference copies are shown read-only. Unused definitions are omitted.

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\ManageBlockLayers.py"
```

In either assignment editor, **Apply now after saving (preview first)** opens a
cleanup preview for the definitions whose rules actually changed. It includes
all their top-level and nested occurrences, including copies outside your original
selection. Unrelated definitions are excluded. The preview shows each stored
reference's short ID, occurrence count, current layer, target layer, and whether
it will move or be skipped. One nested reference edit can affect many occurrences.

**Apply cleanup** performs the displayed moves. **Keep assignments only**, Escape,
or the header X keeps the already saved rules and performs no cleanup. Changing
or removing a rule does not itself move any instances. If the model changes after
previewing, cleanup refuses to apply until you **Refresh preview**. Saving and
applying within one command is one Undo step.

`CleanUpBlockLayers.py` is the immediate whole-file cleanup command for model,
layout, and locally nested instances at every level. It uses all saved rules, not
just the rules changed in the last assignment command. One Undo restores the
whole cleanup, including edits inside block definitions. Missing target layers
open a single review dialog before cleanup changes anything.

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\CleanUpBlockLayers.py"
```

Cleanup moves only the instance's layer. It preserves geometry, transforms,
instance names, other attributes, and the block description.

- Hidden and locked instances are skipped, including hidden/locked source layers
  and their parent layers. Moves to hidden or locked target layers are skipped too.
- Unassigned blocks, invalid saved rules, and reference objects are reported and
  left alone. Missing targets are created or reassigned only through explicit review.
- Linked block instances can be assigned and moved; their internal contents are
  never traversed or edited. The assignment is stored in the current model.
- Unused definitions remain untouched. The traversal starts from placed model
  and layout instances and visits each used local definition once.
- Escape during cleanup rolls back layer changes made so far.

The command line reports counts and groups affected instances by block name,
status, and target layer. Open command history with F2 for the complete report.

## Missing target layers

The review groups missing targets by full layer path, with definition and copy
counts. A shared path is resolved once, including case variants of the same name.
Targets required only by protected references do not trigger layer creation.

- **Create missing target layers with default settings** is off by default.
  Enable it to create unresolved target paths, including missing parent layers.
  Existing parents are reused and their appearance, visibility and locking remain
  unchanged. New layers use default settings; they do not copy the source layer.
- **Choose existing layer** maps selected paths to an existing local layer and
  updates every affected block definition's rule.
- **Skip selected** retains the original rules and placements for that cleanup
  run. An explicit skip overrides the creation toggle, even if another target's
  creation happens to create the skipped path as a parent.
- **Reset selected** returns those paths to the current creation-toggle default.
- **Refresh list** updates a stale review. Changes to targets or assigned rules
  require review again before proceeding.

Choices are staged until **Continue cleanup**. Cancel, Escape, or the header X
aborts the entire cleanup, including moves to targets that already exist.
Creation, rule updates, and instance moves within the command share one Undo step.
Skipping lasts only for the current run; a later cleanup evaluates the saved rules again.

In an Apply now preview, **Resolve missing layers** opens the same review with a
**Save resolutions** action. This saves the new layers/mappings and refreshes the
preview without moving instances. **Apply cleanup** stays disabled while missing
targets remain unresolved. **Keep assignments only** keeps saved resolutions and
performs no instance moves. Invalid paths or failed resolution saves leave the
review open with an explanation; newly created layers are rolled back on failure.

## Shared nested references

A nested reference belongs to the containing block definition. Changing its layer
changes it in every occurrence of that containing definition, while leaving its
geometry and transform unchanged.

Cleanup counts visible and protected occurrences through the full parent chain.
If one shared edit would affect a hidden, locked, or reference occurrence, it is
skipped as **shared with protected copies**, even when another occurrence is
editable. The preview/report identifies the containing definition and protected
copy counts. Independent reference objects inside different parents can still
move separately; shared references deeper inside their common child definition
remain protected. A changed ancestor invalidates an already displayed preview.

Linked references inside local blocks can move, but linked definitions form a
boundary: cleanup never opens or walks their contents. Ordinary curves, surfaces,
and other non-block contents are never edited. No definitions are exploded,
rebuilt, or made unique to work around protected copies.

## Storage and versions

Each definition stores one JSON user string under `Urbanism.BlockLayer`:
schema version, target layer ID, and full layer path. The ID finds a renamed layer
in the same document; the exact full path is a fallback when the ID cannot be
found. A malformed or unsupported rule is reported rather than interpreted.

Rhino saves the data in the 3DM file. `CreateBlockVersion.py` already copies
definition user strings, so newly created versions inherit the assignment.
Copying/importing files uses Rhino's normal behavior; these scripts install no
background watchers and do not intervene during copying/importing. Cross-file
copy/import preservation is a later validation task.

## Validation

Tested inside Rhino 8.36.26293.11001:

- 52 top-level-mode regression checks: multiple instances, nested contents unchanged,
  unused definitions excluded, layout membership, real external linked blocks,
  hidden/locked objects and parent layers, missing layers, damaged rules, exact
  path fallback, renamed targets, metadata/transform preservation, repeated cleanup,
  cancellation rollback, actual version-tool inheritance, and save/reopen.
- Four command-boundary checks in the visible Rhino session: assignment Undo/Redo
  and two-instance cleanup Undo/Redo.
- Native block picker and layer chooser acceptance/cancellation.
- 39 Phase 2 runtime checks: bulk editing/removal, shared-definition counts,
  protected-only definitions, filtering/reverting/cancelling staged edits,
  invalid/stale assignments, scoped previews, stale preview rejection, unrelated
  and hidden copies, save/reopen, and dialog result handling.
- Live editor/preview flows driven through Rhino MCP, including bulk assignment,
  Apply now, bulk removal, command-boundary Undo/Redo, preview cancellation, and
  runtime-rendered dialog captures. The separate native layer chooser is unchanged
  from Phase 1; its blocking modal loop prevents a second MCP script from driving
  it, so its acceptance/cancellation was not reverified through MCP in Phase 2.
- 58 Phase 3 runtime checks: local traversal at multiple depths, nested-only rules,
  the opt-in toggle, shared hidden/locked ancestry, independent parent references,
  protected out-of-scope ancestors, linked boundaries, exact geometry/transform
  preservation, cancellation rollback, save/reopen, a 70-level chain, and a bounded
  repeated hierarchy with 4,096 leaf occurrences.
- 13 Phase 3 live checks through MCP: the visible nested assignment/preview flow,
  shared-copy warning display, Apply, combined assignment/nested Undo/Redo,
  whole-file cleanup, standalone nested Undo, and fixture removal with the restored
  original objects preserved. Final Phase 3 validation totals 162 checks, including
  the 52 and 39 regression checks above.
- 42 Phase 4 runtime checks: grouped paths and case variants, creation defaults,
  shared parents, mapping to existing layers, nested targets, protected references,
  skip/creation interactions, cancellation, stale reviews, rollback, and save/reopen.
- 14 Phase 4 live checks: review, creation/skip, combined Undo/Redo, whole-command cancellation,
  and resolution from a document-owned preview are tested through Rhino MCP with
  rendered dialog captures. Together with the 42 new runtime checks and 149
  regression checks, Phase 4 validation totals 205 checks.

Runtime test: `work/test_block_layers_rhino.py`.
Phase 2 runtime test: `work/test_block_layers_phase2_rhino.py`.
Phase 3 runtime test: `work/test_block_layers_phase3_rhino.py`.
Phase 4 runtime test: `work/test_block_layers_phase4_rhino.py`.
Evidence: `work/block-layer-tests/integration-results.json` and `live-results.json`.
Phase 2 evidence: `phase2-results.json`, `phase2-live-results.json`,
`phase2-editor.png`, and `phase2-preview.png` in the same test-output folder.
Phase 3 evidence: `phase3-results.json`, `phase3-live-results.json`,
`phase3-editor.png`, `phase3-preview.png`, and `phase3-shared-preview.png`.
Phase 4 evidence: `phase4-results.json`, `phase4-live-results.json`,
`phase4-review.png`, `phase4-preview-review.png`, and `phase4-resolved-preview.png`.
The isolated test uses temporary headless documents inside the running Rhino
process; it writes its sample files only under `work/block-layer-tests`.

## Next phases

5. Cross-file copy/import checks and further workflow polish.
