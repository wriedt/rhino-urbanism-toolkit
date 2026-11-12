# -*- coding: utf-8 -*-
"""Erase remaining open-curve edges, bounded by selected-geometry intersections."""
import os
import json
import math
import Rhino
from System.Collections.Generic import List
G=Rhino.Geometry
PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'edge_erase_tests','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
checks=[];failures=[]


def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)


def rect():return G.Rectangle3d(G.Plane.WorldXY,10,10).ToNurbsCurve()
def line(a=(-5,5,0),b=(15,5,0)):return G.LineCurve(G.Point3d(*a),G.Point3d(*b))
def setup(doc,extra=()):
    r=rect();h=G.Hatch.Create(G.Plane.WorldXY,r,List[G.Curve](),0,0,1);r.Dispose()
    return [h,line()]+list(extra)
def builder(doc,cs):
    b=ns['Builder'](doc,cs)
    for c in cs:c.Dispose()
    return b
def parts(b):return [p for r in b.leftovers for p in r['pieces']]
def length(b):return sum(p.GetLength() for p in parts(b))
def merge(b):
    b.begin_stroke()
    for i in range(len(b.cells)):b.touch(i)
    b.apply_stroke()
def cross(b,a=(12,4,0),z=(12,6,0),erase=True):
    b.begin_stroke(erase);b.stroke_segment(G.Point3d(*a),G.Point3d(*z));b.update_pending()


def run(name,test):
    doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
    try:test(doc)
    except Exception as error:failures.append(name+': '+repr(error))
    finally:doc.Dispose()


def basic(doc):
    b=builder(doc,setup(doc))
    try:
        check('initial divider split at two hatch intersections',len(b.edge_atoms)==3)
        merge(b);check('only the two outside tails are edge targets',len(list(b.visible_edges()))==2)
        cross(b)
        check('fast crossing finds the outside tail with endpoints away from it',len(b.stroke_edges)==1)
        check('edge-only drag does not select a region',not b.stroke)
        check('edge pending preview removes targeted tail',len(b.pending_leftovers[0]['pieces'])==1)
        check('pending edge drag has not changed applied leftovers',len(parts(b))==2)
        b.apply_stroke()
        check('edge-only erase preserves merged region',len(b.groups)==1)
        check('only the opposite five-unit tail remains',len(parts(b))==1 and abs(length(b)-5)<1e-8 and parts(b)[0].PointAtStart.X<0)
        check('erased edge no longer pickable',b.hit_edge(G.Point3d(12,5,0)) is None)
        check('opposite tail remains pickable',b.hit_edge(G.Point3d(-2,5,0)) is not None)
        b.undo();check('Undo restores both outside tails',len(parts(b))==2 and not b.erased_edges)
        b.undo();check('Undo merge restores whole original curve',len(parts(b))==1 and abs(length(b)-20)<1e-8)
    finally:b.dispose_geometry()


def click(doc):
    b=builder(doc,setup(doc))
    try:
        b.begin_stroke(True);key=b.hit_edge(G.Point3d(12,5,0));b.stroke_edges.add(key);b.apply_stroke()
        check('Alt-click erases only tail before region merge',abs(length(b)-15)<1e-8 and len(b.groups)==2 and not b.affected)
        check('Alt-click preserves internal source portion',b.hit_edge(G.Point3d(5,5,0)) is not None)
    finally:b.dispose_geometry()


def no_alt(doc):
    b=builder(doc,setup(doc))
    try:
        cross(b,erase=False);b.apply_stroke()
        check('ordinary outside drag does not erase edges',not b.erased_edges and not b.history and abs(length(b)-20)<1e-8)
        cross(b,a=(12,7,0),z=(14,7,0));b.apply_stroke()
        check('Alt-drag that misses all geometry changes nothing',not b.erased_edges and not b.history)
    finally:b.dispose_geometry()


def bent(doc):
    r=rect();h=G.Hatch.Create(G.Plane.WorldXY,r,List[G.Curve](),0,0,1);r.Dispose()
    poly=G.PolylineCurve(List[G.Point3d]([G.Point3d(-5,5,0),G.Point3d(12,5,0),G.Point3d(15,2,0)]))
    b=builder(doc,[h,poly])
    try:
        check('polyline corner does not split topological edge',len(b.edge_atoms)==3)
        merge(b);cross(b,a=(14,1,0),z=(14,4,0));b.apply_stroke()
        check('erasing bent outside tail removes through its corner to boundary',len(parts(b))==1 and abs(length(b)-5)<1e-8)
    finally:b.dispose_geometry()


def crossing_edges(doc):
    b=builder(doc,setup(doc,[line((12,0,0),(12,10,0))]))
    try:
        merge(b);cross(b,a=(14,4,0),z=(14,6,0));b.apply_stroke()
        first=b.leftovers[0]['pieces']
        check('other selected curve limits erased edge at crossing',abs(sum(c.GetLength() for c in first)-7)<1e-8)
        check('outside stub up to other curve survives',b.hit_edge(G.Point3d(11,5,0)) is not None)
        check('crossed unrelated source stays whole',not b.leftovers[1]['consumed'] and abs(b.leftovers[1]['pieces'][0].GetLength()-10)<1e-8)
    finally:b.dispose_geometry()


def arcs(doc):
    r=G.Rectangle3d(G.Plane.WorldXY,G.Interval(-5,5),G.Interval(-2,12)).ToNurbsCurve()
    h=G.Hatch.Create(G.Plane.WorldXY,r,List[G.Curve](),0,0,1);r.Dispose()
    c=G.ArcCurve(G.Arc(G.Point3d(-10,0,0),G.Point3d(0,10,0),G.Point3d(10,0,0)))
    b=builder(doc,[h,c])
    try:
        merge(b);cross(b,a=(-11,4,0),z=(-7,4,0));b.apply_stroke()
        check('curved tail erase keeps opposite tail as exact arc',len(parts(b))==1 and isinstance(parts(b)[0],G.ArcCurve))
        check('curved tail stops at hatch intersection',abs(length(b)-10*math.pi/3)<0.002)
    finally:b.dispose_geometry()


def later_edits(doc):
    b=builder(doc,setup(doc))
    try:
        merge(b);cross(b);b.apply_stroke()
        b.begin_stroke(True);b.touch(next(iter(b.groups[0])));b.apply_stroke()
        check('region erase does not resurrect previously erased tail',not b.groups and len(parts(b))==1 and abs(length(b)-5)<1e-8)
        b.undo();check('Undo region erase retains edge erasure',len(b.groups)==1 and len(b.erased_edges)==1)
        b.undo();check('Undo edge erase restores both tails',not b.erased_edges and len(parts(b))==2)
    finally:b.dispose_geometry()


def duplicates(doc):
    b=builder(doc,setup(doc,[line()]))
    try:
        merge(b);cross(b)
        check('drag detects both coincident source edges',len(b.stroke_edges)==2)
        b.apply_stroke()
        check('no coincident erased edge remains',b.hit_edge(G.Point3d(12,5,0)) is None and abs(length(b)-10)<1e-8)
    finally:b.dispose_geometry()


def screen_pick(doc):
    b=builder(doc,setup(doc))
    class Viewport:
        def __init__(self,scale):self.scale=scale
        def WorldToClient(self,p):return G.Point2d(p.X*self.scale,p.Y*self.scale)
    try:
        merge(b)
        check('edge hover uses a seven-pixel threshold',b.hit_edge(G.Point3d(12,5.05,0),Viewport(100)) is not None)
        check('edge hover rejects ten-pixel miss',b.hit_edge(G.Point3d(12,5.1,0),Viewport(100)) is None)
        check('edge hover follows zoom scale',b.hit_edge(G.Point3d(12,5.1,0),Viewport(10)) is not None)
    finally:b.dispose_geometry()


def output(doc):
    cs=setup(doc);ids=[]
    for g in cs:
        ident=doc.Objects.AddHatch(g) if isinstance(g,G.Hatch) else doc.Objects.AddCurve(g)
        ids.append(ident);g.Dispose()
    b=ns['Builder'](doc,[doc.Objects.FindId(i) for i in ids])
    try:
        merge(b);cross(b);b.apply_stroke();out=b.commit_output()
        check('Finish writes hatch and only surviving open tail',len(out)==2 and sum(isinstance(doc.Objects.FindId(i).Geometry,G.Curve) for i in out)==1)
        check('Finish replaces erased original path',all(doc.Objects.FindId(i) is None or doc.Objects.FindId(i).IsDeleted for i in ids))
    finally:b.dispose_geometry()


for name,test in [('basic',basic),('click',click),('no Alt',no_alt),('bent tail',bent),('crossing curves',crossing_edges),('arcs',arcs),('later edits',later_edits),('duplicates',duplicates),('screen pick',screen_pick),('output',output)]:run(name,test)
report={'passed':len(checks),'checks':checks,'failures':failures}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-edge-erase-tests.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps({k:report[k] for k in ['passed','failures']}))
if failures:raise AssertionError(str(failures))
