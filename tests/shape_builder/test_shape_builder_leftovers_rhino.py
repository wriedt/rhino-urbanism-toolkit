# -*- coding: utf-8 -*-
"""Gesture-aware preservation, source identity, exact curves, and failure recovery."""
import os
import json
import math
import Rhino
import System.Drawing as sd
from System.Collections.Generic import List
G=Rhino.Geometry
PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'leftover_tests','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
checks=[]
failures=[]


def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)


def rect(x0=0,x1=10,y0=0,y1=10):
    return G.Rectangle3d(G.Plane.WorldXY,G.Interval(x0,x1),G.Interval(y0,y1)).ToNurbsCurve()


def line(a=(-5,5,0),z=(15,5,0)):
    return G.LineCurve(G.Point3d(*a),G.Point3d(*z))


def hatch(curve):return G.Hatch.Create(G.Plane.WorldXY,curve,List[G.Curve](),0,0,1)


def add(doc,geometry,name):
    attr=Rhino.DocObjects.ObjectAttributes();attr.Name=name
    attr.ObjectColor=sd.Color.OrangeRed;attr.ColorSource=Rhino.DocObjects.ObjectColorSource.ColorFromObject
    attr.PlotWeight=0.6;attr.PlotWeightSource=Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
    attr.SetUserString('Leftover fixture','preserve me')
    ident=doc.Objects.AddHatch(geometry,attr) if isinstance(geometry,G.Hatch) else doc.Objects.AddCurve(geometry,attr)
    geometry.Dispose()
    return doc.Objects.FindId(ident)


def setup(doc,curve):
    r=rect();h=hatch(r);r.Dispose()
    return [add(doc,h,'input hatch'),add(doc,curve,'input open curve')]


def tool(doc,src):return ns['Builder'](doc,src)


def stroke(b,members=None,erase=False):
    b.begin_stroke(erase)
    for i in sorted(members if members is not None else range(len(b.cells))):b.touch(i)
    b.apply_stroke()


def objects(doc):return {str(o.Id) for o in doc.Objects}


def pieces(b):return [c for r in b.leftovers for c in r['pieces']]


def run(name,test):
    doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
    try:test(doc)
    except Exception as error:failures.append(name+': '+repr(error))
    finally:doc.Dispose()


def crossing(doc):
    src=setup(doc,line());b=tool(doc,src)
    try:
        check('initial open curve remains whole in preview',len(pieces(b))==1 and abs(pieces(b)[0].GetLength()-20)<1e-8)
        b.begin_stroke()
        for i in range(len(b.cells)):b.touch(i)
        b.update_pending()
        check('drag preview shows both tails before release',len(b.pending_leftovers[0]['pieces'])==2)
        check('drag preview does not alter document',len(objects(doc))==2)
        b.apply_stroke()
        check('merge preserves two tails',len(pieces(b))==2)
        check('merge removes only ten units of divider',abs(sum(c.GetLength() for c in pieces(b))-10)<1e-8)
        check('applied stroke disposes pending preview',b.pending_leftovers is None)
        ids=b.commit_output();out=[doc.Objects.FindId(i) for i in ids]
        tails=[o for o in out if isinstance(o.Geometry,G.Curve)]
        check('Finish makes hatch and two open tails',len(ids)==3 and len(tails)==2 and all(not o.Geometry.IsClosed for o in tails))
        check('Finish replaces only original selected objects',objects(doc)=={str(i) for i in ids})
        check('tail names preserved',all(o.Name=='input open curve' for o in tails))
        check('tail colors preserved',all(o.Attributes.ObjectColor.ToArgb()==sd.Color.OrangeRed.ToArgb() for o in tails))
        check('tail print weights preserved',all(abs(o.Attributes.PlotWeight-0.6)<1e-9 for o in tails))
        check('tail user text preserved',all(o.Attributes.GetUserString('Leftover fixture')=='preserve me' for o in tails))
    finally:b.dispose_geometry()


def untouched(doc):
    src=setup(doc,line());b=tool(doc,src)
    try:
        old_id=src[1].Id;crc=src[1].Geometry.DataCRC(0)
        b.commit_output()
        retained=doc.Objects.FindId(old_id)
        check('untouched divider keeps original ID',retained is not None and not retained.IsDeleted)
        check('untouched divider geometry unchanged',retained.Geometry.DataCRC(0)==crc)
        check('untouched divider not duplicated',sum(o.Name=='input open curve' for o in doc.Objects)==1)
    finally:b.dispose_geometry()


def no_region_edge(doc):
    for name,c in [('unrelated',line((-5,15,0),(15,15,0))),('dangling',line((-5,5,0),(5,5,0))),('tangent',line((-5,5,0),(5,15,0)))]:
        src=setup(doc,c);b=tool(doc,src)
        try:
            crc=src[1].Geometry.DataCRC(0)
            stroke(b,erase=True)
            check(name+': no curve span consumed',not b.leftovers[0]['consumed'])
            ids=b.commit_output()
            check(name+': curve retained with original ID and geometry',doc.Objects.FindId(src[1].Id).Geometry.DataCRC(0)==crc)
            check(name+': no duplicate leftover output',not ids)
        finally:b.dispose_geometry()


def undo(doc):
    src=setup(doc,line());b=tool(doc,src)
    try:
        stroke(b);check('gesture records affected cells',b.affected==set(range(len(b.cells))))
        b.undo();check('Undo clears affected cells',not b.affected)
        check('Undo restores full original preview',len(pieces(b))==1 and abs(pieces(b)[0].GetLength()-20)<1e-8)
        stroke(b,erase=True);check('erase consumes original divider without restoring internal line',not b.groups and len(pieces(b))==2)
        b.undo();check('Undo erase restores eligible regions and entire curve',len(b.groups)==2 and len(pieces(b))==1)
    finally:b.dispose_geometry()


def keep(doc):
    src=setup(doc,line());b=tool(doc,src)
    try:
        stroke(b);b.keep_originals=True;before=objects(doc);ids=b.commit_output()
        check('Keep originals retains both sources',before<=objects(doc))
        check('Keep originals does not add duplicate tails',len(ids)==1 and isinstance(doc.Objects.FindId(ids[0]).Geometry,G.Hatch))
    finally:b.dispose_geometry()


def screenshot(doc):
    points=[(6,8), (4,14),(-4,15),(-8,10),(-6,3),(0,4),(12,3),(17,0)]
    poly=G.PolylineCurve(List[G.Point3d]([G.Point3d(x,y,0) for x,y in points]))
    src=setup(doc,poly);b=tool(doc,src)
    try:
        stroke(b)
        check('screenshot: outside excursion survives',all(min(c.PointAt(c.ClosestPoint(G.Point3d(x,y,0))[1]).DistanceTo(G.Point3d(x,y,0)) for c in pieces(b))<1e-7 for x,y in points[1:5]))
        check('screenshot: leftovers remain open curves',pieces(b) and all(not c.IsClosed for c in pieces(b)))
        ids=b.commit_output();out=[doc.Objects.FindId(i).Geometry for i in ids]
        check('screenshot: outside region is not automatically closed',all(not g.IsClosed for g in out if isinstance(g,G.Curve)))
        check('screenshot: merged hatch remains one hatch',sum(isinstance(g,G.Hatch) for g in out)==1)
    finally:b.dispose_geometry()


def open_region(doc):
    coords=[((-5,0,0),(15,0,0)),((10,-5,0),(10,15,0)),((15,10,0),(-5,10,0)),((0,15,0),(0,-5,0))]
    src=[add(doc,line(a,z),'open grid') for a,z in coords]
    b=tool(doc,src)
    try:
        check('open-only region initially has no closed output',all(not b.is_output_group(g) for g in b.groups))
        before=objects(doc);ids=b.commit_output()
        check('unacted open-only region keeps four original curves',not ids and objects(doc)==before)
        stroke(b)
        check('clicking open-only region explicitly promotes it',b.is_output_group(b.groups[0]))
        check('promoted region leaves eight tails',len(pieces(b))==8)
        b.undo();check('Undo promotion restores open-only state',not b.affected and all(not b.is_output_group(g) for g in b.groups) and len(pieces(b))==4)
        stroke(b);ids=b.commit_output()
        out=[doc.Objects.FindId(i).Geometry for i in ids]
        check('promoted output has one closed shape and eight open tails',len(out)==9 and sum(g.IsClosed for g in out)==1)
    finally:b.dispose_geometry()


def two_regions(doc):
    src=[]
    for x in [0,30]:
        for a,z in [((x,0,0),(x+10,0,0)),((x+10,0,0),(x+10,10,0)),((x+10,10,0),(x,10,0)),((x,10,0),(x,0,0))]:src.append(add(doc,line(a,z),'open boundary'))
    b=tool(doc,src)
    try:
        stroke(b,{b.hit(G.Point3d(5,5,0))})
        ids=b.commit_output()
        check('only dragged open-only region becomes closed',len(ids)==1 and doc.Objects.FindId(ids[0]).Geometry.IsClosed)
        check('other open-only region keeps original source curves',all(doc.Objects.FindId(o.Id) is not None and not doc.Objects.FindId(o.Id).IsDeleted for o in src[4:]))
    finally:b.dispose_geometry()


def arc(doc):
    r=rect(-5,5,-2,12);h=hatch(r);r.Dispose()
    c=G.ArcCurve(G.Arc(G.Point3d(-10,0,0),G.Point3d(0,10,0),G.Point3d(10,0,0)))
    src=[add(doc,h,'hatch'),add(doc,c,'arc')];b=tool(doc,src)
    try:
        stroke(b)
        check('arc leftovers remain exact ArcCurves',len(pieces(b))==2 and all(isinstance(c,G.ArcCurve) for c in pieces(b)))
        check('arc leftover lengths correct',abs(sum(c.GetLength() for c in pieces(b))-20*math.pi/3)<0.002)
    finally:b.dispose_geometry()


def tilted(doc):
    r=rect();h=hatch(r);r.Dispose();c=line()
    plane=G.Plane(G.Point3d(40,50,60),G.Vector3d(1,2,3));t=G.Transform.PlaneToPlane(G.Plane.WorldXY,plane)
    h.Transform(t);c.Transform(t)
    src=[add(doc,h,'tilted hatch'),add(doc,c,'tilted line')];b=tool(doc,src)
    try:
        stroke(b)
        check('tilted leftovers stay on their original plane',len(pieces(b))==2 and all(abs(plane.DistanceTo(p.PointAtStart))<1e-7 and abs(plane.DistanceTo(p.PointAtEnd))<1e-7 for p in pieces(b)))
        check('tilted leftovers preserve physical length',abs(sum(p.GetLength() for p in pieces(b))-10)<1e-7)
    finally:b.dispose_geometry()


def domains(doc):
    c=line((15,5,0),(-5,5,0));c.Domain=G.Interval(100,500)
    src=setup(doc,c);b=tool(doc,src)
    try:
        stroke(b)
        check('reversed curve with custom domain keeps both tails',len(pieces(b))==2 and abs(sum(p.GetLength() for p in pieces(b))-10)<1e-7)
    finally:b.dispose_geometry()


def rollback(doc):
    src=setup(doc,line());before=objects(doc);b=tool(doc,src)
    try:
        stroke(b);original=b.delete_source;calls=[0]
        def fail_second(source):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('injected failure')
            original(source)
        b.delete_source=fail_second
        try:b.commit_output();raise AssertionError('failure missing')
        except RuntimeError:pass
        check('rollback restores originals and removes newly added tails',objects(doc)==before)
    finally:b.dispose_geometry()


for name,test in [('crossing',crossing),('untouched',untouched),('non-boundary curves',no_region_edge),('Undo',undo),('Keep originals',keep),('screenshot',screenshot),('open-only region',open_region),('two open regions',two_regions),('arcs',arc),('tilted',tilted),('domains',domains),('rollback',rollback)]:run(name,test)
report={'passed':len(checks),'checks':checks,'failures':failures}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-leftover-tests.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps({k:report[k] for k in ['passed','failures']}))
if failures:raise AssertionError(str(failures))
