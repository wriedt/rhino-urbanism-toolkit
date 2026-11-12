# -*- coding: utf-8 -*-
"""Run with Rhino MCP. Uses a disposable headless document, no user geometry."""
import os
import json
import time
import Rhino
from System.Collections.Generic import List

PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'ShapeBuilder.py'))
ns = {'__name__': 'shape_builder_tests', '__file__': PATH}
exec(compile(open(PATH, encoding='utf-8').read(), PATH, 'exec'), ns)
G = Rhino.Geometry
checks = []
failures = []
doc = Rhino.RhinoDoc.CreateHeadless(None)
doc.ModelAbsoluteTolerance = 0.001


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def rect(x0=0, x1=10, y0=0, y1=10):
    return G.Rectangle3d(G.Plane.WorldXY, G.Interval(x0, x1), G.Interval(y0, y1)).ToNurbsCurve()


def area(builder):
    total = 0.0
    for loops in builder.outlines:
        breps = G.Brep.CreatePlanarBreps(ns['net_curves'](loops), builder.tol)
        for brep in breps:
            props = G.AreaMassProperties.Compute(brep)
            total += props.Area
            props.Dispose()
            brep.Dispose()
    return total



def stroke(b, indices, erase=False):
    b.dragging = True
    b.stroke = set(indices)
    b.erase = erase
    b.apply_stroke()


def fixture(name, curves, test):
    b = None
    try:
        b = ns['Builder'](doc, curves)
        check(name + ': valid closed loops', all(c.IsValid and c.IsClosed for cell in b.cells for c in cell.loops))
        check(name + ': safe seeds', all(c.contains(c.seed) for c in b.cells))
        test(b)
    except Exception as error:
        failures.append(name + ': ' + repr(error))
    finally:
        if b:
            b.dispose_geometry()
        for c in curves:
            c.Dispose()


def overlap(b):
    check('overlap: three cells', len(b.cells) == 3)
    check('overlap: combined area 150', abs(area(b)-150) < 1e-6)
    ids = [b.hit(G.Point3d(x,5,0)) for x in (2,7,12)]
    check('overlap: distinct hit tests', len(set(ids)) == 3 and None not in ids)
    check('outside: not selectable', b.hit(G.Point3d(-10,5,0)) is None)
    check('edge: not ambiguous selectable', b.hit(G.Point3d(5,5,0)) is None)
    stroke(b, [ids[0]])
    check('single-cell click: no undo noise', len(b.history) == 0)
    b.stroke_segment(G.Point3d(-1,5,0),G.Point3d(16,5,0))
    check('fast stroke: no skipped cells', len(b.stroke) == 3)
    stroke(b, b.stroke)
    check('merge: one outline', len(b.outlines) == 1 and len(b.outlines[0]) == 1)
    check('merge: area unchanged', abs(area(b)-150) < 1e-6)
    b.hover = ids[0]
    check('merge: hover covers whole group', b.active_members() == set(ids))
    check('merge: highlight uses one boundary', len(b.group_outlines[0][1][0]) == 1)
    stroke(b, [ids[0]], True)
    check('erase merged: removes whole shape', len(b.outlines) == 0)
    b.undo()
    check('undo erase: restores merged shape', len(b.outlines) == 1)
    b.undo()
    check('undo merge: restores three cells', len(b.groups) == 3)
    stroke(b, [ids[1]], True)
    check('erase overlap: area 100', abs(area(b)-100) < 1e-6)
    check('erased cell: unpickable', b.hit(G.Point3d(7,5,0)) is None)
    b.undo()
    check('undo erase: area 150', abs(area(b)-150) < 1e-6)


def nested(b):
    check('nested: two cells', len(b.cells) == 2)
    outer=b.hit(G.Point3d(2,2,0));inner=b.hit(G.Point3d(10,10,0))
    check('nested: hole separate from ring', outer != inner)
    check('nested: ring has inner boundary', len(b.cells[outer].loops) == 2)
    stroke(b,[inner],True)
    check('nested: erase preserves courtyard',len(b.outlines)==1 and len(b.outlines[0])==2 and abs(area(b)-300)<1e-6)
    b.undo()
    stroke(b,[outer,inner])
    check('nested: fill removes courtyard',len(b.outlines)==1 and len(b.outlines[0])==1 and abs(area(b)-400)<1e-6)


def merge_all(b, expected, label):
    stroke(b,range(len(b.cells)))
    # A positional model tolerance implies an area tolerance proportional to perimeter.
    area_tolerance = max(1e-6, sum(c.GetLength() for c in b.curves) * b.tol * 2)
    check(label + ': area within model tolerance', abs(area(b)-expected) < area_tolerance)
    distances = []
    for loops in b.outlines:
        for curve in loops:
            for i in range(65):
                p = curve.PointAt(curve.Domain.ParameterAt(i/64.0))
                distance = min(p.DistanceTo(source.PointAt(source.ClosestPoint(p)[1])) for source in b.curves)
                distances.append(distance)
    check(label + ': sampled boundaries within tolerance', max(distances) <= b.tol * 1.01)


started=time.time()
try:
    fixture('overlap', [rect(),rect(5,15)], overlap)
    fixture('nested', [rect(0,20,0,20),rect(5,15,5,15)], nested)
    lines=[G.LineCurve(G.Point3d(*a),G.Point3d(*z)) for a,z in [
        ((0,0,0),(10,0,0)),((10,0,0),(10,10,0)),((10,10,0),(0,10,0)),((0,10,0),(0,0,0)),
        ((5,-2,0),(5,12,0)),((-2,5,0),(12,5,0))]]
    def grid(b):
        check('open line grid: four cells',len(b.cells)==4)
        merge_all(b,100,'open line grid merge')
        check('open line grid: one outline',len(b.outlines)==1)
    fixture('open line grid',lines,grid)
    fixture('duplicate boundaries',[rect(),rect()],lambda b: merge_all(b,100,'duplicates'))
    def circles(b):
        import math
        overlap_area=2*25*math.acos(0.5)-0.5*5*math.sqrt(75)
        check('overlapping circles: three cells',len(b.cells)==3)
        merge_all(b,50*math.pi-overlap_area,'overlapping circles')
    fixture('overlapping circles',[G.Circle(G.Point3d(0,0,0),5).ToNurbsCurve(),G.Circle(G.Point3d(5,0,0),5).ToNurbsCurve()],circles)
    def tangents(b):
        merge_all(b,50*3.141592653589793,'tangent circles')
        check('tangent circles: remain independently selectable',len(b.groups)==2)
    fixture('tangent circles',[G.Circle(G.Point3d(0,0,0),5).ToNurbsCurve(),G.Circle(G.Point3d(10,0,0),5).ToNurbsCurve()],tangents)
    fixture('shared full edge',[rect(),rect(10,20)],lambda b: merge_all(b,200,'shared edge'))
    def disconnected(b):
        merge_all(b,200,'disconnected')
        check('disconnected: remain independently selectable',len(b.groups)==2)
    fixture('disconnected',[rect(),rect(20,30)],disconnected)
    fixture('narrow region',[rect(),rect(9.98,20)],lambda b: merge_all(b,200,'narrow region'))
    concave=G.PolylineCurve(List[G.Point3d]([G.Point3d(x,y,0) for x,y in [(0,0),(10,0),(10,2),(2,2),(2,10),(0,10),(0,0)]]))
    fixture('concave',[concave],lambda b: check('concave: correct area',abs(area(b)-36)<1e-6))
    bowtie=G.PolylineCurve(List[G.Point3d]([G.Point3d(x,y,0) for x,y in [(0,0),(10,10),(0,10),(10,0),(0,0)]]))
    fixture('self intersection',[bowtie],lambda b: merge_all(b,50,'self intersection'))
    tilted=[rect(),rect(5,15)]
    transform=G.Transform.PlaneToPlane(G.Plane.WorldXY,G.Plane(G.Point3d(100,200,30),G.Vector3d(1,2,3)))
    for c in tilted:c.Transform(transform)
    fixture('tilted plane',tilted,lambda b: merge_all(b,150,'tilted plane'))
    for name, curves in [('noncoplanar',[rect(),rect(5,15)]),('unclosed',[G.LineCurve(G.Point3d(0,0,0),G.Point3d(10,0,0))]),('empty',[])]:
        if name=='noncoplanar':curves[1].Translate(0,0,1)
        try:
            b=ns['Builder'](doc,curves)
            b.dispose_geometry()
            failures.append(name+': accepted invalid input')
        except ValueError:
            checks.append(name+': rejected safely')
        finally:
            for c in curves:c.Dispose()
finally:
    doc.Dispose()
report={'passed':len(checks),'checks':checks,'failures':failures,'seconds':round(time.time()-started,2)}
with open(os.path.join(os.path.dirname(PATH), 'work', 'shape-builder-tests.json'), 'w') as output:
    json.dump(report,output,indent=2)
print(json.dumps({key:report[key] for key in ('passed','failures','seconds')}))
if failures:
    raise AssertionError('Shape Builder test failures: '+str(failures))
