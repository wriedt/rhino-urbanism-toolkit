"""Run in Rhino MCP with __rhino_doc__; no persistent test geometry."""
import importlib.util
import importlib
import os
import Rhino

spec = importlib.util.spec_from_file_location('pp_split_test',
    os.path.join(os.path.dirname(__file__), 'PushPullCurve.py'))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
importlib.reload(pp.mixed_curves)
doc = __rhino_doc__
tol = doc.ModelAbsoluteTolerance
plane = Rhino.Geometry.Plane.WorldXY
checks = []


def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)


square = [(0., 0.), (10., 0.), (10., 10.), (0., 10.)]
for closed, points in [(True, square), (False, square[:2])]:
    for index in range(len(points) if closed else len(points)-1):
        a, b = points[index], points[(index+1) % len(points)]
        mid = pp.vec2_mul(pp.vec2_add(a, b), .5)
        split = pp.split_segment_points(points, closed, index, mid, tol)
        check(len(split) == len(points)+1, 'one new vertex including closing seam')
        for half in (0, 1):
            for extrude in (False, True):
                result = pp.compute_push_result(split, closed, index+half,
                    Rhino.Geometry.Point3d.Origin, plane, tol, True, -2, extrude=extrude)
                check(result['ok'] and not result['blocked'], 'either half moves in both modes')
                check(result['added_connectors'] >= 1, 'split gets a perpendicular connection')
        check(pp.split_segment_points(points, closed, index, a, tol) is None, 'endpoint rejected')
check(square == [(0.,0.),(10.,0.),(10.,10.),(0.,10.)], 'source list unchanged')

curve = Rhino.Geometry.PolyCurve()
curve.Append(Rhino.Geometry.Line(Rhino.Geometry.Point3d(0,0,0), Rhino.Geometry.Point3d(10,0,0)))
curve.Append(Rhino.Geometry.Arc(Rhino.Geometry.Point3d(10,0,0),
    Rhino.Geometry.Point3d(5,8,0), Rhino.Geometry.Point3d(0,0,0)))
try:
    for half in (0, 1):
        edit = pp.mixed_curves.MixedCurveEdit(curve, plane, tol)
        try:
            check(edit.select_line(Rhino.Geometry.Point3d(3,0,0)), 'mixed line selected')
            original_arc = edit.segments[1].ToNurbsCurve()
            check(not edit.split_selected_line(Rhino.Geometry.Point3d.Origin, half), 'mixed endpoint rejected')
            check(edit.split_selected_line(Rhino.Geometry.Point3d(5,0,0), half), 'mixed split staged')
            check(edit.selected_index == half and len(edit.segments) == 3, 'correct mixed half selected')
            retained_arc = edit.segments[2].ToNurbsCurve()
            try:
                check(Rhino.Geometry.GeometryBase.GeometryEquals(original_arc, retained_arc),
                    'curved neighbour retained exactly')
            finally:
                retained_arc.Dispose()
                original_arc.Dispose()
            for extrude in (False, True):
                result = edit.compute(Rhino.Geometry.Point3d.Origin, -2, extrude)
                try:
                    check(result['ok'] and result['new_curve'].IsClosed, 'mixed half moves and remains connected')
                finally:
                    pp.mixed_curves.dispose_result(result)
        finally:
            edit.dispose()
finally:
    curve.Dispose()

nonplanar = Rhino.Geometry.PolylineCurve([Rhino.Geometry.Point3d(0,0,0),
    Rhino.Geometry.Point3d(10,0,2), Rhino.Geometry.Point3d(10,10,0),
    Rhino.Geometry.Point3d(0,10,0), Rhino.Geometry.Point3d(0,0,0)])
try:
    for target in [plane, Rhino.Geometry.Plane(Rhino.Geometry.Point3d(3,4,5),
            Rhino.Geometry.Vector3d(1,2,3))]:
        projected = pp.project_curve_to_plane(nonplanar, target, tol)
        try:
            check(projected is not None and projected.IsInPlane(target,tol), 'projection uses actual target CPlane')
            check(not nonplanar.IsPlanar(tol), 'source remains non-planar and unchanged')
        finally:
            if projected: projected.Dispose()
finally:
    nonplanar.Dispose()
collapsed = Rhino.Geometry.LineCurve(Rhino.Geometry.Point3d(0,0,0), Rhino.Geometry.Point3d(0,0,10))
try:
    check(pp.project_curve_to_plane(collapsed, plane, tol) is None, 'collapsed projection rejected')
finally:
    collapsed.Dispose()
class Proxy:
    def __init__(self, target, **overrides):
        self.target, self.overrides = target, overrides
    def __getattr__(self, key):
        return self.overrides[key] if key in self.overrides else getattr(self.target, key)


class ObjectPicker:
    def __init__(self, obj):
        self.obj = obj
    def __getattr__(self, key):
        return lambda *args: None
    def Get(self):
        return Rhino.Input.GetResult.Object
    def CommandResult(self):
        return Rhino.Commands.Result.Success
    def ObjectId(self):
        return self.obj.Id
    def Curve(self):
        return self.obj.Geometry
    def SelectionPoint(self):
        return Rhino.Geometry.Point3d(3,0,.6)
    def Object(self, index=None):
        return self if index is not None else self.obj


# Exercise the real command orchestration against a real temporary document
# object. Only user input is scripted; projection/split/commit geometry is real.
import scriptcontext as sc
context = sc.doc
selected = [o.Id for o in doc.Objects.GetSelectedObjects(False,False)]
native_rhino = pp.Rhino
native_confirm = pp.confirm_cplane_projection
native_distance = pp.pick_push_distance
native_split = pp.pick_segment_split
fixture = Rhino.Geometry.PolylineCurve([Rhino.Geometry.Point3d(0,0,0),
    Rhino.Geometry.Point3d(10,0,2), Rhino.Geometry.Point3d(10,10,0),
    Rhino.Geometry.Point3d(0,10,0), Rhino.Geometry.Point3d(0,0,0)])
fixture_id = doc.Objects.AddCurve(fixture)
fixture.Dispose()
try:
    sc.doc = doc
    obj = doc.Objects.FindId(fixture_id)
    before = obj.Geometry.DuplicateCurve()
    pp.Rhino = Proxy(Rhino, Input=Proxy(Rhino.Input,
        Custom=Proxy(Rhino.Input.Custom, GetObject=lambda: ObjectPicker(obj))))
    for stage in ('decline', 'distance', 'split_point', 'half', 'after_split'):
        pp.confirm_cplane_projection = lambda: stage != 'decline'
        calls = []
        def distance(document, points, closed, index, target, *args, **kwargs):
            calls.append(list(points))
            if stage in ('split_point', 'half', 'after_split') and len(calls) == 1:
                return Rhino.Commands.Result.Success, dict(split_requested=True, extrude=True)
            return Rhino.Commands.Result.Cancel, None
        pp.pick_push_distance = distance
        # The split getter has its own finally blocks for either cancel phase;
        # both report None to main and must leave the source untouched.
        pp.pick_segment_split = lambda *args: ((Rhino.Geometry.Point3d(5,0,0),1)
            if stage == 'after_split' else None)
        check(pp.main() == Rhino.Commands.Result.Cancel, 'cancel at '+stage)
        check(Rhino.Geometry.GeometryBase.GeometryEquals(before, doc.Objects.FindId(fixture_id).Geometry),
            'cancellation leaves original geometry intact at '+stage)
        if stage == 'after_split':
            check(len(calls) == 2 and len(calls[1]) == 5, 'staged split returns to distance picker')
    before.Dispose()
finally:
    pp.Rhino = native_rhino
    pp.confirm_cplane_projection = native_confirm
    pp.pick_push_distance = native_distance
    pp.pick_segment_split = native_split
    doc.Objects.Delete(fixture_id,True)
    doc.Objects.UnselectAll()
    for obj_id in selected: doc.Objects.Select(obj_id)
    sc.doc = context
    doc.Views.Redraw()
print('PUSHPULL SPLIT/PROJECT: {} checks passed'.format(len(checks)))
