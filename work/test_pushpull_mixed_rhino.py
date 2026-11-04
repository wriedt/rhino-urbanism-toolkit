"""Run through Rhino MCP: exact mixed-curve geometry and commit regression."""
import importlib.util
import importlib
import math
import Rhino
import scriptcontext as sc
import System

spec=importlib.util.spec_from_file_location('pp_mixed_test',r'C:\Projects\rhino-urbanism\PushPullCurve.py')
pp=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
m=importlib.reload(pp.mixed_curves)
doc=__rhino_doc__
plane=Rhino.Geometry.Plane.WorldXY
checks=[]
owned=[]
fixtures=[]
original_ids={o.Id for o in doc.Objects}
selected_ids=[o.Id for o in doc.Objects.GetSelectedObjects(False,False)]


def check(value,label):
    if not value:raise AssertionError(label)
    checks.append(label)


def point(x,y):return Rhino.Geometry.Point3d(x,y,0)


def rounded(angled=False,open_curve=False):
    curve=Rhino.Geometry.PolyCurve()
    pts=[point(0,0),point(0,10),point(5,12),point(10,0)] if angled else [point(0,0),point(0,10),point(10,10),point(10,0)]
    for a,b in zip(pts,pts[1:]):curve.Append(Rhino.Geometry.Line(a,b))
    if not open_curve:curve.Append(Rhino.Geometry.Arc(point(10,0),point(5,-5),point(0,0)))
    else:
        curve.Append(Rhino.Geometry.Arc(point(10,0),point(5,-5),point(0,0)))
        # Expose open ends while keeping the selected line adjacent to the arc.
        cut=curve.Trim(curve.Domain.T0+0.2,curve.Domain.T1)
        curve.Dispose()
        curve=cut
    owned.append(curve)
    return curve


def u_shape(spline=False):
    curve=Rhino.Geometry.PolyCurve()
    curve.Append(Rhino.Geometry.Line(point(0,10),point(10,10)))
    if spline:
        rest=Rhino.Geometry.NurbsCurve.Create(False,3,[point(10,10),point(12,6),point(10,-5),point(-2,-5),point(0,10)])
        curve.Append(rest)
        rest.Dispose()
    else:curve.Append(Rhino.Geometry.Arc(point(10,10),point(5,-5),point(0,10)))
    owned.append(curve)
    return curve


def calculate(curve,selection,distance,extrude=False,test_plane=plane):
    context=m.MixedCurveEdit(curve,test_plane,doc.ModelAbsoluteTolerance)
    try:
        check(context.select_line(selection),'straight component selectable')
        r=context.compute(Rhino.Geometry.Point3d.Origin,distance,extrude)
        if r['ok']:
            check(r['new_curve'].IsValid and r['new_curve'].IsClosed==curve.IsClosed,'valid connected result')
            events=Rhino.Geometry.Intersect.Intersection.CurveSelf(r['new_curve'],doc.ModelAbsoluteTolerance)
            check(events is None or events.Count==0,'no resulting self intersections')
        return r
    finally:context.dispose()


try:
    curve=rounded()
    context=m.MixedCurveEdit(curve,plane,0.001)
    check(not context.select_line(point(5,-5)),'arc cannot be selected')
    context.dispose()
    for explicit in [False,True]:
        for distance in [-2.,2.]:
            r=calculate(curve,point(0,5),distance,explicit)
            try:
                check(r['ok'],'line next to tangent arc moves')
                arc_pieces=[s for s in r['new_curve'].DuplicateSegments() if s.IsArc(0.001)]
                try:
                    check(len(arc_pieces)==1,'arc retained as an exact arc')
                    ok,arc=arc_pieces[0].TryGetArc()
                    check(ok and abs(arc.Radius-5)<1e-8,'arc radius unchanged')
                    if distance<0 and not explicit:
                        check(abs(r['preview_segment_start'][0]-2)<1e-8 and
                              abs(r['preview_segment_start'][1]+4)<1e-8,'inward tangent join clips at arc intersection')
                        check(arc_pieces[0].GetLength()<math.pi*5,'arc shortened without reshaping')
                        check(r['added_connectors']==0,'intersection uses no connector')
                    else:
                        check(abs(arc_pieces[0].GetLength()-math.pi*5)<1e-8,'untrimmed arc preserved')
                        check(r['added_connectors']==1,'no intersection or Extrude adds connector')
                finally:
                    for segment in arc_pieces:segment.Dispose()
            finally:m.dispose_result(r)
    curve=rounded(True)
    r=calculate(curve,point(0,5),2,True)
    check(r['ok'] and r['added_connectors']==2,'Extrude adds both connectors at angled/curved neighbours')
    m.dispose_result(r)
    for spline in [False,True]:
        curve=u_shape(spline)
        for distance in [-1.,-3.,2.]:
            r=calculate(curve,point(5,10),distance)
            try:
                check(r['ok'],'two cuts in one curved component supported')
                if distance<0:
                    check(r['added_connectors']==0 and len(r['trimmed_curves'])==2,'both ends trimmed on same component')
                    check(abs(r['preview_segment_start'][1]-(10+distance))<1e-8,'cut remains on moved line')
                    components=r['new_curve'].DuplicateSegments()
                    source=curve.SegmentCurve(1)
                    try:
                        curved=[c for c in components if not c.IsLinear(0.001)]
                        check(len(curved)==1,'one original curved component retained')
                        for fraction in [0.,0.25,0.5,0.75,1.]:
                            p=curved[0].PointAtNormalizedLength(fraction)
                            ok,t=source.ClosestPoint(p)
                            check(ok and source.PointAt(t).DistanceTo(p)<1e-7,'trimmed curve stays on exact source shape')
                    finally:
                        for component in components:component.Dispose()
                else:check(r['added_connectors']==2,'outward curved corners use two connectors')
            finally:m.dispose_result(r)
        reverse=curve.DuplicateCurve()
        owned.append(reverse)
        reverse.Reverse()
        r=calculate(reverse,point(5,10),3)
        check(r['ok'],'reversed contour clips correctly')
        m.dispose_result(r)
    tilted=Rhino.Geometry.Plane(Rhino.Geometry.Point3d(100,200,300),Rhino.Geometry.Vector3d(1,2,3))
    transform=Rhino.Geometry.Transform.PlaneToPlane(plane,tilted)
    curve=rounded()
    curve.Transform(transform)
    pick=point(0,5)
    pick.Transform(transform)
    r=calculate(curve,pick,-2,test_plane=tilted)
    check(r['ok'],'tilted plane supports exact trimming')
    m.dispose_result(r)
    open_mixed=Rhino.Geometry.PolyCurve()
    owned.append(open_mixed)
    open_mixed.Append(Rhino.Geometry.Arc(point(10,0),point(5,-5),point(0,0)))
    open_mixed.Append(Rhino.Geometry.Line(point(0,0),point(0,10)))
    open_mixed.Append(Rhino.Geometry.Line(point(0,10),point(5,12)))
    for explicit in [False,True]:
        for distance in [-2.,2.]:
            r=calculate(open_mixed,point(0,5),distance,explicit)
            check(r['ok'] and not r['new_curve'].IsClosed,'open mixed curve remains open')
            m.dispose_result(r)
    # A closed curve may place its seam inside the curved component.
    curve=u_shape(True)
    seam=curve.Domain.ParameterAt(0.7)
    check(curve.ChangeClosedCurveSeam(seam),'mixed closure seam changed')
    r=calculate(curve,point(5,10),-2)
    check(r['ok'],'trimming is independent of curved closure seam')
    m.dispose_result(r)
    # Explicit extrusion still rejects collisions with an unrelated boundary.
    # Moving the top chord through the full U would lose its original region.
    r=calculate(u_shape(),point(5,10),-30)
    check(r['blocked'],'mixed curve cannot jump past a collapse')
    m.dispose_result(r)
    # Exercise copy and replacement in the intended document with owned fixtures.
    curve=u_shape(True)
    attrs=Rhino.DocObjects.ObjectAttributes()
    attrs.Name='PUSHPULL_MIXED_TEST'
    attrs.SetUserString('preserve','mixed metadata')
    obj_id=doc.Objects.AddCurve(curve,attrs)
    fixtures.append(obj_id)
    attrs.Dispose()
    r=calculate(curve,point(5,10),-3)
    try:
        before={o.Id for o in doc.Objects}
        check(pp.apply_push_result(doc,doc.Objects.FindId(obj_id),r,plane,True,False)==Rhino.Commands.Result.Success,'mixed copy commits')
        copies={o.Id for o in doc.Objects}-before
        fixtures.extend(copies)
        check(len(copies)==1,'mixed copy creates one curve')
        check(pp.apply_push_result(doc,doc.Objects.FindId(obj_id),r,plane,True,True)==Rhino.Commands.Result.Success,'mixed replacement commits')
        obj=doc.Objects.FindId(obj_id)
        check(obj.Attributes.GetUserString('preserve')=='mixed metadata','mixed metadata preserved')
        check(obj.Geometry.IsClosed and not obj.Geometry.TryGetPolyline()[0],'committed curve retains curved geometry')
    finally:m.dispose_result(r)
finally:
    for obj_id in fixtures:
        if doc.Objects.FindId(obj_id):doc.Objects.Delete(obj_id,True)
    for geometry in owned:geometry.Dispose()
    doc.Objects.UnselectAll()
    for obj_id in selected_ids:doc.Objects.Select(obj_id)
    doc.Views.Redraw()
check({o.Id for o in doc.Objects}==original_ids,'original document geometry preserved')
print('PUSHPULL MIXED: {} checks passed; fixtures removed'.format(len(checks)))
