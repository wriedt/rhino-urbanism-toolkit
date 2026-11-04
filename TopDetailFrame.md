# Top Detail Frame prototype

Rhino 8 / Python 3. A selectable model-space frame controls the pan of a
parallel World Top layout detail. This is an experimental standalone command,
not yet packaged in the Urbanism plug-in.

## Try it

1. Open a copy of a model with a layout and an ordinary rectangular Top detail.
2. Unlock the detail's viewport. Stay in page space so its border is selectable.
3. Open `TopDetailFrame.py` in Rhino's `ScriptEditor`, using Python 3, and Run.
4. Choose **Link**, then select the detail border.
5. Switch to the model Top viewport. A cyan rectangle at World Z=0 marks the view.
6. Select it and use ordinary **Move**, or the Gumball XY plane handle.
   After the command finishes, the layout detail pans to match.
7. Run the script again to link another detail, **Refresh**, or **Stop**.

The layout rectangle stays in place, and its scale stays unchanged. Existing
layout details hide the generated guide. New details created after linking may
show it; hide the guide in those details manually. Frame object names contain
the layout name and user text identifies the source detail.

## Scope and limitations

- Translation in World XY only. Scaling, rotation, vertical moves and reshaping
  leave the layout untouched and print a warning. Undo the unsupported edit.
- Top parallel views only; no perspective, tilted views or non-rectangular crops.
- Link only ordinary rectangular paper details. Rotated paper boundaries have
  not been tested. Existing in-plane view twist can be retained; editing it
  while linked requires Refresh.
- The detail must remain unlocked. Locking it suspends updates until unlocked.
- One-way control in this prototype. After editing a layout view directly,
  **Refresh** all tracked frames from the layouts before moving them again.
  Refresh discards pending frame edits. Layouts take priority on conflicts.
- The watcher runs on Rhino's UI idle event, at most five times per second,
  only outside commands and Undo/Redo. Updates occur after moving, not during drag.
- Links are session-only. Stop/restart, closing the document, or restarting Rhino
  leaves ordinary guide curves. Delete obsolete guides and link again. Copies of
  a guide are inert; only the original object ID controls the detail.
- Deleting a guide does not delete the detail. The session retains its ID so
  Undo Delete can recover the link. Do not change document units while linked.
- The frame is the undoable source of camera position. Idle camera updates do
  not create separate undo records. Native Move Undo/Redo resynchronized correctly
  in the live Rhino 8 test, with Redo remaining available.
- Save only after the pan has appeared. For now, stop the listener when done.

## Validation status

Tested live through Rhino MCP on 2026-10-22, in Rhino 8, using temporary layout
details with model units in metres and layout units in millimetres at 1:100.
The first run exposed the unavailable `DetailViewObject.ParentPageView` property;
the script now finds the owning layout by enumerating its details.

A follow-up regression reproduced creation in page space while a layout was
active: Rhino overwrote the attributes passed to `AddCurve`. The script now
sets and verifies `Space=ModelSpace` and an empty `ViewportId` after insertion.
Creation with an active layout, Refresh repairing a page-space frame, and a
subsequent native model-space Move all passed live tests. On rerunning an updated
script, the old listener is replaced while retaining the tracked frame IDs.

Passed: creating a linked frame of the expected 20 x 15 metre extent; native
Move with exact frame/detail alignment and preserved scale; native Undo and
Redo; rejection of Scale, Rotate and Z movement; recovery after undoing those
edits; direct layout pan followed by Refresh; moving two linked frames together;
deleting a frame without deleting its detail; Undo Delete followed by another
working Move; and stopping the listener. Temporary test frames and layout were
removed afterwards. Geometry comparisons used a 1e-6 model-unit tolerance.

Python syntax and five isolated translation-rule tests also pass. Mouse-driven
Gumball dragging, file close/reopen and rotated paper boundaries remain manual
checks. The script is still a session-only prototype, not a packaged command.

Checks to repeat before plug-in integration:

| Check | Expected result |
| --- | --- |
| Model in metres, layout in mm at 1:100 | Frame matches the visible model extent |
| Move frame +10 model units in X | Detail shows an area 10 units farther in X |
| Move again in Y | No accumulated drift; scale and paper rectangle unchanged |
| Undo and Redo moves, including multiple steps | Frame and detail remain aligned; Redo remains available |
| Gumball XY move; cancelled Move | Pan after release; no change after cancellation |
| Scale, rotate, Z-move, edit a vertex | Warning; detail unchanged; Undo restores usable frame |
| Two details; move both frames | Each linked detail follows only its own frame |
| Copy/delete guide; Undo Delete | Copy inert; detail survives deletion; original link recovers |
| Pan/zoom layout directly, then Refresh | Frame resets to current layout crop |
| Lock detail; Stop; close/reopen file | Clear warning or stopped listener, no stray callbacks |

Implementation references: RhinoCommon `RhinoViewport.GetNearRect`,
`SetCameraLocations(target, camera)`, `DetailViewObject.CommitViewportChanges`,
`ObjectAttributes.AddHideInDetailOverride`, and `RhinoApp.Idle`.

## Future development notes — paused 2026-10-22

These are requested ideas for a later version, not implemented features.
Development is paused at the working Top-view, XY-movement prototype.

### Transforming the frame

- Support ordinary dragging and Gumball movement as first-class interactions.
  Verify mouse-driven dragging, release, cancellation and Undo/Redo; native Move
  is tested, but Gumball dragging has not been verified yet.
- Support rotation within the frame's plane, updating the detail's view twist.
  Define the rotation pivot and preserve alignment when rotating about an
  arbitrary point, not just the frame centre.
- Support uniform scaling: a larger model frame shows a larger area through the
  same paper detail. For example, scaling the frame by 2 changes 1:100 to 1:200.
  Scaling about an arbitrary point must also reposition the view correctly.
- Consider live layout feedback while dragging, with a final committed update on
  release. Keep cancellation and Undo/Redo consistent across all interactions.
- Define unsupported transforms explicitly: non-uniform scaling, shear, mirror,
  out-of-plane movement/rotation and individual vertex edits are candidates.

### Other construction planes

- Keep Top as the initial supported view; later support other view planes.
- Investigate reading the CPlane stored on the detail's viewport as the initial
  reference. A detail has its own viewport; it is not necessarily linked to a
  separate named/model view, so avoid assuming such a link exists.
- Decide what to do when the stored CPlane and camera orientation disagree.
  Define whether the frame follows the view plane or an explicitly chosen
  CPlane, including its origin/elevation. Express supported transforms in that
  plane's local axes rather than World XY.
- Perspective views remain a separate future design problem.

### Recognisable model-space frame

- Give generated frames their own dedicated layer, for example
  `Urbanism::Layout Frames`, with a consistent colour and visibility controls.
  Keep them hidden in layout details, including details created after linking.
- Add associated text identifying the object, for example
  `LAYOUT FRAME | Page 1 | Ground floor | 1:100`. Update it with layout/detail
  renames and scale changes, and keep it attached to the frame when transformed.
- Investigate a plug-in custom object or other dedicated object representation,
  with recognisable selection feedback and properties. Treat this as an option
  to prototype, not a confirmed capability of the current Python script.
- Compare that approach with a standard curve carrying persistent link metadata
  plus plug-in-drawn labels. Evaluate editing, snapping, copying, save/reopen,
  and behaviour when the plug-in is unavailable.

### Warnings and protection

- Warn when deleting a linked frame. Explain that the operation removes the
  controller/guide, and define explicitly whether the layout detail survives
  (preferred default: keep the detail). Offer cancel or an intentional unlink.
- Warn clearly on an unsupported transform, ideally before committing it; retain
  the last valid framing and offer a predictable recovery path.
- Investigate which Rhino events/custom-object hooks allow a real cancellable
  warning. Do not assume an after-the-fact event can veto deletion or a transform.
- Cover batch edits, Delete, layer deletion, copied frames, Undo/Redo and repeated
  warnings during a drag. Avoid modal warning loops on every redraw.

### Integration considerations

- Persist frame/detail links across save/reopen, and restore their controllers
  when the Urbanism plug-in loads.
- Establish rules for edits made on the layout versus through the model frame,
  deleted/duplicated layouts and details, and stale or broken links.
- Package the command in the Urbanism plug-in after the interactions above have
  been validated in Rhino.
