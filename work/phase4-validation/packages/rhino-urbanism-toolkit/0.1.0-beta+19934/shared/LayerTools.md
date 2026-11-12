# Layer utilities

Eight Rhino 8 / Python 3 commands share `layer_tools.py`. Keep that helper beside
the scripts. The following RUT-prefixed aliases are installed in the configured
Rhino instance. You can also run a file from the Script Editor or a toolbar macro.

| Rhino alias | Script | Behavior |
|---|---|---|
| `RUTIsolateLayer` | `IsolateLayer.py` | Select objects and show their layers, required parent layers and, by default, child layers. Hide other layers. |
| `RUTUnisolateLayer` | `UnisolateLayer.py` | Restore visibility and the current layer from before the first isolation. |
| `RUTIsolateLockLayer` | `IsolateLockLayer.py` | Keep selected objects' layers, required parents and optional children unlocked; lock the other layers. |
| `RUTUnisolateLockLayer` | `UnisolateLockLayer.py` | Restore locks and the current layer from before the first lock isolation. |
| `RUTShowAllLayers` | `ShowAllLayers.py` | Show all layers, including descendants of hidden parents. |
| `RUTUnlockAllLayers` | `UnlockAllLayers.py` | Unlock all layers, including descendants of locked parents. |
| `RUTShowAndUnlockAllLayers` | `ShowAndUnlockAllLayers.py` | Show and unlock all layers. |
| `RUTToggleLayerExpansion` | `ToggleLayerExpansion.py` | Collapse every layer row if any are expanded; otherwise expand all rows. |

## Layer 0 exception

If a root layer named exactly `0` exists, all eight tools keep it **visible and
unlocked**, including persistent visibility/locking settings. They also repair it
if it was already hidden or locked. Isolation, restoration from older snapshots,
and Undo/Redo honor this exception. The tools do not create layer `0` when absent.

This is a name-based rule for the root layer, not layer-table index zero. A sublayer
such as `Building::0` is ordinary. Children of root `0` follow the normal isolation
rules; they are not automatically exempted. Selection cancellation makes no changes.
The exception takes precedence over the visibility/lock preservation described below.

## Isolate and restore

1. Run `IsolateLayer.py` and select one or more objects, or use preselection.
2. At the selection prompt, `IncludeChildren=Yes` is the default. Switch to `No`
   to exclude child layers. To change this option, start without preselection.
3. Run `UnisolateLayer.py` to return to the original visibility.

All objects on the retained layers remain visible, including objects directly on
required parent layers. Child layers are shown even if they were previously off.
Choosing a sublayer does not include its siblings. Individually hidden objects
remain hidden, locking is unchanged, and viewport-specific visibility overrides
are unchanged. This is layer isolation, not isolation of individual objects.

Repeated isolation keeps the snapshot from before the **first** isolation.
Showing all layers or manually changing visibility does not discard it.
Restoring without a saved isolation prints a message and changes nothing.

Rhino cannot hide its current layer. Isolation temporarily makes an eligible
retained layer current when necessary; restoration returns to the former current
layer. A locked/reference layer is never forced to become current. If no eligible
layer is available, the operation stops and rolls back. If the former current
layer was deleted or made unavailable, restoration chooses another eligible
layer that was originally visible, or a new layer. If none exists, unlock a
suitable layer and retry; the saved snapshot is retained.

Layer IDs make restoration survive renaming. Deleted layers are skipped. New
layers keep their visibility settings, subject to their parents' restored
visibility. Restoration does not restore layer names, hierarchy, locking,
geometry, object visibility, or layer-panel expansion.

The snapshot belongs to the current document and the current Rhino session;
it survives helper reloads but is not saved in the model. Restore before closing
the document or Rhino if you want to retain the original visibility.

## Undo and cancellation

Each operation is one Undo step, with Redo support. Isolation's saved snapshot and
temporary current layer follow Undo/Redo. Escape at the selection prompt changes
nothing. Escape during a batch update or an update failure rolls back the batch.
Redraw always returns to its previous enabled/disabled state.

## Isolate by locking

Select objects and run `RUTIsolateLockLayer` to keep their layers editable while
locking the surroundings. `IncludeChildren=Yes` is the default, matching visibility
isolation. Required parent layers stay unlocked; objects directly on those parent
layers also remain editable. Included children are unlocked even if previously
locked. Individually locked objects remain locked.

Run `RUTUnisolateLockLayer` to restore the original layer locks and persistent child
locking settings. Repeated isolation preserves the first snapshot. Renamed layers
restore by ID, deleted layers are skipped, and new layers retain their lock settings
subject to their parents' restored locking. The snapshot is document-specific and
session-only, with Undo/Redo and cancellation rollback.

Visibility is unchanged by either lock command. Rhino cannot lock the current
layer, so isolation switches to a visible, local retained layer when necessary.
Restoration prefers the original current layer, with a visible unlocked fallback
if it was deleted or made unavailable. With no suitable current layer, the command
rolls back and retains any saved restore point.

Lock isolation and visibility isolation have independent snapshots: restoring one
does not consume the other's snapshot or change its visibility/lock settings.

## Toolbar macros

Use the same pattern for any script in the table. The scripts themselves do not
install aliases; the configured aliases use these full paths. Adjust them if you
move the project or use another Rhino installation.

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\IsolateLayer.py"
```

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\UnisolateLayer.py"
```

## Validation

`test_layer_tools_rhino.py` exercises disposable Rhino documents, including
visibility inheritance, repeated isolation, Undo/Redo, changed/deleted layers,
document separation, current-layer fallback, locking, redraw and rollback.
`test_layer_tools_live_rhino.py` checks actual preselection and both isolation
and lock-isolation command pairs, then removes its temporary point and layer and
restores the user's selection, locks and visibility. Live tests require no existing
isolation. `test_layer_lock_tools_rhino.py` covers lock inheritance, restoration,
Undo/Redo, changed/deleted layers, document separation, cancellation and interaction
with visibility isolation in disposable documents.
`test_layer_zero_rhino.py` covers the root `0` exception across all eight tools,
older snapshots, Undo/Redo, sublayer names and layers created after isolation.
