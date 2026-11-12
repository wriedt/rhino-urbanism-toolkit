# -*- coding: utf-8 -*-
"""General layer utilities; isolation state is per document and session."""
import copy
import Rhino
import scriptcontext as sc
from System import Guid

PREFIX = 'RUT.LayerIsolation.'


def key(doc):
    return PREFIX + str(doc.RuntimeSerialNumber)


def lock_key(doc):
    return key(doc) + '.Locks'


def layers(doc):
    return [layer for layer in doc.Layers if not layer.IsDeleted]


def ordered(doc):
    pending = {layer.Id: layer for layer in layers(doc)}
    result = []
    while pending:
        ready = [layer for layer in pending.values() if layer.ParentLayerId not in pending]
        if not ready:
            raise ValueError('Invalid layer hierarchy.')
        for layer in ready:
            result.append(layer)
            del pending[layer.Id]
    return result


def snapshot(doc):
    return dict(current=str(doc.Layers.CurrentLayer.Id), visibility={
        str(layer.Id): (layer.IsVisible, layer.GetPersistentVisibility())
        for layer in layers(doc)}, locking={
        str(layer.Id): (layer.IsLocked, layer.GetPersistentLocking())
        for layer in layers(doc)})


def clone(layer):
    result = Rhino.DocObjects.Layer()
    result.CopyAttributesFrom(layer)
    return result


def is_zero(layer):
    """The root layer named 0 is protected; a sublayer named 0 is ordinary."""
    return layer.Name == '0' and layer.ParentLayerId == Guid.Empty


def protect_zero(layer):
    layer.IsVisible = True
    layer.SetPersistentVisibility(True)
    layer.IsLocked = False
    layer.SetPersistentLocking(False)


def zero_needs_update(doc):
    return any(is_zero(layer) and
               (not layer.IsVisible or not layer.GetPersistentVisibility()
                or layer.IsLocked or layer.GetPersistentLocking()) for layer in layers(doc))


def enforce_zero(doc):
    for original in layers(doc):
        if is_zero(original):
            layer = clone(original)
            if (not layer.IsVisible or not layer.GetPersistentVisibility()
                    or layer.IsLocked or layer.GetPersistentLocking()):
                modify(doc, layer)


def modify(doc, layer):
    if is_zero(layer):
        protect_zero(layer)
    if not doc.Layers.Modify(layer, layer.Index, True):
        raise RuntimeError('Could not update layer "{}".'.format(layer.FullPath))


def check_escape():
    if sc.escape_test(False):
        raise RuntimeError('Layer operation cancelled; previous settings restored.')


def visibility(doc, values, allow_cancel=False):
    values = dict(values)
    values.update({str(layer.Id): (True, True) for layer in layers(doc) if is_zero(layer)})
    # Parent edits propagate to children; always read each child afresh.
    for original in ordered(doc):
        if allow_cancel:
            check_escape()
        value = values.get(str(original.Id))
        if value is None:
            continue
        layer = clone(doc.Layers.FindId(original.Id))
        visible, persistent = value
        if layer.IsVisible == visible and layer.GetPersistentVisibility() == persistent:
            continue
        layer.IsVisible = visible
        layer.SetPersistentVisibility(persistent)
        modify(doc, layer)


def set_current(doc, layer_id):
    layer = doc.Layers.FindId(Guid(layer_id))
    if layer is None or layer.IsDeleted:
        return False
    if not can_be_current(doc, layer):
        return False
    ancestors = []
    parent = layer
    while parent is not None:
        ancestors.append(parent.Id)
        parent = doc.Layers.FindId(parent.ParentLayerId)
    visibility(doc, {str(value): (True, True) for value in ancestors})
    return doc.Layers.SetCurrentLayerIndex(layer.Index, True)


def finish_undo(sender, event):
    if not (event.IsEndUndo or event.IsEndRedo):
        return
    pending = sc.sticky.pop(PREFIX + 'pending', [])
    for doc, saved in pending:
        recording = doc.UndoRecordingEnabled
        redraw = doc.Views.RedrawEnabled
        try:
            # Native layer Undo completes before restoring the current layer.
            # Doing this inside the custom Undo callback corrupts native Redo.
            doc.UndoRecordingEnabled = False
            doc.Views.RedrawEnabled = False
            restore_locks(doc, saved.get('locking', {}), saved['current'], True)
            set_current(doc, saved['current'])
            visibility(doc, saved['visibility'])
        finally:
            doc.UndoRecordingEnabled = recording
            doc.Views.RedrawEnabled = redraw
            if redraw:
                doc.Views.Redraw()


def close_document(sender, event):
    sc.sticky.pop(key(event.Document), None)
    sc.sticky.pop(lock_key(event.Document), None)


def ensure_undo_handler():
    if PREFIX + 'handler' not in sc.sticky:
        Rhino.Commands.Command.UndoRedo += finish_undo
        sc.sticky[PREFIX + 'handler'] = finish_undo
    if PREFIX + 'close_handler' not in sc.sticky:
        Rhino.RhinoDoc.CloseDocument += close_document
        sc.sticky[PREFIX + 'close_handler'] = close_document


def undo_state(sender, event):
    state_key, old, saved = event.Tag
    inverse = copy.deepcopy(sc.sticky.get(state_key))
    inverse_saved = snapshot(event.Document)
    event.Document.AddCustomUndoEvent('Layer isolation state', undo_state,
                                      (state_key, inverse, inverse_saved))
    if old is None:
        sc.sticky.pop(state_key, None)
    else:
        sc.sticky[state_key] = copy.deepcopy(old)
    sc.sticky.setdefault(PREFIX + 'pending', []).append((event.Document, saved))


def transaction(doc, name, operation, state_key=None):
    ensure_undo_handler()
    sc.escape_test(False, True)
    backups = [clone(layer) for layer in layers(doc)]
    before = snapshot(doc)
    state_key = state_key or key(doc)
    old = copy.deepcopy(sc.sticky.get(state_key))
    redraw = doc.Views.RedrawEnabled
    zero_dirty = zero_needs_update(doc)
    undo = doc.BeginUndoRecord(name)
    try:
        doc.Views.RedrawEnabled = False
        enforce_zero(doc)
        result = operation()
        if zero_dirty or sc.sticky.get(state_key) != old or before['current'] != str(doc.Layers.CurrentLayer.Id):
            if not doc.AddCustomUndoEvent('Layer isolation state', undo_state, (state_key, old, before)):
                raise RuntimeError('Could not register isolation Undo.')
        return result
    except Exception:
        try:
            restore_locks(doc, before['locking'], before['current'], True)
            set_current(doc, before['current'])
            for layer in backups:
                modify(doc, layer)
            visibility(doc, before['visibility'])
        finally:
            if old is None:
                sc.sticky.pop(state_key, None)
            else:
                sc.sticky[state_key] = old
        raise
    finally:
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.RedrawEnabled = redraw
        if redraw:
            doc.Views.Redraw()


def isolation_layers(doc, selected_ids, include_children=True):
    table = {layer.Id: layer for layer in layers(doc)}
    selected = {Guid(str(value)) for value in selected_ids}
    if not selected or not selected.issubset(table):
        raise ValueError('Select objects on existing layers first.')
    keep = set(selected)
    if include_children:
        for layer in ordered(doc):
            if layer.ParentLayerId in keep:
                keep.add(layer.Id)
    for layer_id in list(keep):
        parent = table[layer_id].ParentLayerId
        seen = set()
        while parent != Guid.Empty:
            if parent in seen or parent not in table:
                raise ValueError('Invalid layer hierarchy.')
            seen.add(parent)
            keep.add(parent)
            parent = table[parent].ParentLayerId
    # Add 0 after descendant expansion: its children are not implicitly retained.
    keep.update(layer.Id for layer in table.values() if is_zero(layer))
    return keep


def can_be_current(doc, layer):
    if layer.IsReference:
        return False
    while layer is not None:
        if layer.IsLocked:
            return False
        layer = doc.Layers.FindId(layer.ParentLayerId)
    return True


def isolate(doc, selected_ids, include_children=True):
    keep = isolation_layers(doc, selected_ids, include_children)
    before = snapshot(doc)

    def apply():
        if doc.Layers.CurrentLayer.Id not in keep:
            candidates = [layer for layer in ordered(doc)
                          if layer.Id in keep and can_be_current(doc, layer)]
            if not any(set_current(doc, str(layer.Id)) for layer in candidates):
                raise ValueError('No isolated layer can be current. Choose an unlocked local layer.')
        visibility(doc, {str(layer.Id): (layer.Id in keep, layer.Id in keep) for layer in layers(doc)}, True)
        if key(doc) not in sc.sticky:
            sc.sticky[key(doc)] = before
        return len(keep)

    count = transaction(doc, 'Isolate layers', apply)
    print('Isolated {} layers including required parents. Run UnisolateLayer.py to restore.'.format(count))
    return count


def unisolate(doc):
    saved = sc.sticky.get(key(doc))
    if saved is None:
        if zero_needs_update(doc):
            transaction(doc, 'Keep layer 0 visible and unlocked', lambda: None)
        print('There is no saved layer isolation in this document.')
        return False

    restore_values = snapshot(doc)['visibility']
    restore_values.update(saved['visibility'])

    def apply():
        if not set_current(doc, saved['current']):
            candidates = [layer for layer in layers(doc)
                          if saved['visibility'].get(str(layer.Id), (True, True))[0]
                          and can_be_current(doc, layer)]
            if not any(set_current(doc, str(layer.Id)) for layer in candidates):
                raise ValueError('Cannot restore: no available visible current layer. Unlock one and retry.')
        visibility(doc, restore_values, True)
        sc.sticky.pop(key(doc), None)
        return True

    result = transaction(doc, 'Restore layer visibility', apply)
    print('Restored layer visibility. New layers retain their current settings.')
    return result


def locking(doc, values, allow_cancel=False):
    values = dict(values)
    values.update({str(layer.Id): (False, False) for layer in layers(doc) if is_zero(layer)})
    for original in ordered(doc):
        if allow_cancel:
            check_escape()
        value = values.get(str(original.Id))
        if value is None:
            continue
        layer = clone(doc.Layers.FindId(original.Id))
        locked, persistent = value
        if layer.IsLocked == locked and layer.GetPersistentLocking() == persistent:
            continue
        layer.IsLocked = locked
        layer.SetPersistentLocking(persistent)
        modify(doc, layer)


def restore_locks(doc, values, current=None, reveal_current=False, allow_cancel=False):
    values = dict(values)
    values.update({str(layer.Id): (False, False) for layer in layers(doc) if is_zero(layer)})
    # Unlock required destinations before switching away from a layer that must
    # become locked. Parent-first edits preserve inherited persistent locks.
    locking(doc, {k: v for k, v in values.items() if not v[0]}, allow_cancel)

    def eligible(layer):
        if layer.IsReference:
            return False
        while layer is not None:
            if values.get(str(layer.Id), (layer.IsLocked, False))[0]:
                return False
            layer = doc.Layers.FindId(layer.ParentLayerId)
        return True

    candidates = [layer for layer in layers(doc) if eligible(layer)
                  and (layer.IsVisible or (reveal_current and str(layer.Id) == current))]
    candidates.sort(key=lambda layer: (str(layer.Id) != current,
                                      layer.Id != doc.Layers.CurrentLayer.Id))
    for layer in candidates:
        changed = (set_current(doc, str(layer.Id)) if reveal_current else
                   doc.Layers.SetCurrentLayerIndex(layer.Index, True))
        if changed:
            break
    else:
        raise ValueError('No visible unlocked local layer can be current; settings were preserved.')
    locking(doc, values, allow_cancel)


def isolate_lock(doc, selected_ids, include_children=True):
    keep = isolation_layers(doc, selected_ids, include_children)
    before = snapshot(doc)

    def apply():
        values = {str(layer.Id): (layer.Id not in keep, layer.Id not in keep)
                  for layer in layers(doc)}
        # Pick a visible retained layer as current without showing hidden layers.
        desired = next((str(layer.Id) for layer in ordered(doc)
                        if layer.Id in keep and layer.IsVisible and not layer.IsReference), None)
        if doc.Layers.CurrentLayer.Id in keep:
            desired = str(doc.Layers.CurrentLayer.Id)
        restore_locks(doc, values, desired, allow_cancel=True)
        if lock_key(doc) not in sc.sticky:
            sc.sticky[lock_key(doc)] = dict(current=before['current'], locking=before['locking'])
        return len(keep)

    count = transaction(doc, 'Isolate layer locks', apply, lock_key(doc))
    print('Kept {} layers unlocked including required parents. Run RUTUnisolateLockLayer to restore.'.format(count))
    return count


def unisolate_lock(doc):
    saved = sc.sticky.get(lock_key(doc))
    if saved is None:
        if zero_needs_update(doc):
            transaction(doc, 'Keep layer 0 visible and unlocked', lambda: None, lock_key(doc))
        print('There is no saved layer lock isolation in this document.')
        return False
    values = snapshot(doc)['locking']
    values.update(saved['locking'])

    def apply():
        restore_locks(doc, values, saved['current'], allow_cancel=True)
        sc.sticky.pop(lock_key(doc), None)
        return True

    result = transaction(doc, 'Restore layer locks', apply, lock_key(doc))
    print('Restored layer locks. Visibility is unchanged.')
    return result


def update_all(doc, visible=False, unlock=False, expansion=None):
    def apply():
        if visible:
            visibility(doc, {str(layer.Id): (True, True) for layer in layers(doc)}, True)
        for original in ordered(doc):
            check_escape()
            layer = clone(doc.Layers.FindId(original.Id))
            changed = False
            if unlock and (layer.IsLocked or layer.GetPersistentLocking()):
                layer.IsLocked = False
                layer.SetPersistentLocking(False)
                changed = True
            if expansion is not None and layer.IsExpanded != expansion:
                layer.IsExpanded = expansion
                changed = True
            if changed:
                modify(doc, layer)
    return transaction(doc, 'Update layers', apply)


def toggle_expansion(doc):
    return update_all(doc, expansion=not any(layer.IsExpanded for layer in layers(doc)))


def pick_layers(doc, lock=False):
    getter = Rhino.Input.Custom.GetObject()
    try:
        getter.SetCommandPrompt('Select objects whose layers to keep unlocked' if lock
                                else 'Select objects whose layers to isolate')
        getter.SubObjectSelect = False
        getter.GroupSelect = True
        getter.EnablePreSelect(True, True)
        children = Rhino.Input.Custom.OptionToggle(True, 'No', 'Yes')
        getter.AddOptionToggle('IncludeChildren', children)
        while True:
            result = getter.GetMultiple(1, 0)
            if result == Rhino.Input.GetResult.Option:
                continue
            if result != Rhino.Input.GetResult.Object:
                return None
            ids = set()
            for index in range(getter.ObjectCount):
                obj = doc.Objects.FindId(getter.Object(index).ObjectId)
                if obj is not None:
                    ids.add(doc.Layers[obj.Attributes.LayerIndex].Id)
            return (ids, children.CurrentValue) if ids else None
    finally:
        getter.Dispose()


def run_command(action):
    try:
        return action()
    except (ValueError, RuntimeError) as error:
        print('Layer tools: ' + str(error))
        return False



