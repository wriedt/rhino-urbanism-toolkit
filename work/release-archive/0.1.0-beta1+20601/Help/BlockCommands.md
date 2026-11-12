# Block commands

Six focused Rhino 8 / Python 3 commands cover block versions, family names and
home layers. Run the **RUT-prefixed aliases** below. The underlying script filenames
remain unchanged so toolbar macros can still run the files directly.

| Rhino command | Script | Purpose |
|---|---|---|
| `RUTCreateBlockVersion` | [CreateBlockVersion.py](CreateBlockVersion.py) | Create an independent version for selected copies. |
| `RUTConsolidateBlockVersions` | [ConsolidateBlockVersions.py](ConsolidateBlockVersions.py) | Renumber a family into a continuous sequence. |
| `RUTRenameBlockFamily` | [RenameBlockFamily.py](RenameBlockFamily.py) | Rename the shared family name and its separator. |
| `RUTAssignBlockLayer` | [AssignBlockLayer.py](AssignBlockLayer.py) | Save a definition's home-layer rule without moving copies. |
| `RUTApplyBlockLayers` | [ApplyBlockLayers.py](ApplyBlockLayers.py) | Review and apply saved home-layer rules. |
| `RUTShowBlockLayers` | [ShowBlockLayers.py](ShowBlockLayers.py) | Browse definitions and edit the selected home-layer rule. |

## Running and shortcuts

The six aliases are installed in the configured Rhino instance. Use these prefixed
names instead of the former unprefixed aliases. For a toolbar button or another
Rhino installation, use this macro with the appropriate script from the table:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\CreateBlockVersion.py"
```

Keep `block_versions.py`, `block_actions.py`, `block_layers.py`, `block_dialogs.py`
and `urbanism_ui.py` beside the command scripts. Commands reload these helpers.
The retired block manager and quick-actions palette are no longer part of the workflow.

## Common dialog behavior

- Pick blocks in Rhino, or use compatible preselection. Choices and reviews use compact aqua dialogs.
- **Adjust naming** opens one **Version part** selector. Brackets mark the chosen
  text in context, such as `Building_[03]_Floor_02`. Identical tokens in different
  positions can be distinguished. **No version** treats a name as unversioned.
- **Starting name** appears only when introducing versioning to an unversioned source.
- **Full review** lists all affected definitions or proposed movements. Long one-line
  previews abbreviate the middle of names; hover for the complete value.
- Click a table header to sort ascending; click again for descending. Sorting uses
  numeric order within text. The selected definition remains correctly associated
  with its row. Resize window edges and column dividers to reveal long values;
  clipped cells have ellipses and full-value tooltips.
- Coral warning panels with a warning icon explain errors. Invalid plans cannot be applied.
- **Enter/Space** invoke the highlighted primary action even when a secondary button
  or checkbox has focus. A disabled primary action does nothing. Spaces remain normal
  text input, and open dropdowns retain their selection keyboard behavior.
- **Escape** or the header **X** cancels without applying. There are no Cancel buttons,
  outer checkbox focus rings or dotted button focus rectangles.
- Each applied operation is one Rhino Undo step, with Redo support. Stale reviews
  are rejected; mutation failures attempt to restore changes already made.

## RUTCreateBlockVersion

Select one or more top-level copies of the **same local definition**. The next
version follows the **highest existing version in that family**, including unused
definitions. This applies equally to numbers and letters:

| Family | Selected source | New version |
|---|---|---|
| `House_v02`, `House_v04` | `House_v02` | `House_v05` |
| `House_001` | `House_001` | `House_002` |
| `House A` | `House A` | `House B` |
| `House A`, `House Z` | Either | `House AA` |
| `House_A01`, `House_A03` | `House_A01` | `House_A04` |

Separators, letter case, `v`/`V` and zero padding are preserved. Padding expands
when necessary without renaming existing versions. For a combined token such as
`A01`, its letter prefix stays fixed and its numeric portion increments. Choose
`01` instead if the `A` belongs to the shared family name.

Only selected copies switch to the new independent definition. Other copies keep
their definition. Geometry, transforms, instance/member attributes, descriptions
and definition user strings (including home-layer rules) are preserved. Nested
definitions remain shared; the command does not recursively make them unique.

For an unversioned name, the default starting name ends in `_v01`. You can change
the convention. The review shows both the source rename and the new version.
Renaming the source affects **all copies** of that definition. Dimensions/product
codes can be ambiguous: use **No version** when a detected number belongs to the name.

## RUTConsolidateBlockVersions

Select one family member. Definitions are ordered by existing version and then
accidental numeric/copy suffixes. Each definition receives its own sequential
version, starting at **1 / A**, or at the lowest existing version when checked.
The naming convention and widest numeric padding are retained.

| Before | Start | After |
|---|---|---|
| `01, 02, 04, 06` | 1 | `01, 02, 03, 04` |
| `01, 01 copy, 03` | 1 | `01, 02, 03` |
| `12, 12 01, 13, 14` | Lowest | `12, 13, 14, 15` |

Numeric duplicate branches require an existing exact parent name as evidence.
Check the family in Full review. Consolidation renames definitions; it does not
merge geometry, delete definitions or change which definition an instance uses.

## RUTRenameBlockFamily

Select one member and enter the new family name. **Separator** defaults to the
existing separator. Choose **None**, **Space**, **Underscore**, **Hyphen** or
**Custom**. Custom separators preserve exact characters, including spaces.
Changing only the separator is supported: `House 01` can become `House01`. A
shared ending after the version can also be edited when present.

Version tokens and copy suffixes retain their spelling. All matching definitions
participate, including unused definitions and definitions inside other blocks.
Choose **No version** to rename an ordinary block as a whole. Family detection
matches the surrounding name and convention, ignoring case. Conflicting target
names or existing destination families are rejected; families are never silently
merged. Linked/reference definitions are protected. Text labels are not changed.

## RUTAssignBlockLayer

Select one or more local blocks, choose an existing home layer, and press **Save**.
Repeated copies are reduced to one rule per definition. The rule applies to all
copies; saving it moves nothing. Choose **No home layer** to remove a rule.
Unused local definitions can receive a rule through RUTShowBlockLayers.

## RUTApplyBlockLayers

Review movements throughout the model, then choose **Apply layers**. **Include
nested block instances** is off by default. When enabled, local nested instances
are evaluated against their own rules, not the parent's rule. **Refresh** rebuilds
the review after model changes.

- Linked/reference blocks and their internal contents are skipped.
- Hidden/locked copies and layers are protected, including protected ancestors.
- Editing a nested reference affects every occurrence of its containing definition.
  A shared edit is skipped if any occurrence is protected; the review reports the scope.
- Missing, invalid or unassigned rules cause no movement or automatic layer creation.
  Repair a rule through RUTShowBlockLayers and Assign layer.
- Layer identity survives renaming; a full-path fallback supports transferred rules.
  Hidden, locked and reference target layers are protected.
- Only instance layers change. Geometry, transforms and other attributes are retained.
  Unused definitions have no placed instances to move.

## RUTShowBlockLayers

The searchable overview opens with **all definitions**, including unassigned and
unused definitions. Untick **Include unassigned blocks** to show only saved rules.
Select a local row and choose **Assign layer** to open the same assignment dialog.
Linked/reference rows are read-only. The overview does not apply layer movements.

Existing `Urbanism.BlockLayer` metadata remains compatible; no model migration is
needed. There is no background layer enforcement.

## Validation

Validated in Rhino 8.36 on 2026-11-10: 13 naming test cases, 38 isolated document
checks and 94 live dialog/Undo checks. Coverage includes family detection, copies,
linked/nested protection, keyboard actions, sorting identity, resizing, warning
feedback and Undo/Redo. Automated fixtures are removed after tests. The temporary
manual RUT Block Playground scene has been removed.
