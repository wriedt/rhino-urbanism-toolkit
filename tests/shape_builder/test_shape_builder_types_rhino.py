# -*- coding: utf-8 -*-
"""Curve-versus-hatch output follows each drag's starting master."""
import os
import json
import Rhino
import System.Drawing as sd
G=Rhino.Geometry
PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'type_tests','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
checks=[]


def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)


def layer(doc,name,color):
    index=doc.Layers.FindByFullPath(name,-1)
    if index<0:
        item=Rhino.DocObjects.Layer();item.Name=name;item.Color=color
        index=doc.Layers.Add(item)
    return index


def pair(doc,x):
    curve_layer=layer(doc,'Curve master',sd.Color.DarkViolet)
    hatch_layer=layer(doc,'Hatch master',sd.Color.SeaGreen)
    pattern=next((p.Index for p in doc.HatchPatterns if p.Name=='Hatch1'),None)
    if pattern is None:pattern=doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Hatch1)
    c=G.Circle(G.Point3d(x+10,10,0),5).ToNurbsCurve()
    r=G.Rectangle3d(G.Plane.WorldXY,G.Interval(x,x+20),G.Interval(0,10)).ToNurbsCurve()
    h=G.Hatch.Create(G.Plane.WorldXY,r,ns['net_curves']([]),pattern,0.4,2.5)
    ca=Rhino.DocObjects.ObjectAttributes();ca.LayerIndex=curve_layer
    ha=Rhino.DocObjects.ObjectAttributes();ha.LayerIndex=hatch_layer
    ci=doc.Objects.AddCurve(c,ca);hi=doc.Objects.AddHatch(h,ha)
    for g in (c,r,h):g.Dispose()
    return [doc.Objects.FindId(ci),doc.Objects.FindId(hi)]


def drag(b,start,end):
    b.begin_stroke();b.touch(b.hit(start));b.stroke_segment(start,end);b.touch(b.hit(end));b.apply_stroke()


def discard(prepared):
    for gs,attr in prepared:
        for g in gs:g.Dispose()
        attr.Dispose()


for hatch_first in (False,True):
    for curve_start in (False,True):
        doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
        b=None
        try:
            src=pair(doc,0)
            b=ns['Builder'](doc,list(reversed(src)) if hatch_first else src)
            suffix='curve start={}, hatch selected first={}'.format(curve_start,hatch_first)
            check('initial mixed types: '+suffix,{b.group_is_hatch(g) for g in b.groups}=={False,True})
            start,end=(G.Point3d(10,13,0),G.Point3d(10,2,0)) if curve_start else (G.Point3d(10,2,0),G.Point3d(10,13,0))
            drag(b,start,end)
            check('one merged shape: '+suffix,len(b.groups)==1)
            check('master type follows drag: '+suffix,b.group_is_hatch(b.groups[0]) is (not curve_start))
            prepared=b.make_outputs()
            try:
                geom=prepared[0][0][0]
                check('actual output type: '+suffix,isinstance(geom,G.Curve if curve_start else G.Hatch))
                check('master layer: '+suffix,prepared[0][1].LayerIndex==src[0 if curve_start else 1].Attributes.LayerIndex)
                if not curve_start:
                    check('hatch pattern: '+suffix,geom.PatternIndex==src[1].Geometry.PatternIndex)
                    check('hatch scale: '+suffix,geom.PatternScale==2.5)
            finally:discard(prepared)
            b.undo()
            check('Undo restores mixed types: '+suffix,len(b.groups)==3 and {b.group_is_hatch(g) for g in b.groups}=={False,True})
        finally:
            if b:b.dispose_geometry()
            doc.Dispose()


doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
b=None
try:
    left=pair(doc,0);right=pair(doc,40)
    b=ns['Builder'](doc,left+right)
    drag(b,G.Point3d(10,13,0),G.Point3d(10,2,0))
    drag(b,G.Point3d(50,2,0),G.Point3d(50,13,0))
    check('same operation: one curve and one hatch',{b.group_is_hatch(g) for g in b.groups}=={False,True} and len(b.groups)==2)
    check('panel reports both output types',b.output_summary()=='1 curve / 1 hatch')
    b.undo()
    check('Undo second drag preserves first curve merge',sum(not b.group_is_hatch(g) and len(g)>1 for g in b.groups)==1)
    drag(b,G.Point3d(50,2,0),G.Point3d(50,13,0))
    before={str(o.Id) for o in doc.Objects}
    ids=b.commit_output()
    check('Finish creates both types together',len(ids)==2 and {isinstance(doc.Objects.FindId(i).Geometry,G.Hatch) for i in ids}=={False,True})
    check('Finish replaces all four chosen originals',not before & {str(o.Id) for o in doc.Objects})
    check('Finish preserves each master layer',{doc.Objects.FindId(i).Attributes.LayerIndex for i in ids}=={left[0].Attributes.LayerIndex,right[1].Attributes.LayerIndex})
finally:
    if b:b.dispose_geometry()
    doc.Dispose()


doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
b=None
try:
    src=pair(doc,0)
    r=G.Rectangle3d(G.Plane.WorldXY,G.Interval(15,30),G.Interval(0,10)).ToNurbsCurve()
    h=G.Hatch.Create(G.Plane.WorldXY,r,ns['net_curves']([]),src[1].Geometry.PatternIndex,0.7,3.0)
    ident=doc.Objects.AddHatch(h,src[1].Attributes);r.Dispose();h.Dispose()
    b=ns['Builder'](doc,src+[doc.Objects.FindId(ident)])
    drag(b,G.Point3d(10,13,0),G.Point3d(10,2,0))
    drag(b,G.Point3d(10,2,0),G.Point3d(25,2,0))
    check('chained curve merge stays a curve',len(b.groups)==1 and not b.group_is_hatch(b.groups[0]))
    b.undo()
    drag(b,G.Point3d(25,2,0),G.Point3d(10,2,0))
    check('starting next drag in hatch changes whole merge to hatch',len(b.groups)==1 and b.group_is_hatch(b.groups[0]))
    b.undo()
    check('Undo restores previous curve master',any(len(g)>1 and not b.group_is_hatch(g) for g in b.groups))
finally:
    if b:b.dispose_geometry()
    doc.Dispose()

report={'passed':len(checks),'checks':checks}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-type-tests.json'),'w') as f:json.dump(report,f,indent=2)
print('PASS drag-start output types:',len(checks))
