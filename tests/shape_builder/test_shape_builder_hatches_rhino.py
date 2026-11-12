# -*- coding: utf-8 -*-
"""Hatch, replacement, rollback and preview tests in disposable Rhino documents."""
import os
import json
import Rhino
import System.Drawing as sd
from System.Collections.Generic import List

PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'test_hatches','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
G=Rhino.Geometry
checks=[]
failures=[]


def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)


def rect(x0=0,x1=10,y0=0,y1=10):
    return G.Rectangle3d(G.Plane.WorldXY,G.Interval(x0,x1),G.Interval(y0,y1)).ToNurbsCurve()


def hatch(outer,inner=None,pattern=1,rotation=0.37,scale=2.5):
    h=G.Hatch.Create(G.Plane.WorldXY,outer,ns['net_curves'](inner or []),max(0,pattern),rotation,scale)
    h.PatternIndex=pattern
    h.BasePoint=G.Point3d(3,4,0)
    return h


def add(doc,geometry):
    attr=Rhino.DocObjects.ObjectAttributes()
    attr.ObjectColor=sd.Color.DarkOrchid
    attr.ColorSource=Rhino.DocObjects.ObjectColorSource.ColorFromObject
    attr.SetUserString('Fixture','preserved')
    ident=doc.Objects.AddHatch(geometry,attr) if isinstance(geometry,G.Hatch) else doc.Objects.AddCurve(geometry,attr)
    return doc.Objects.FindId(ident)


def objects(doc):return {str(o.Id) for o in doc.Objects}




def merge(b):
    b.dragging=True;b.stroke=set(range(len(b.cells)));b.erase=False;b.apply_stroke()


def run(name,test):
    doc=Rhino.RhinoDoc.CreateHeadless(None)
    doc.ModelAbsoluteTolerance=0.001
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Hatch1)
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Hatch2)
    try:test(doc)
    except Exception as error:failures.append(name+': '+repr(error))
    finally:doc.Dispose()


def replacement(doc):
    a,z=rect(),rect(5,15)
    src=[add(doc,a),add(doc,z)];a.Dispose();z.Dispose()
    b=ns['Builder'](doc,src)
    try:
        check('curves: replace originals by default',not b.keep_originals)
        check('curves: curve output follows each master',all(not b.group_is_hatch(g) for g in b.groups))
        check('preview: exact source IDs recorded',b.source_ids=={o.Id for o in src})
        before=objects(doc)
        merge(b)
        check('preview: editing leaves document untouched',objects(doc)==before)
        ids=b.commit_output()
        check('replace: one result replaces two sources',len(ids)==1 and objects(doc)=={str(i) for i in ids})
        check('replace: valid closed result',doc.Objects.FindId(ids[0]).Geometry.IsClosed)
    finally:b.dispose_geometry()


def keep(doc):
    a=rect();src=add(doc,a);a.Dispose()
    b=ns['Builder'](doc,[src]);b.keep_originals=True
    try:
        ids=b.commit_output()
        check('keep: source and output coexist',objects(doc)=={str(src.Id)}|{str(i) for i in ids})
    finally:b.dispose_geometry()


def hatches(doc):
    a,z=rect(),rect(5,15)
    h1,h2=hatch(a),hatch(z,pattern=2,rotation=0.8,scale=4)
    src=[add(doc,h1),add(doc,h2)]
    for g in (a,z,h1,h2):g.Dispose()
    b=ns['Builder'](doc,src)
    try:
        check('hatches: hatch output follows each master',all(b.group_is_hatch(g) for g in b.groups))
        check('hatches: three overlapping cells',len(b.cells)==3)
        # Untouched regions retain each contributing hatch's style.
        prepared=b.make_outputs()
        try:
            styles={geometry.PatternIndex for gs,attr in prepared for geometry in gs}
            check('hatches: untouched regions retain both source patterns',styles=={1,2})
        finally:
            for gs,attr in prepared:
                for g in gs:g.Dispose()
                attr.Dispose()
        merge(b)
        ids=b.commit_output();out=doc.Objects.FindId(ids[0])
        check('hatches: merged output is a hatch',len(ids)==1 and isinstance(out.Geometry,G.Hatch))
        check('hatches: originals replaced',objects(doc)=={str(i) for i in ids})
        h=out.Geometry
        check('hatches: first contributing pattern preserved',h.PatternIndex==1)
        check('hatches: rotation preserved',abs(h.PatternRotation-0.37)<1e-9)
        check('hatches: scale preserved',abs(h.PatternScale-2.5)<1e-9)
        check('hatches: base point preserved',h.BasePoint.DistanceTo(G.Point3d(3,4,0))<1e-8)
        check('hatches: color preserved',out.Attributes.ObjectColor.ToArgb()==sd.Color.DarkOrchid.ToArgb())
        check('hatches: user text preserved',out.Attributes.GetUserString('Fixture')=='preserved')
    finally:b.dispose_geometry()


def holes(doc):
    outer,inner=rect(0,20,0,20),rect(5,15,5,15)
    h=hatch(outer,[inner]);src=add(doc,h)
    for g in (outer,inner,h):g.Dispose()
    b=ns['Builder'](doc,[src])
    try:
        check('hatch hole: empty interior is not selectable',b.hit(G.Point3d(10,10,0)) is None)
        check('hatch hole: ring stays one cell',len(b.cells)==1)
        ids=b.commit_output();out=doc.Objects.FindId(ids[0]).Geometry
        loops=list(out.Get3dCurves(False))
        check('hatch hole: inner boundary survives output',len(loops)==1)
        for c in loops:c.Dispose()
    finally:b.dispose_geometry()


def divided_hole(doc):
    outer,inner=rect(0,20,0,20),rect(5,15,5,15)
    h=hatch(outer,[inner]);line=G.LineCurve(G.Point3d(-2,10,0),G.Point3d(22,10,0))
    src=[add(doc,h),add(doc,line)]
    b=ns['Builder'](doc,src)
    try:
        check('mixed hole: divider does not fill empty courtyard',b.hit(G.Point3d(10,8,0)) is None and b.hit(G.Point3d(10,12,0)) is None)
        check('mixed hole: hatch ring remains selectable',b.hit(G.Point3d(2,2,0)) is not None)
    finally:
        b.dispose_geometry()
        for g in (outer,inner,h,line):g.Dispose()


def mixed(doc):
    a,z=rect(),rect(5,15);h=hatch(a)
    src=[add(doc,h),add(doc,z)]
    for g in (a,z,h):g.Dispose()
    b=ns['Builder'](doc,src)
    try:
        check('mixed: curves and hatches accepted',len(b.cells)==3)
        check('mixed: both output types coexist before merging',{b.group_is_hatch(g) for g in b.groups}=={False,True})
        merge(b);ids=b.commit_output()
        check('mixed: merged hatch replaces both inputs',len(ids)==1 and len(objects(doc))==1 and isinstance(doc.Objects.FindId(ids[0]).Geometry,G.Hatch))
    finally:b.dispose_geometry()


def rollback(doc):
    a,z=rect(),rect(5,15);src=[add(doc,a),add(doc,z)]
    for g in (a,z):g.Dispose()
    before=objects(doc)
    b=ns['Builder'](doc,src)
    try:
        merge(b)
        original=b.delete_source
        calls=[0]
        def broken(source):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('Injected second deletion failure')
            original(source)
        b.delete_source=broken
        try:b.commit_output();raise AssertionError('failure was not raised')
        except RuntimeError as error:check('rollback: expected failure reported','Injected' in str(error))
        check('rollback: deleted original restored and outputs removed',objects(doc)==before)
        check('rollback: original attributes restored',all(doc.Objects.FindId(o.Id).Attributes.GetUserString('Fixture')=='preserved' for o in src))
    finally:b.dispose_geometry()


def changed(doc):
    a=rect();src=add(doc,a);a.Dispose()
    b=ns['Builder'](doc,[src])
    try:
        doc.Objects.Transform(src.Id,G.Transform.Translation(0,0,1),True)
        before=objects(doc)
        try:b.commit_output();raise AssertionError('changed source was accepted')
        except RuntimeError:check('changed source: rejected before commit',True)
        check('changed source: document unchanged by failed commit',objects(doc)==before)
    finally:b.dispose_geometry()


def live_preview(doc):
    a,z=rect(),rect(5,15);b=ns['Builder'](doc,[a,z])
    for g in (a,z):g.Dispose()
    try:
        b.dragging=True;b.stroke={0,1};b.update_pending()
        check('drag preview: selected regions have one combined outline',len(b.pending_loops)==1 and len(b.pending_loops[0])==1)
        b.apply_stroke()
        check('drag preview: temporary geometry cleared after stroke',not b.pending_loops)
        check('status: merged and separate counts shown','1 merged | 1 separate' in b.status_text())
    finally:b.dispose_geometry()


def tilted(doc):
    a,z=rect(),rect(5,15);hs=[hatch(a),hatch(z)]
    target=G.Plane(G.Point3d(10,20,30),G.Vector3d(1,2,3))
    transform=G.Transform.PlaneToPlane(G.Plane.WorldXY,target)
    for h in hs:h.Transform(transform)
    src=[add(doc,h) for h in hs]
    b=ns['Builder'](doc,src)
    try:
        merge(b);ids=b.commit_output();out=doc.Objects.FindId(ids[0]).Geometry
        loops=list(out.Get3dCurves(True))
        check('tilted hatch: output stays on source plane',all(abs(target.DistanceTo(c.PointAtStart))<1e-7 for c in loops))
        check('tilted hatch: output remains in source location',out.GetBoundingBox(True).Center.DistanceTo(target.Origin)<20)
        check('tilted hatch: pattern rotation preserved',abs(out.PatternRotation-src[0].Geometry.PatternRotation)<1e-8)
        for c in loops:c.Dispose()
    finally:
        b.dispose_geometry()
        for g in [a,z]+hs:g.Dispose()


def untouched_curve(doc):
    a=rect();src=add(doc,a);a.Dispose()
    b=ns['Builder'](doc,[src])
    try:
        ids=b.commit_output();out=doc.Objects.FindId(ids[0]).Geometry
        check('untouched curve: remains a valid curve',isinstance(out,G.Curve) and out.IsValid)
        check('untouched curve: source layer preserved',doc.Objects.FindId(ids[0]).Attributes.LayerIndex==src.Attributes.LayerIndex)
    finally:b.dispose_geometry()


def untouched_hatch(doc):
    a=rect();h=hatch(a);src=add(doc,h);a.Dispose();h.Dispose()
    b=ns['Builder'](doc,[src])
    try:
        ids=b.commit_output()
        check('untouched hatch: remains a valid hatch',isinstance(doc.Objects.FindId(ids[0]).Geometry,G.Hatch) and doc.Objects.FindId(ids[0]).Geometry.IsValid)
    finally:b.dispose_geometry()


for name,test in [('replacement',replacement),('keep',keep),('hatches',hatches),('holes',holes),('divided hole',divided_hole),('mixed',mixed),('rollback',rollback),('changed',changed),('preview',live_preview),('tilted',tilted),('untouched curve',untouched_curve),('untouched hatch',untouched_hatch)]:run(name,test)
report={'passed':len(checks),'checks':checks,'failures':failures}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-hatch-tests.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps({k:report[k] for k in ('passed','failures')}))
if failures:raise AssertionError(str(failures))
