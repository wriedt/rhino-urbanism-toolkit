# -*- coding: utf-8 -*-
"""Lock-isolation regression checks in disposable Rhino documents."""
import importlib
import Rhino
import scriptcontext as sc
from System import Guid
import layer_tools as lt
importlib.reload(lt)


def run():
    docs, checks = [], []
    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)
    def document():
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.UndoRecordingEnabled = True
        docs.append(doc)
        return doc
    def add(doc, name, parent=None, locked=False, visible=True):
        layer = Rhino.DocObjects.Layer(); layer.Name = name
        layer.IsLocked = locked; layer.IsVisible = visible
        if parent is not None:
            layer.ParentLayerId = doc.Layers[parent].Id
        index = doc.Layers.Add(layer)
        assert index >= 0
        return index
    def undo(doc, redo=False):
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        value = doc.Redo() if redo else doc.Undo()
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        return value
    try:
        doc = document()
        a = add(doc, 'A'); b = add(doc, 'B', a)
        c = add(doc, 'C', a, locked=True)
        deep = add(doc, 'Deep', b)
        hidden = add(doc, 'Hidden', visible=False)
        other = add(doc, 'Other')
        aid, bid = doc.Layers[a].Id, doc.Layers[b].Id
        before = lt.snapshot(doc)
        lt.isolate_lock(doc, [bid], False)
        isolated = lt.snapshot(doc)
        check(isolated['visibility'] == before['visibility'], 'lock isolation preserves visibility')
        check(not doc.Layers[a].IsLocked and not doc.Layers[b].IsLocked, 'selected layers and parents remain unlocked')
        check(doc.Layers[0].IsLocked and doc.Layers[other].IsLocked, 'other layers including original current become locked')
        check(doc.Layers[deep].IsLocked and doc.Layers[c].IsLocked, 'excluded descendants and siblings lock')
        check(doc.Layers[hidden].IsLocked and not doc.Layers[hidden].IsVisible, 'hidden layers stay hidden and lock')
        check(undo(doc) and lt.snapshot(doc) == before, 'lock isolation Undo restores locks and current')
        check(lt.lock_key(doc) not in sc.sticky, 'Undo removes lock snapshot')
        check(undo(doc, True) and lt.snapshot(doc) == isolated, 'lock isolation Redo restores complete state')
        check(lt.lock_key(doc) in sc.sticky, 'Redo restores lock snapshot')
        first = sc.sticky[lt.lock_key(doc)]
        lt.isolate_lock(doc, [aid])
        check(not doc.Layers[c].IsLocked and not doc.Layers[deep].IsLocked, 'children default includes previously locked descendants')
        check(sc.sticky[lt.lock_key(doc)] == first, 'repeated lock isolation keeps first snapshot')
        before_restore = lt.snapshot(doc)
        lt.unisolate_lock(doc)
        check(lt.snapshot(doc) == before, 'restore returns original locks persistent flags current and visibility')
        check(undo(doc) and lt.snapshot(doc) == before_restore, 'lock restore Undo restores isolated state')
        check(lt.lock_key(doc) in sc.sticky, 'restore Undo recovers snapshot')
        check(undo(doc, True) and lt.snapshot(doc) == before, 'lock restore Redo restores original state')
        check(lt.unisolate_lock(doc) is False, 'restore without snapshot is harmless')
        # A locked parent with an implicitly unlocked child must round-trip.
        lt.locking(doc, {str(aid): (True, True), str(bid): (True, False)})
        before = lt.snapshot(doc)
        lt.isolate_lock(doc, [bid]); lt.unisolate_lock(doc)
        check(lt.snapshot(doc) == before, 'inherited and persistent locking round-trip')
        lt.update_all(doc, unlock=True)
        before = lt.snapshot(doc)
        lt.isolate_lock(doc, [bid])
        layer = lt.clone(doc.Layers[b]);layer.Name = 'Renamed';lt.modify(doc, layer)
        new = add(doc, 'New', locked=True)
        assert doc.Layers.Delete(hidden, True)
        lt.unisolate_lock(doc)
        check(doc.Layers[b].Name == 'Renamed' and not doc.Layers[b].IsLocked, 'renamed layers restore by identity')
        check(doc.Layers[new].IsLocked and doc.Layers[hidden].IsDeleted, 'new lock settings preserved and deleted layers skipped')
        # Lock and visibility snapshots have independent lifetimes.
        lt.isolate(doc, [aid])
        saved_visibility = sc.sticky[lt.key(doc)]
        lt.isolate_lock(doc, [bid])
        visible = lt.snapshot(doc)['visibility']
        lt.unisolate_lock(doc)
        check(lt.snapshot(doc)['visibility'] == visible and sc.sticky[lt.key(doc)] == saved_visibility,
              'lock restore leaves visibility isolation intact')
        lt.unisolate(doc)
        lt.isolate_lock(doc, [bid])
        locks = lt.snapshot(doc)['locking']
        lt.isolate(doc, [bid]);lt.unisolate(doc)
        check(lt.snapshot(doc)['locking'] == locks and lt.lock_key(doc) in sc.sticky,
              'visibility restore leaves lock isolation intact')
        lt.unisolate_lock(doc)
        # Hidden-only selection cannot become current without changing visibility.
        invisible = add(doc, 'Hidden target', visible=False)
        before = lt.snapshot(doc)
        try:
            lt.isolate_lock(doc, [doc.Layers[invisible].Id])
        except ValueError:
            pass
        else:
            raise AssertionError('hidden-only selection accepted')
        check(lt.snapshot(doc) == before and lt.lock_key(doc) not in sc.sticky, 'unavailable current layer failure rolls back')
        # Partial cancellation rolls back locks/current without touching either snapshot.
        real_escape = lt.check_escape
        count = [0]
        def cancel():
            count[0] += 1
            if count[0] == 3:
                raise RuntimeError('simulated Escape')
        lt.check_escape = cancel
        try:
            try:
                lt.isolate_lock(doc, [bid])
            except RuntimeError:
                pass
            else:
                raise AssertionError('cancel not triggered')
        finally:
            lt.check_escape = real_escape
        check(lt.snapshot(doc) == before and lt.lock_key(doc) not in sc.sticky, 'batch cancellation restores state')
        check(doc.Views.RedrawEnabled, 'cancellation restores redraw')
        for invalid in ([], [Guid.NewGuid()]):
            try:
                lt.isolate_lock(doc, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid selection accepted')
        check(lt.snapshot(doc) == before, 'invalid selections preserve state')
        other_doc = document()
        lt.isolate_lock(doc, [bid])
        check(not lt.unisolate_lock(other_doc) and lt.lock_key(doc) in sc.sticky, 'lock snapshots are document-specific')
        lt.unisolate_lock(doc)
        # Delete the original current layer and restore onto an eligible fallback.
        third = document();x = add(third, 'Target')
        lt.isolate_lock(third, [third.Layers[x].Id])
        assert third.Layers.Delete(0, True)
        check(lt.unisolate_lock(third) and not third.Layers[x].IsLocked, 'deleted original current uses fallback')
        print('PASS: {} lock-isolation checks'.format(len(checks)))
        return checks
    finally:
        for doc in docs:
            sc.sticky.pop(lt.key(doc), None)
            sc.sticky.pop(lt.lock_key(doc), None)
            doc.Dispose()


if __name__ == '__main__':
    run()
