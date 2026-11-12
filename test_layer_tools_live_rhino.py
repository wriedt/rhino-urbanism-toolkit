# -*- coding: utf-8 -*-
"""Live picker integration check; removes its own point and layer."""
import importlib
import Rhino
import scriptcontext as sc
from System import Guid
import layer_tools as lt
import IsolateLayer
import UnisolateLayer
import IsolateLockLayer
import UnisolateLockLayer


def run(doc):
    for module in (lt, IsolateLayer, UnisolateLayer, IsolateLockLayer, UnisolateLockLayer):
        importlib.reload(module)
    if lt.key(doc) in sc.sticky or lt.lock_key(doc) in sc.sticky:
        raise ValueError('Restore the existing layer isolation before running live tests.')
    before = lt.snapshot(doc)
    previous_selection = [o.Id for o in doc.Objects.GetSelectedObjects(False, False)]
    modified = doc.Modified
    layer_id, object_id = None, None
    try:
        layer = Rhino.DocObjects.Layer()
        layer.Name = 'RUT_LayerPickerTest_' + str(Guid.NewGuid())[:8]
        index = doc.Layers.Add(layer)
        layer_id = doc.Layers[index].Id
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = index
        object_id = doc.Objects.AddPoint(Rhino.Geometry.Point3d.Origin, attr)
        doc.Objects.UnselectAll()
        assert doc.Objects.Select(object_id)
        assert IsolateLayer.main(doc) == 1 + sum(lt.is_zero(l) for l in lt.layers(doc))
        assert all(l.IsVisible == (l.Id == layer_id or lt.is_zero(l)) for l in lt.layers(doc))
        assert UnisolateLayer.main(doc)
        after = lt.snapshot(doc)
        assert after['current'] == before['current']
        assert all(after['visibility'][k] == value for k, value in before['visibility'].items())
        doc.Objects.UnselectAll()
        assert doc.Objects.Select(object_id)
        assert IsolateLockLayer.main(doc) == 1 + sum(lt.is_zero(l) for l in lt.layers(doc))
        assert all(l.IsLocked == (l.Id != layer_id and not lt.is_zero(l)) for l in lt.layers(doc))
        assert lt.snapshot(doc)['visibility'] == after['visibility']
        assert UnisolateLockLayer.main(doc)
        restored = lt.snapshot(doc)
        assert restored['visibility'] == after['visibility']
        assert restored['current'] == before['current']
        assert all(restored['locking'][k] == value for k, value in before['locking'].items())
        print('PASS: live preselection and all four isolation command entry points')
    finally:
        if lt.lock_key(doc) in sc.sticky:
            lt.unisolate_lock(doc)
        if lt.key(doc) in sc.sticky:
            lt.unisolate(doc)
        lt.set_current(doc, before['current'])
        lt.visibility(doc, before['visibility'])
        if object_id:
            doc.Objects.Delete(object_id, True)
        if layer_id:
            layer = doc.Layers.FindId(layer_id)
            if layer is not None:
                doc.Layers.Delete(layer.Index, True)
        doc.Objects.UnselectAll()
        for obj_id in previous_selection:
            doc.Objects.Select(obj_id)
        doc.Modified = modified
        doc.Views.Redraw()
