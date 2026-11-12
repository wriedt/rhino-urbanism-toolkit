# -*- coding: utf-8 -*-
"""Run in Rhino Python 3. Tests use disposable headless documents only."""
import importlib
import Rhino
import scriptcontext as sc
from System import Guid
import layer_tools as lt
importlib.reload(lt)


def run():
    checks = []
    docs = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def document():
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.UndoRecordingEnabled = True
        docs.append(doc)
        return doc

    def add(doc, name, parent=None, visible=True, locked=False):
        layer = Rhino.DocObjects.Layer()
        layer.Name = name
        layer.IsVisible = visible
        layer.IsLocked = locked
        if parent is not None:
            layer.ParentLayerId = doc.Layers[parent].Id
        index = doc.Layers.Add(layer)
        assert index >= 0
        return index

    def undo(doc, redo=False):
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        result = doc.Redo() if redo else doc.Undo()
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        return result

    def state(doc):
        return lt.snapshot(doc)

    def visible(doc, index):
        return doc.Layers[index].IsVisible

    try:
        doc = document()
        a = add(doc, 'A')
        b = add(doc, 'B', a)
        c = add(doc, 'C', a, False)
        deep = add(doc, 'Deep', b)
        other = add(doc, 'Other')
        hidden = add(doc, 'Hidden', visible=False)
        locked = add(doc, 'Locked', locked=True)
        original = state(doc)
        aid, bid = doc.Layers[a].Id, doc.Layers[b].Id
        keep = lt.isolation_layers(doc, [bid, bid], False)
        check(keep == {aid, bid}, 'selected layers deduplicate and include ancestors only')
        check(lt.isolation_layers(doc, [bid], True) == {aid, bid, doc.Layers[deep].Id},
              'children included without including siblings')
        lt.isolate(doc, [bid], False)
        check(visible(doc, a) and visible(doc, b) and not visible(doc, deep), 'isolate without children')
        check(not visible(doc, 0) and not visible(doc, other), 'unrelated layers hidden including former current')
        check(doc.Layers[locked].IsLocked, 'isolation preserves locking')
        check(lt.key(doc) in sc.sticky, 'isolation stores restore point')
        check(undo(doc), 'isolation Undo executes')
        check(state(doc) == original, 'Undo restores visibility and current layer')
        check(lt.key(doc) not in sc.sticky, 'Undo removes restore point')
        check(undo(doc, True), 'isolation Redo executes')
        check(lt.key(doc) in sc.sticky and not visible(doc, other), 'Redo restores isolation and restore point')
        lt.isolate(doc, [aid])
        check(visible(doc, c) and visible(doc, deep), 'children default includes previously hidden descendants')
        check(sc.sticky[lt.key(doc)] == original, 'repeated isolation preserves first snapshot')
        lt.unisolate(doc)
        check(state(doc) == original, 'restore returns directly to original state')
        check(lt.key(doc) not in sc.sticky, 'restore consumes snapshot')
        check(undo(doc), 'restore Undo executes')
        check(lt.key(doc) in sc.sticky and not visible(doc, other), 'restore Undo restores isolation state')
        check(undo(doc, True), 'restore Redo executes')
        check(state(doc) == original and lt.key(doc) not in sc.sticky, 'restore Redo is complete')
        check(lt.unisolate(doc) is False, 'restore without isolation is harmless')
        before = state(doc)
        for invalid in ([], [Guid.NewGuid()]):
            try:
                lt.isolate(doc, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid selection accepted')
        check(state(doc) == before and lt.key(doc) not in sc.sticky, 'invalid selections change nothing')
        lt.isolate(doc, [bid])
        layer = lt.clone(doc.Layers[b]); layer.Name = 'Renamed'; lt.modify(doc, layer)
        new = add(doc, 'New layer', visible=False)
        check(doc.Layers.Delete(hidden, True), 'delete an original layer during isolation')
        lt.unisolate(doc)
        check(doc.Layers[b].Name == 'Renamed' and visible(doc, b), 'renamed layers restore by identity')
        check(not visible(doc, new), 'new layer visibility retained')
        check(doc.Layers[hidden].IsDeleted, 'deleted layers stay deleted')
        # Hidden parent with remembered visible child must round-trip exactly.
        values = {str(aid): (False, False), str(bid): (False, True)}
        lt.visibility(doc, values)
        before = state(doc)
        lt.isolate(doc, [bid])
        lt.unisolate(doc)
        check(state(doc) == before, 'hidden parent and persistent child visibility round-trip')
        lt.update_all(doc, visible=True)
        check(all(layer.IsVisible and layer.GetPersistentVisibility() for layer in lt.layers(doc)),
              'show all includes hidden descendants and persistent visibility')
        check(doc.Layers[locked].IsLocked, 'show all preserves locks')
        lt.update_all(doc, unlock=True)
        check(all(not layer.IsLocked and not layer.GetPersistentLocking() for layer in lt.layers(doc)),
              'unlock all clears persistent locking')
        lt.update_all(doc, expansion=False)
        lt.toggle_expansion(doc)
        check(all(layer.IsExpanded for layer in lt.layers(doc)), 'toggle expands all collapsed layers')
        lt.toggle_expansion(doc)
        check(not any(layer.IsExpanded for layer in lt.layers(doc)), 'toggle collapses expanded layers')
        lt.update_all(doc, visible=True, unlock=True)
        check(all(layer.IsVisible and not layer.IsLocked for layer in lt.layers(doc)), 'combined show/unlock')
        doc.Views.RedrawEnabled = False
        lt.update_all(doc, visible=True)
        check(not doc.Views.RedrawEnabled, 'previous redraw-disabled state retained')
        doc.Views.RedrawEnabled = True
        # Inject an actual partial update failure and ensure rollback/state retention.
        before = state(doc)
        real = lt.modify
        calls = [0]
        def fail_once(d, layer):
            calls[0] += 1
            if calls[0] == 2:
                raise RuntimeError('injected failure')
            return real(d, layer)
        lt.modify = fail_once
        try:
            try:
                lt.isolate(doc, [bid])
            except RuntimeError:
                pass
            else:
                raise AssertionError('failure not injected')
        finally:
            lt.modify = real
        check(state(doc) == before and lt.key(doc) not in sc.sticky, 'partial failure rolls back visibility/current/state')
        check(doc.Views.RedrawEnabled, 'failure restores redraw')
        before = state(doc)
        real_escape = lt.check_escape
        calls = [0]
        def cancel_after_one():
            calls[0] += 1
            if calls[0] == 2:
                raise RuntimeError('simulated Escape')
        lt.check_escape = cancel_after_one
        try:
            try:
                lt.isolate(doc, [bid])
            except RuntimeError:
                pass
            else:
                raise AssertionError('cancellation not injected')
        finally:
            lt.check_escape = real_escape
        check(state(doc) == before and lt.key(doc) not in sc.sticky, 'batch cancellation rolls back partial edits')
        check(doc.Views.RedrawEnabled, 'cancellation restores redraw')
        # A new child keeps its persistent setting when its parent is hidden again.
        lt.visibility(doc, {str(aid): (False, False)})
        lt.isolate(doc, [aid])
        new_child = add(doc, 'New child', a)
        lt.unisolate(doc)
        check(not visible(doc, a) and not visible(doc, new_child)
              and doc.Layers[new_child].GetPersistentVisibility(),
              'new child respects restored hidden parent and remembers its own visibility')
        # Exercise lock inheritance and Undo for the remaining utility commands.
        layer = lt.clone(doc.Layers[a]); layer.IsLocked = True
        lt.modify(doc, layer)
        check(doc.Layers[b].IsLocked, 'parent locking propagates to child')
        lt.update_all(doc, unlock=True)
        check(not doc.Layers[a].IsLocked and not doc.Layers[b].IsLocked,
              'unlock all clears inherited parent/child locking')
        check(undo(doc) and doc.Layers[a].IsLocked, 'unlock all is one Undo step')
        check(undo(doc, True) and not doc.Layers[a].IsLocked, 'unlock all supports Redo')
        before = state(doc)
        lt.update_all(doc, visible=True)
        check(undo(doc) and state(doc) == before, 'show all is one Undo step')
        check(undo(doc, True) and all(l.IsVisible for l in lt.layers(doc)), 'show all supports Redo')
        lt.update_all(doc, expansion=False)
        layer = lt.clone(doc.Layers[a]); layer.IsExpanded = True
        lt.modify(doc, layer)
        lt.toggle_expansion(doc)
        check(not any(l.IsExpanded for l in lt.layers(doc)), 'mixed expansion collapses all rows')
        second = document()
        target = add(second, 'Target')
        lt.isolate(doc, [bid])
        check(lt.unisolate(second) is False, 'restore points are document-specific')
        lt.isolate(second, [second.Layers[target].Id])
        lt.unisolate(second)
        check(lt.key(doc) in sc.sticky, 'restoring another document preserves first restore point')
        lt.unisolate(doc)
        # Original current layer deleted: restore uses an eligible visible layer.
        third = document()
        x = add(third, 'Target')
        lt.isolate(third, [third.Layers[x].Id])
        check(third.Layers.Delete(0, True), 'original current layer can be deleted while isolated')
        check(lt.unisolate(third) and visible(third, x), 'deleted original current layer uses fallback')
        # All isolated layers locked: fail without silently unlocking anything.
        fourth = document()
        x = add(fourth, 'Locked target', locked=True)
        before = state(fourth)
        try:
            lt.isolate(fourth, [fourth.Layers[x].Id])
        except ValueError:
            pass
        else:
            raise AssertionError('locked current target accepted')
        check(state(fourth) == before and fourth.Layers[x].IsLocked, 'locked target failure is atomic')
        print('PASS: {} layer-tool checks'.format(len(checks)))
        return checks
    finally:
        for doc in docs:
            sc.sticky.pop(lt.key(doc), None)
            doc.Dispose()


if __name__ == '__main__':
    run()
