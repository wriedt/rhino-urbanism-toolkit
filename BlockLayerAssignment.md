# Block home layers

Use these RUT-prefixed Rhino commands:

| Command | Behavior |
|---|---|
| `RUTAssignBlockLayer` | Save or remove a definition-wide home-layer rule without moving copies. |
| `RUTApplyBlockLayers` | Review and apply saved rules; optionally include local nested instances. |
| `RUTShowBlockLayers` | Browse all definitions and edit the selected local definition's rule. |

The overview includes unassigned and unused definitions by default. Untick
**Include unassigned blocks** to filter to saved rules. **Assign layer** opens the
assignment dialog; **Save** writes its rule. **No home layer** removes a rule.

Apply reviews the whole model. **Include nested block instances** defaults to off.
Linked/reference blocks are skipped. Hidden/locked copies and layers are protected.
A nested edit is shared by all occurrences of its parent definition and is skipped
if any occurrence is protected. Missing/invalid rules do not create layers or move
objects. Use the overview to repair them. Only instance layers change.

Existing `Urbanism.BlockLayer` metadata remains compatible. There is no background
enforcement. Each save or apply is one Undo step. Escape/X cancels.

Tables support column sorting, window/column resizing and full-value tooltips.
Enter/Space invokes the highlighted primary action, preserving normal text input
and open-dropdown selection. Errors appear as coral warnings.

Underlying script filenames remain stable. Example toolbar macro:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\AssignBlockLayer.py"
```

See [Block commands](BlockCommands.md) for complete behavior, safeguards and validation.
