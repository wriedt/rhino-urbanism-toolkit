# -*- coding: utf-8 -*-
"""Root layer 0 exception checks in a disposable Rhino document."""
import importlib
import Rhino
import scriptcontext as sc
import layer_tools as lt
importlib.reload(lt)


def run():
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.UndoRecordingEnabled = True
    checks = []
    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)
    def add(name, parent=None):
        layer = Rhino.DocObjects.Layer();layer.Name = name
        if parent is not None:
            layer.ParentLayerId = doc.Layers[parent].Id
        return doc.Layers.Add(layer)
    def good():
        layer = doc.Layers[z]
        return (layer.IsVisible and layer.GetPersistentVisibility()
                and not layer.IsLocked and not layer.GetPersistentLocking())
    def dirty():
        # Seed pre-existing/manual settings without using the protected helpers.
        layer = lt.clone(doc.Layers[z]);layer.IsVisible = False
        layer.SetPersistentVisibility(False);layer.IsLocked = True
        layer.SetPersistentLocking(True)
        assert doc.Layers.Modify(layer, z, True)
    def undo(redo=False):
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        result = doc.Redo() if redo else doc.Undo()
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)
        return result
    try:
        z = add('0');child = add('Child', z)
        target = add('Target');nested_zero = add('0', target)
        tid = doc.Layers[target].Id
        check(z != 0 and lt.is_zero(doc.Layers[z]) and not lt.is_zero(doc.Layers[0]), 'exception uses root name, not table index')
        check(not lt.is_zero(doc.Layers[nested_zero]), 'sublayer named 0 is ordinary')
        keep = lt.isolation_layers(doc, [tid], False)
        check(doc.Layers[z].Id in keep and doc.Layers[child].Id not in keep, 'zero retained without implicitly retaining its children')
        lt.isolate(doc, [tid], False)
        check(good() and not doc.Layers[child].IsVisible and not doc.Layers[nested_zero].IsVisible, 'visibility isolation protects only root zero')
        lt.unisolate(doc)
        lt.isolate_lock(doc, [tid], False)
        check(good() and doc.Layers[child].IsLocked and doc.Layers[nested_zero].IsLocked, 'lock isolation protects only root zero')
        lt.unisolate_lock(doc)
        for label, action in [
            ('show all', lambda: lt.update_all(doc, visible=True)),
            ('unlock all', lambda: lt.update_all(doc, unlock=True)),
            ('show and unlock', lambda: lt.update_all(doc, visible=True, unlock=True)),
            ('toggle expansion', lambda: lt.toggle_expansion(doc)),
            ('restore visibility without snapshot', lambda: lt.unisolate(doc)),
            ('restore locks without snapshot', lambda: lt.unisolate_lock(doc)),
        ]:
            dirty();action();check(good(), label + ' repairs an already hidden/locked zero')
        dirty()
        lt.isolate(doc, [tid], False)
        check(good(), 'visibility isolation repairs pre-existing zero settings')
        check(undo() and good(), 'Undo cannot hide or lock zero')
        check(undo(True) and good(), 'Redo keeps zero protected')
        lt.unisolate(doc)
        check(good(), 'visibility restore overrides stale hidden zero in snapshot')
        dirty()
        lt.isolate_lock(doc, [tid], False)
        check(good(), 'lock isolation repairs pre-existing zero settings')
        lt.unisolate_lock(doc)
        check(good(), 'lock restore overrides stale locked zero in snapshot')
        check(undo() and good(), 'lock restore Undo keeps zero protected')
        check(undo(True) and good(), 'lock restore Redo keeps zero protected')
        # Policy also applies when zero is created after the snapshot was saved.
        layer = lt.clone(doc.Layers[z]);layer.Name = 'FormerZero';lt.modify(doc, layer)
        lt.isolate(doc, [tid], False)
        z = add('0');dirty()
        lt.unisolate(doc)
        check(good(), 'zero created after isolation is protected on restore')
        print('PASS: {} zero-layer checks'.format(len(checks)))
        return checks
    finally:
        sc.sticky.pop(lt.key(doc), None)
        sc.sticky.pop(lt.lock_key(doc), None)
        doc.Dispose()


if __name__ == '__main__':
    run()
