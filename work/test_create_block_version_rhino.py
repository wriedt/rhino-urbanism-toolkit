"""Integration checks; run inside Rhino 8 through MCP, not ordinary Python."""
import importlib.util
import math
import Rhino
from System import Guid
from System.Collections.Generic import List
from System.Drawing import Color

spec = importlib.util.spec_from_file_location('block_version', r'C:\Projects\rhino-urbanism\CreateBlockVersion.py')
bv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bv)
doc = __rhino_doc__
prefix = 'CBV_TEST_'
definitions, instances = [], []
checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def add_definition(name, size=2, nested=None):
    geo = List[Rhino.Geometry.GeometryBase]()
    attrs = List[Rhino.DocObjects.ObjectAttributes]()
    geo.Add(Rhino.Geometry.Box(Rhino.Geometry.Plane.WorldXY,
        Rhino.Geometry.Interval(0, size), Rhino.Geometry.Interval(0, size),
        Rhino.Geometry.Interval(0, size)).ToBrep())
    a = Rhino.DocObjects.ObjectAttributes()
    a.SetUserString('part', 'preserve me')
    a.ObjectColor = Color.Coral
    a.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    attrs.Add(a)
    if nested is not None:
        geo.Add(Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[nested].Id,
            Rhino.Geometry.Transform.Translation(3, 0, 0)))
        attrs.Add(Rhino.DocObjects.ObjectAttributes())
    index = doc.InstanceDefinitions.Add(prefix + name, 'test description',
        Rhino.Geometry.Point3d.Origin, geo, attrs)
    assert index >= 0
    definitions.append(index)
    return index


def insert(index, transform=None):
    a = Rhino.DocObjects.ObjectAttributes()
    a.Name = 'keep-instance-name'
    a.SetUserString('instance', 'keep')
    obj_id = doc.Objects.AddInstanceObject(index, transform or Rhino.Geometry.Transform.Identity, a)
    assert obj_id != Guid.Empty
    instances.append(obj_id)
    return obj_id


try:
    for old, expected in [('Block_01','Block_02'),('Block_1','Block_2'),
            ('Block_10','Block_11'),('Block_001','Block_002'),
            ('Block_009','Block_010'),('Block_99','Block_100')]:
        check(bv.next_name(old, [old]) == expected, old + ' -> ' + expected)
    check(bv.next_name('Building_2026_Type_03_Left',
        ['Building_2026_Type_08_Left','Building_2025_Type_99_Left']) ==
        'Building_2026_Type_09_Left', 'Flexible placement and exact family')
    check(bv.next_name('Block_03_Floor_02', ['Block_08_Floor_02'], 0) ==
        'Block_09_Floor_02', 'Explicit digit group override')
    check(bv.next_name('Block_01', ['block_12']) == 'Block_13', 'Case insensitive family')
    inner = add_definition('Inner_01', 1)
    old = add_definition('Block_001', 2, inner)
    add_definition('Block_008', 9)
    source = doc.InstanceDefinitions[old]
    source.SetUserString('definition', 'keep')
    transform = (Rhino.Geometry.Transform.Translation(12, 4, 3) *
        Rhino.Geometry.Transform.Rotation(0.7, Rhino.Geometry.Vector3d.ZAxis, Rhino.Geometry.Point3d.Origin) *
        Rhino.Geometry.Transform.Scale(Rhino.Geometry.Plane.WorldXY, -2, 3, 0.5))
    first, second, untouched = insert(old, transform), insert(old), insert(old)
    before = doc.Objects.FindId(first)
    bbox = before.Geometry.GetBoundingBox(True)
    plan = bv.make_plan(doc, [first, second])
    check(plan['new_name'] == prefix + 'Block_009', 'Highest version, preserving padding')
    bv.apply_plans(doc, [plan])
    new_index = doc.Objects.FindId(first).InstanceDefinition.Index
    definitions.append(new_index)
    new = doc.InstanceDefinitions[new_index]
    check(doc.Objects.FindId(second).InstanceDefinition.Id == new.Id, 'Selected instances share new definition')
    check(doc.Objects.FindId(untouched).InstanceDefinition.Index == old, 'Unselected instance stays original')
    after = doc.Objects.FindId(first)
    check(all(abs(after.InstanceXform[i,j] - transform[i,j]) < 1e-12
              for i in range(4) for j in range(4)), 'Translation, rotation, nonuniform scale and mirror preserved')
    check(after.Geometry.GetBoundingBox(True).Min.DistanceTo(bbox.Min) < 1e-9 and
        after.Geometry.GetBoundingBox(True).Max.DistanceTo(bbox.Max) < 1e-9, 'World geometry unchanged')
    check(after.Attributes.Name == 'keep-instance-name' and
        after.Attributes.GetUserString('instance') == 'keep', 'Instance ID and attributes preserved')
    members = list(new.GetObjects())
    check(len(members) == 2 and members[1].Geometry.ParentIdefId == doc.InstanceDefinitions[inner].Id,
        'Nested definition remains shared')
    check(members[0].Attributes.GetUserString('part') == 'preserve me' and
        members[0].Attributes.ObjectColor.ToArgb() == Color.Coral.ToArgb(), 'Definition member attributes preserved')
    check(new.GetUserString('definition') == 'keep' and new.Description == source.Description,
        'Definition description and user strings preserved')
    check(abs(Rhino.Geometry.VolumeMassProperties.Compute(members[0].Geometry).Volume - 8) < 1e-9,
        'Geometry copied from selected old version rather than latest')
    entrance = add_definition('Entrance')
    e1, e2 = insert(entrance), insert(entrance)
    baseline = prefix + 'Entrance_01'
    ep = bv.make_plan(doc, [e1], baseline=baseline)
    bv.apply_plans(doc, [ep])
    definitions.append(doc.Objects.FindId(e1).InstanceDefinition.Index)
    check(doc.InstanceDefinitions[entrance].Name == baseline and
        doc.Objects.FindId(e2).InstanceDefinition.Name == baseline and
        doc.Objects.FindId(e1).InstanceDefinition.Name == prefix + 'Entrance_02',
        'Unnumbered baseline rename and selected-only new version')
    collision = add_definition('Collision')
    c1 = insert(collision)
    try:
        bv.make_plan(doc, [c1], baseline=baseline)
        raise AssertionError('Existing baseline was accepted')
    except ValueError:
        checks.append('Existing baseline rejected before mutation')
    # Force a late failure to exercise restoration of the first successful switch.
    bad = bv.make_plan(doc, [c1], baseline=prefix + 'Collision_01')
    bad['ids'].append(Guid.NewGuid())
    try:
        bv.apply_plans(doc, [bad])
        raise AssertionError('Bad instance was accepted')
    except RuntimeError:
        check(doc.Objects.FindId(c1).InstanceDefinition.Index == collision and
            doc.InstanceDefinitions[collision].Name == prefix + 'Collision' and
            bad['new_name'] not in bv.definition_names(doc), 'Failure rolls back instance, rename and definition')
    print('PASS: {0} Rhino checks'.format(len(checks)))
    for label in checks:
        print('  ' + label)
finally:
    for obj_id in instances:
        doc.Objects.Delete(obj_id, True)
    for index in reversed(definitions):
        doc.InstanceDefinitions.Delete(index, True, True)
    doc.Views.Redraw()

