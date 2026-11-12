#! python 3
"""Create a guarded, disposable hands-on drawing without changing the live model."""
import json
from pathlib import Path
import sys
import traceback
import Rhino
from System import Guid
from System.Drawing import Color
from System.Collections.Generic import List

G = Rhino.Geometry
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/phase5-validation'
OUT.mkdir(parents=True, exist_ok=True)
PATH = OUT / 'RUT-beta-hands-on.3dm'
REPORT = OUT / 'scene.json'
report = {'path': str(PATH), 'user_checks': 'Pending; no manual checks marked passed'}
doc = None
try:
    assert not PATH.exists(), 'Existing hands-on drawing preserved; choose a new output filename.'
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelUnitSystem = Rhino.UnitSystem.Meters
    doc.ModelAbsoluteTolerance = .001
    ids = {}
    layers = {}

    def layer(name, color, parent=None):
        item = Rhino.DocObjects.Layer()
        item.Name = name
        item.Color = Color.FromArgb(*color)
        if parent is not None:
            item.ParentLayerId = doc.Layers[parent].Id
        index = doc.Layers.Add(item)
        assert index >= 0
        layers[name] = index
        return index

    zero = layer('0', (55, 70, 80))
    doc.Layers.SetCurrentLayerIndex(zero, True)
    notes = layer('Read me - labels', (60, 75, 85))

    def attributes(name, index):
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex, a.Name = index, name
        a.SetUserString('RUT.BetaTest', name)
        return a

    def add(geometry, name, index):
        oid = doc.Objects.Add(geometry, attributes(name, index))
        assert oid != Guid.Empty
        ids[name] = oid
        return oid

    def rect(x, y, w, h):
        return G.Rectangle3d(G.Plane(G.Point3d(x, y, 0), G.Vector3d.ZAxis), w, h).ToNurbsCurve()

    def box(x, y, w, h, z):
        return G.BoundingBox(G.Point3d(x, y, 0), G.Point3d(x+w, y+h, z)).ToBrep()

    def label(text, x, y):
        text_geometry = G.TextEntity()
        text_geometry.Plane = G.Plane(G.Point3d(x, y, 0), G.Vector3d.ZAxis)
        text_geometry.PlainText = text
        text_geometry.TextHeight = .9
        add(text_geometry, text.split('\n')[0], notes)

    parent = layer('01 Layers', (45, 135, 160))
    child = layer('Child', (40, 170, 155), parent)
    hidden = layer('Initially hidden', (160, 140, 90), parent)
    locked = layer('Initially locked', (160, 100, 90), parent)
    add(rect(0, 45, 8, 6), 'Layer parent', parent)
    add(rect(10, 45, 8, 6), 'Layer child', child)
    add(rect(20, 45, 8, 6), 'Hidden square', hidden)
    add(rect(30, 45, 8, 6), 'Locked square', locked)
    doc.Layers[hidden].IsVisible = False
    doc.Layers[locked].IsLocked = True
    add(rect(-3, 45, 1, 6), 'Root zero stays available', zero)
    label('1  LAYERS\nParent + child; one hidden, one locked. Root 0 stays available.', 0, 56)

    blocks = layer('02 Blocks', (75, 125, 175))
    home = layer('Block home destination', (40, 150, 140), blocks)
    geo = box(0, 0, 4, 4, 3)
    indices = {}
    for name in ('BetaHouse_v02', 'BetaHouse_v04', 'BetaHouse_v06'):
        indices[name] = doc.InstanceDefinitions.Add(name, 'RUT disposable beta example',
            G.Point3d.Origin, [geo], [attributes('Member ' + name, blocks)])
        assert indices[name] >= 0
    for name, x in [('BetaHouse_v02', 45), ('BetaHouse_v02', 51), ('BetaHouse_v04', 57)]:
        oid = doc.Objects.AddInstanceObject(indices[name], G.Transform.Translation(x, 45, 0),
            attributes(name + ' copy at ' + str(x), blocks))
        assert oid != Guid.Empty
        ids[name + ' copy at ' + str(x)] = oid
    label('2  BLOCKS\nv02 x2, v04 x1; unused v06. Next version should be v07.', 45, 56)

    floor = layer('03 Floor Area', (45, 145, 165))
    good = add(box(0, 10, 10, 8, 3), 'Tall 80 m2', floor)
    short = add(box(13, 10, 4, 8, .5), 'Short 32 m2 - height 0.5 m', floor)
    opened = add(G.PlaneSurface(G.Plane(G.Point3d(20, 10, 0), G.Vector3d.ZAxis),
        G.Interval(0, 10), G.Interval(0, 8)).ToBrep(), 'Open surface - must warn', floor)
    inner = doc.InstanceDefinitions.Add('BetaArea_inner', '', G.Point3d.Origin,
        [box(0, 0, 6, 5, 3)], [attributes('Area inner 30 m2', floor)])
    nested = G.InstanceReferenceGeometry(doc.InstanceDefinitions[inner].Id,
        G.Transform.Scale(G.Plane.WorldXY, 2, .5, 1))
    outer = doc.InstanceDefinitions.Add('BetaArea_nested', '', G.Point3d.Origin,
        [nested], [attributes('Area transformed child', floor)])
    nested_id = doc.Objects.AddInstanceObject(outer, G.Transform.Translation(0, -1, 0),
        attributes('Nested block 30 m2', floor))
    ids['Nested block 30 m2'] = nested_id
    label('3  FLOOR AREA\nTall 80 m2 | Short 32 m2 | Open surface = warning\nNested block below: 30 m2', 0, 23)

    curves = layer('04 PushPullCurve', (50, 125, 170))
    add(rect(45, 10, 10, 8), 'Push-pull rectangle', curves)
    mixed = G.PolyCurve()
    mixed.Append(G.LineCurve(G.Point3d(60, 10, 0), G.Point3d(70, 10, 0)))
    mixed.Append(G.ArcCurve(G.Arc(G.Point3d(70, 10, 0), G.Point3d(74, 14, 0), G.Point3d(70, 18, 0))))
    mixed.Append(G.LineCurve(G.Point3d(70, 18, 0), G.Point3d(60, 18, 0)))
    mixed.Append(G.LineCurve(G.Point3d(60, 18, 0), G.Point3d(60, 10, 0)))
    assert mixed.IsClosed and mixed.IsValid
    add(mixed, 'Mixed straight + semicircle', curves)
    nonplanar = G.PolylineCurve([G.Point3d(45, -1, 0), G.Point3d(55, -1, 0),
        G.Point3d(55, 5, 1), G.Point3d(45, 5, 0), G.Point3d(45, -1, 0)])
    add(nonplanar, 'Nonplanar projection example', curves)
    label('4  PUSH / PULL\nRectangle | Mixed arc | Nonplanar projection below', 45, 23)

    shapes = layer('05 ShapeBuilder - curves', (35, 145, 165))
    hatch_layer = layer('05 ShapeBuilder - hatch', (200, 125, 90))
    add(rect(0, -28, 12, 10), 'ShapeBuilder curve', shapes)
    pattern = doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Hatch1)
    hatch = G.Hatch.Create(G.Plane.WorldXY, rect(7, -24, 12, 10), List[G.Curve](), pattern, .25, 1)
    add(hatch, 'ShapeBuilder hatch master', hatch_layer)
    add(G.LineCurve(G.Point3d(-3, -23, 0), G.Point3d(22, -23, 0)), 'Open divider with outside tails', shapes)
    label('5  SHAPE BUILDER\nOverlapping curve + hatch + open divider\nMerge, Alt-erase, Undo, Cancel; reverse drag for master style.', 0, -9)
    grid = layer('06 ShapeBuilder - 100 regions', (75, 145, 155))
    for i in range(11):
        add(G.LineCurve(G.Point3d(45+2*i, -30, 0), G.Point3d(45+2*i, -10, 0)), 'Grid vertical '+str(i), grid)
        add(G.LineCurve(G.Point3d(45, -30+2*i, 0), G.Point3d(65, -30+2*i, 0)), 'Grid horizontal '+str(i), grid)
    label('6  SHAPE BUILDER - 100 REGIONS\nSelect this layer only. Try a long stroke and erase.', 45, -7)

    installation = json.loads((ROOT/'work/phase4-validation/installation.json').read_text())
    runtime = next(Path(installation['plugin_files'][0]).parent.glob('libs/*/rut_runtime'))
    sys.path.insert(0, str(runtime))
    import floor_area
    checks = []
    for name, oid, sections, expected_valid, expected_base in [
        ('Tall base', good, False, True, 80), ('Tall section', good, True, True, 80),
        ('Short base', short, False, True, 32), ('Short section warns', short, True, False, None),
        ('Open surface warns', opened, False, False, None),
        ('Nested block', nested_id, True, True, 30)]:
        result = floor_area.measure(doc, [oid], sections=sections)
        try:
            assert result.valid == expected_valid, name
            if expected_base is not None:
                assert abs(result.base-expected_base) < 1e-6, name
                if sections:
                    assert abs(result.section-expected_base) < 1e-6, name
            checks.append({'name': name, 'passed': True, 'base': result.base,
                'section': result.section, 'issues': len(result.issues)})
        finally:
            result.dispose()
    options = Rhino.FileIO.FileWriteOptions()
    options.SuppressDialogBoxes = True
    assert doc.WriteFile(str(PATH), options)
    saved = Rhino.FileIO.File3dm.Read(str(PATH))
    assert saved and saved.Settings.ModelUnitSystem == Rhino.UnitSystem.Meters
    # File3dm also contains definition members; the live table's default iterator
    # excludes some object states. Verify every authored top-level ID instead.
    saved_ids = {obj.Attributes.ObjectId for obj in saved.Objects}
    assert set(ids.values()).issubset(saved_ids), 'All test objects survive saving.'
    saved.Dispose()
    report.update({'created': True, 'units': 'metres', 'objects': len(list(doc.Objects)),
        'definitions': len(list(doc.InstanceDefinitions)), 'checks': checks,
        'candidate': installation['active_version'],
        'objects_by_name': {name: str(oid) for name, oid in ids.items()}})
except Exception:
    report['error'] = traceback.format_exc()
finally:
    if doc:
        doc.Dispose()
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
