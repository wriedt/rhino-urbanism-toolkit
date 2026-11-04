"""Rhino runtime integration tests. Execute via Rhino MCP with __rhino_doc__."""
import importlib
import json
import os
import sys

import Rhino
from System import Guid
from System.Collections.Generic import List
from System.Drawing import Color

ROOT = r'C:\Projects\rhino-urbanism'
OUT = os.path.join(ROOT, 'work', 'block-layer-tests')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT)
import block_layers as bl
import CreateBlockVersion as bv
importlib.reload(bl)
checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def layer(doc, name, parent=None, hidden=False, locked=False):
    value = Rhino.DocObjects.Layer()
    value.Name = name
    if parent is not None:
        value.ParentLayerId = doc.Layers[parent].Id
    value.IsVisible = not hidden
    value.IsLocked = locked
    index = doc.Layers.Add(value)
    assert index >= 0
    return index


def definition(doc, name, nested=None):
    geo = List[Rhino.Geometry.GeometryBase]()
    attrs = List[Rhino.DocObjects.ObjectAttributes]()
    geo.Add(Rhino.Geometry.Circle(Rhino.Geometry.Point3d.Origin, 2).ToNurbsCurve())
    a = Rhino.DocObjects.ObjectAttributes()
    a.SetUserString('part', 'preserve')
    a.LayerIndex = 0
    attrs.Add(a)
    if nested is not None:
        geo.Add(Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[nested].Id,
            Rhino.Geometry.Transform.Translation(5, 0, 0)))
        attrs.Add(a.Duplicate())
    index = doc.InstanceDefinitions.Add(name, 'Keep description',
        Rhino.Geometry.Point3d.Origin, geo, attrs)
    assert index >= 0
    return index


def instance(doc, index, source=0, x=0, hidden=False, locked=False):
    a = Rhino.DocObjects.ObjectAttributes()
    a.LayerIndex = source
    a.Name = 'preserved instance name'
    a.SetUserString('instance', 'preserve')
    a.ObjectColor = Color.Coral
    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    if hidden:
        a.Mode = Rhino.DocObjects.ObjectMode.Hidden
    elif locked:
        a.Mode = Rhino.DocObjects.ObjectMode.Locked
    value = doc.Objects.AddInstanceObject(index, Rhino.Geometry.Transform.Translation(x, 0, 0), a)
    assert value != Guid.Empty
    return value


def run_isolated():
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    reopened = None
    try:
        trees = layer(doc, 'Trees')
        other = layer(doc, 'Other')
        parent_hidden = layer(doc, 'Hidden parent', hidden=True)
        child_hidden = layer(doc, 'Child', parent_hidden)
        parent_locked = layer(doc, 'Locked parent', locked=True)
        child_locked = layer(doc, 'Child', parent_locked)
        i = definition(doc, 'Tree_01')
        moving = instance(doc, i, x=10)
        moving2 = instance(doc, i, x=20)
        check(bl.assign_layer(doc, moving, trees), 'Assignment saved')
        check(not bl.assign_layer(doc, moving, trees), 'Repeated assignment is a no-op')
        check(doc.Objects.FindId(moving).Attributes.LayerIndex == 0, 'Assign does not move instance')
        check(doc.InstanceDefinitions[i].Description == 'Keep description', 'Description preserved')
        check(bl.read_assignment(doc.InstanceDefinitions[i])['layer_path'] == 'Trees', 'Assignment readable')
        hidden = instance(doc, i, hidden=True)
        locked = instance(doc, i, locked=True)
        on_hidden = instance(doc, i, child_hidden)
        on_locked = instance(doc, i, child_locked)
        unassigned_i = definition(doc, 'Unassigned_01')
        unassigned = instance(doc, unassigned_i)
        missing_i = definition(doc, 'Missing_01')
        missing = instance(doc, missing_i)
        missing_layer = layer(doc, 'Missing target')
        bl.assign_layer(doc, missing, missing_layer)
        check(doc.Layers.Delete(missing_layer, True), 'Missing target fixture deleted')
        invalid_i = definition(doc, 'Invalid_01')
        invalid = instance(doc, invalid_i)
        doc.InstanceDefinitions[invalid_i].SetUserString(bl.ASSIGNMENT_KEY, '{bad')
        nested_i = definition(doc, 'Nested_01')
        temp = instance(doc, nested_i)
        bl.assign_layer(doc, temp, trees)
        doc.Objects.Delete(temp, True)
        outer_i = definition(doc, 'Outer_01', nested_i)
        outer = instance(doc, outer_i)
        unused_i = definition(doc, 'Unused_01', nested_i)
        protected_i = definition(doc, 'ProtectedTarget_01')
        protected = instance(doc, protected_i)
        bl.assign_layer(doc, protected, child_locked)
        hidden_target_i = definition(doc, 'HiddenTarget_01')
        hidden_target = instance(doc, hidden_target_i)
        bl.assign_layer(doc, hidden_target, child_hidden)
        # Page-space instances participate without changing layout membership.
        page = doc.Views.AddPageView('Block layer test', 297, 210)
        page_id = instance(doc, i)
        attrs = doc.Objects.FindId(page_id).Attributes.Duplicate()
        attrs.Space = Rhino.DocObjects.ActiveSpace.PageSpace
        attrs.ViewportId = page.MainViewport.Id
        check(doc.Objects.ModifyAttributes(page_id, attrs, True), 'Page-space fixture')
        # IDs survive layer renames, including stale saved full paths.
        renamed = doc.Layers[trees]
        renamed.Name = 'Renamed Trees'
        check(doc.Layers.Modify(renamed, trees, True), 'Target renamed')
        check(bl.find_target(doc, bl.read_assignment(doc.InstanceDefinitions[i])).Index == trees,
              'Target ID survives rename')
        # Full path is exact: same leaf name under another parent is insufficient.
        fallback_i = definition(doc, 'Fallback_01')
        fallback = instance(doc, fallback_i)
        doc.InstanceDefinitions[fallback_i].SetUserString(bl.ASSIGNMENT_KEY,
            json.dumps(dict(version=1, layer_id=str(Guid.NewGuid()), layer_path='Renamed Trees')))
        ambiguous_i = definition(doc, 'DifferentPath_01')
        ambiguous = instance(doc, ambiguous_i)
        doc.InstanceDefinitions[ambiguous_i].SetUserString(bl.ASSIGNMENT_KEY,
            json.dumps(dict(version=1, layer_id=str(Guid.NewGuid()), layer_path='Different::Renamed Trees')))
        # Actual linked definition from a saved external model.
        source_path = os.path.join(OUT, 'linked-source.3dm')
        source = Rhino.FileIO.File3dm()
        source.Objects.AddSphere(Rhino.Geometry.Sphere(Rhino.Geometry.Point3d.Origin, 1))
        check(source.Write(source_path, 8), 'Linked source written')
        source.Dispose()
        linked_i = definition(doc, 'Linked_01')
        check(doc.InstanceDefinitions.ModifySourceArchive(linked_i, source_path,
            Rhino.DocObjects.InstanceDefinitionUpdateType.Linked, True), 'Real linked definition created')
        linked = instance(doc, linked_i)
        check(bl.assign_layer(doc, linked, trees), 'Linked instance definition accepts assignment')
        linked_contents = [(str(o.Id), o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[linked_i].GetObjects()]
        nested_contents = [(str(o.Id), o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[outer_i].GetObjects()]
        before = doc.Objects.FindId(moving)
        transform = str(before.InstanceXform)
        rows = bl.cleanup(doc, include_nested=False)
        status = {str(r['id']): r['status'] for r in rows}
        for object_id in [moving, moving2, fallback, linked, page_id]:
            check(status[str(object_id)] == 'moved', 'Moved ' + str(object_id))
            check(doc.Objects.FindId(object_id).Attributes.LayerIndex == trees, 'Correct destination ' + str(object_id))
        for object_id, expected in [(hidden,'hidden'), (locked,'locked'), (on_hidden,'hidden'),
                (on_locked,'locked'), (unassigned,'unassigned'), (missing,'missing target layer'),
                (invalid,'invalid assignment'), (protected,'target locked'),
                (hidden_target,'target hidden'), (ambiguous,'missing target layer')]:
            check(status[str(object_id)] == expected, 'Skip ' + expected)
        after = doc.Objects.FindId(moving)
        check(str(after.InstanceXform) == transform, 'Transform preserved')
        check(after.Attributes.Name == 'preserved instance name'
              and after.Attributes.GetUserString('instance') == 'preserve'
              and after.Attributes.ObjectColor.ToArgb() == Color.Coral.ToArgb(), 'Instance attributes preserved: ' +
              str((after.Attributes.Name, after.Attributes.GetUserString('instance'), str(after.Attributes.ObjectColor))))
        check([(str(o.Id),o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[outer_i].GetObjects()]
              == nested_contents, 'Nested instance untouched')
        check([(str(o.Id),o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[linked_i].GetObjects()]
              == linked_contents, 'Linked contents untouched')
        check(all(r['block'] != 'Unused_01' for r in rows), 'Unused definition excluded')
        check(doc.Objects.FindId(page_id).Attributes.ViewportId == page.MainViewport.Id,
              'Layout membership preserved')
        check(all(r['status'] != 'move' for r in bl.plan_cleanup(doc, include_nested=False)), 'Top-level cleanup is repeatable')
        # Escape after the first layer change must restore all changed instances.
        for object_id in [moving, moving2]:
            a = doc.Objects.FindId(object_id).Attributes.Duplicate()
            a.LayerIndex = other
            doc.Objects.ModifyAttributes(object_id, a, True)
        original_sc = bl.sc
        class CancelAfterFirstMove:
            calls = 0

            @classmethod
            def escape_test(cls, throw=False, reset=False):
                if reset:
                    cls.calls = 0
                    return False
                cls.calls += 1
                return cls.calls == len(rows) + 2
        try:
            bl.sc = CancelAfterFirstMove
            try:
                bl.cleanup(doc, include_nested=False)
                raise AssertionError('Expected cancellation')
            except RuntimeError as error:
                check('cancelled' in str(error), 'Cancellation reported')
        finally:
            bl.sc = original_sc
        check(all(doc.Objects.FindId(object_id).Attributes.LayerIndex == other
                  for object_id in [moving, moving2]), 'Partial cleanup rolled back')
        bl.cleanup(doc, include_nested=False)
        # Valid JSON with a damaged ID also reports invalid rather than aborting.
        doc.InstanceDefinitions[invalid_i].SetUserString(bl.ASSIGNMENT_KEY,
            json.dumps(dict(version=1, layer_id='not-a-guid', layer_path='Trees')))
        check(next(r for r in bl.plan_cleanup(doc, include_nested=False) if r['id'] == invalid)['status']
              == 'invalid assignment', 'Malformed layer ID reported')
        # Inherit through the actual versioning tool, then clean new version.
        plan = bv.make_plan(doc, [moving])
        bv.apply_plans(doc, [plan])
        version = doc.Objects.FindId(moving).InstanceDefinition
        check(version.Name == 'Tree_02', 'Versioning tool created next version')
        check(version.GetUserString(bl.ASSIGNMENT_KEY) == doc.InstanceDefinitions[i].GetUserString(bl.ASSIGNMENT_KEY),
              'Versioning inherits assignment')
        a = doc.Objects.FindId(moving).Attributes.Duplicate()
        a.LayerIndex = other
        doc.Objects.ModifyAttributes(moving, a, True)
        check(next(r for r in bl.cleanup(doc, include_nested=False) if r['id'] == moving)['status'] == 'moved',
              'New version cleans correctly')
        # Disk write followed by a genuinely reopened Rhino document.
        path = os.path.join(OUT, 'persistence.3dm')
        options = Rhino.FileIO.FileWriteOptions()
        options.SuppressDialogBoxes = True
        check(doc.WriteFile(path, options), 'Document saved')
        reopened = Rhino.RhinoDoc.OpenHeadless(path)
        check(reopened is not None, 'Document reopened')
        v = reopened.InstanceDefinitions.Find('Tree_02')
        check(bl.read_assignment(v)['layer_path'] == 'Trees', 'Saved assignment survives reopen')
        check(bl.find_target(reopened, bl.read_assignment(v)).Name == 'Renamed Trees',
              'Reopened assignment resolves renamed layer')
        check(reopened.Objects.FindId(moving).Attributes.LayerIndex == trees, 'Instance layer survives reopen')
        linked_reopened = reopened.InstanceDefinitions.Find('Linked_01')
        check(bl.read_assignment(linked_reopened) is not None, 'Linked assignment survives reopen')
        check(all(r['status'] != 'move' for r in bl.plan_cleanup(reopened, include_nested=False)), 'Reopened top-level cleanup stable')
        bl.report(rows)
    finally:
        if reopened:
            reopened.Dispose()
        doc.Dispose()
    with open(os.path.join(OUT, 'integration-results.json'), 'w') as stream:
        json.dump(dict(passed=len(checks), checks=checks), stream, indent=2)
    print('BLOCK LAYERS: {0} runtime checks passed'.format(len(checks)))


if __name__ == '__main__':
    run_isolated()
