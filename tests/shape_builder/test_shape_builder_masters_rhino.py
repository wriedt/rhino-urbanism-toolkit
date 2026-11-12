# -*- coding: utf-8 -*-
"""Drag-start hatch inheritance, including chained merges and stroke Undo."""
import os
import json
import Rhino
G=Rhino.Geometry
PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'master_tests','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
checks=[]
doc=Rhino.RhinoDoc.CreateHeadless(None)
doc.ModelAbsoluteTolerance=0.001


def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)


def inputs(ranges):
    result=[]
    for i,(x0,x1) in enumerate(ranges):
        layer=Rhino.DocObjects.Layer();layer.Name='Master '+str(i)
        li=doc.Layers.FindByFullPath(layer.Name,-1)
        if li<0:li=doc.Layers.Add(layer)
        pattern=[Rhino.DocObjects.HatchPattern.Defaults.Hatch1,
                 Rhino.DocObjects.HatchPattern.Defaults.Hatch2,
                 Rhino.DocObjects.HatchPattern.Defaults.Grid][i]
        existing=next((p for p in doc.HatchPatterns if p.Name==pattern.Name),None)
        pi=existing.Index if existing else doc.HatchPatterns.Add(pattern)
        c=G.Rectangle3d(G.Plane.WorldXY,G.Interval(x0,x1),G.Interval(0,10)).ToNurbsCurve()
        h=G.Hatch.Create(G.Plane.WorldXY,c,ns['net_curves']([]),pi,0.2*i,1+i)
        attr=Rhino.DocObjects.ObjectAttributes();attr.LayerIndex=li
        ident=doc.Objects.AddHatch(h,attr)
        result.append(doc.Objects.FindId(ident))
        c.Dispose();h.Dispose()
    return result


def merge(b,start,end):
    b.begin_stroke()
    b.touch(b.hit(start))
    b.stroke_segment(start,end)
    b.touch(b.hit(end))
    b.apply_stroke()


try:
    src=inputs([(0,10),(5,15)])
    for first,last,index in [(2,12,0),(12,2,1)]:
        b=ns['Builder'](doc,src)
        try:
            merge(b,G.Point3d(first,5,0),G.Point3d(last,5,0))
            entry=b.output_style(b.groups[0])
            check('direction {}: start layer wins'.format(index),entry['attributes'].LayerIndex==src[index].Attributes.LayerIndex)
            check('direction {}: start pattern wins'.format(index),entry['hatch'].PatternIndex==src[index].Geometry.PatternIndex)
            prepared=b.make_outputs()
            try:
                check('direction {}: output uses start layer'.format(index),prepared[0][1].LayerIndex==src[index].Attributes.LayerIndex)
                check('direction {}: output uses start scale'.format(index),prepared[0][0][0].PatternScale==src[index].Geometry.PatternScale)
                check('direction {}: output uses start rotation'.format(index),abs(prepared[0][0][0].PatternRotation-src[index].Geometry.PatternRotation)<1e-9)
            finally:
                for gs,attr in prepared:
                    for g in gs:g.Dispose()
                    attr.Dispose()
            b.undo()
            check('direction {}: undo restores source styles'.format(index),len(b.groups)==3 and {b.output_style(g)['hatch'].PatternIndex for g in b.groups}=={s.Geometry.PatternIndex for s in src})
        finally:b.dispose_geometry()
    for s in src:doc.Objects.Delete(s.Id,True)
    src=inputs([(0,10),(5,15),(12,22)])
    b=ns['Builder'](doc,src)
    try:
        merge(b,G.Point3d(2,5,0),G.Point3d(11,5,0))
        first=b.output_style(next(g for g in b.groups if b.hit(G.Point3d(11,5,0)) in g))
        check('first merge master is A',first['hatch'].PatternIndex==src[0].Geometry.PatternIndex)
        merge(b,G.Point3d(11,5,0),G.Point3d(20,5,0))
        check('chained merge inherits existing master A',b.output_style(b.groups[0]) is first)
        b.undo()
        merge(b,G.Point3d(20,5,0),G.Point3d(2,5,0))
        check('reverse chained merge adopts C',b.output_style(b.groups[0])['hatch'].PatternIndex==src[2].Geometry.PatternIndex)
        b.undo()
        check('undo restores previous merged master A',b.output_style(next(g for g in b.groups if b.hit(G.Point3d(11,5,0)) in g)) is first)
        b.begin_stroke(True);b.touch(b.hit(G.Point3d(11,5,0)));b.apply_stroke();b.undo()
        check('erase and undo restore master A',b.output_style(next(g for g in b.groups if b.hit(G.Point3d(11,5,0)) in g)) is first)
    finally:b.dispose_geometry()
finally:doc.Dispose()
report={'passed':len(checks),'checks':checks}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-master-tests.json'),'w') as f:json.dump(report,f,indent=2)
print('PASS drag-start inheritance:',len(checks))
