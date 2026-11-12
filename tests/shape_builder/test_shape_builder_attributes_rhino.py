"""Regression coverage for attributes inherited from open boundary curves."""
import os,json,Rhino
import System.Drawing as sd
from System.Collections.Generic import List
G=Rhino.Geometry
PATH=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','ShapeBuilder.py'))
ns={'__name__':'attribute_tests','__file__':PATH}
exec(compile(open(PATH,encoding='utf-8').read(),PATH,'exec'),ns)
checks,failures=[],[]
def check(name,value):
    if not value:raise AssertionError(name)
    checks.append(name)
def poly(points):return G.PolylineCurve(List[G.Point3d]([G.Point3d(x,y,0) for x,y in points]))
def add(doc,g,a):
    ident=doc.Objects.Add(g,a);g.Dispose()
    return doc.Objects.FindId(ident)
def attributes(doc,by_layer):
    layer=Rhino.DocObjects.Layer();layer.Name='source orange';layer.Color=sd.Color.DarkOrange
    a=Rhino.DocObjects.ObjectAttributes();a.LayerIndex=doc.Layers.Add(layer)
    a.Name='Original custom curve';a.ObjectColor=sd.Color.OrangeRed
    a.ColorSource=(Rhino.DocObjects.ObjectColorSource.ColorFromLayer if by_layer else Rhino.DocObjects.ObjectColorSource.ColorFromObject)
    a.PlotColor=sd.Color.Purple;a.PlotColorSource=Rhino.DocObjects.ObjectPlotColorSource.PlotColorFromObject
    a.PlotWeight=0.65;a.PlotWeightSource=Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromObject
    a.LinetypeSource=Rhino.DocObjects.ObjectLinetypeSource.LinetypeFromObject
    a.SetUserString('Project custom property','retain this value')
    return a
def stroke(b,points):
    b.begin_stroke()
    for x,y in points:
        i=b.hit(G.Point3d(x,y,0));check('stroke hits intended region',i is not None);b.touch(i)
    b.apply_stroke()
def assert_attributes(actual,source,prefix):
    for field in ['Name','LayerIndex','ColorSource','PlotColorSource','PlotWeightSource','PlotWeight','LinetypeSource','LinetypeIndex','MaterialSource','MaterialIndex']:
        check(prefix+': '+field,getattr(actual,field)==getattr(source,field))
    for field in ['ObjectColor','PlotColor']:
        check(prefix+': '+field,getattr(actual,field).ToArgb()==getattr(source,field).ToArgb())
    check(prefix+': user text',actual.GetUserString('Project custom property')=='retain this value')
def screenshot(doc,by_layer):
    attr=attributes(doc,by_layer)
    curve=add(doc,poly([(6,8),(4,14),(-4,15),(-8,10),(-6,3),(0,4),(12,3),(17,0)]),attr)
    r=G.Rectangle3d(G.Plane.WorldXY,10,10).ToNurbsCurve()
    h=G.Hatch.Create(G.Plane.WorldXY,r,List[G.Curve](),0,0,1)
    boundary=add(doc,r,Rhino.DocObjects.ObjectAttributes())
    hatch=add(doc,h,Rhino.DocObjects.ObjectAttributes())
    unrelated=add(doc,poly([(-20,20),(20,20)]),Rhino.DocObjects.ObjectAttributes())
    b=ns['Builder'](doc,[unrelated,hatch,boundary,curve])
    try:
        i=b.hit(G.Point3d(-4,9,0));group=next(g for g in b.groups if i in g)
        check('open region remains potential',not b.is_output_group(group))
        check('contributing curve supplies master',b.output_style(group)['source_id']==curve.Id)
        stroke(b,[(-4,9)]);check('extraction promotes region',b.is_output_group(next(g for g in b.groups if i in g)))
        b.undo();group=next(g for g in b.groups if i in g)
        check('Undo restores potential status',not b.is_output_group(group))
        check('Undo retains master',b.output_style(group)['source_id']==curve.Id)
        stroke(b,[(-4,9),(5,6)])
        check('curve-start merge retains type',not b.group_is_hatch(next(g for g in b.groups if i in g)))
        ids=b.commit_output();out=[doc.Objects.FindId(k) for k in ids]
        closed=[o for o in out if isinstance(o.Geometry,G.Curve) and o.Geometry.IsClosed]
        check('one committed closed curve',len(closed)==1)
        assert_attributes(closed[0].Attributes,attr,'closed output')
        tails=[o for o in out if isinstance(o.Geometry,G.Curve) and not o.Geometry.IsClosed]
        check('unused spans survive',bool(tails))
        for tail in tails:assert_attributes(tail.Attributes,attr,'leftover')
        check('unrelated curve keeps identity',doc.Objects.FindId(unrelated.Id) is not None and not doc.Objects.FindId(unrelated.Id).IsDeleted)
    finally:b.dispose_geometry()
def collective(doc):
    main=attributes(doc,False)
    short=add(doc,poly([(0,-1),(0,11)]),Rhino.DocObjects.ObjectAttributes())
    long=add(doc,poly([(-1,0),(10,0),(10,10),(-1,10)]),main)
    b=ns['Builder'](doc,[short,long])
    try:
        check('longest boundary supplies master',b.output_style(b.groups[0])['source_id']==long.Id)
        check('untouched collective region stays open',not b.is_output_group(b.groups[0]))
        stroke(b,[(5,5)]);ids=b.commit_output()
        closed=[doc.Objects.FindId(k) for k in ids if doc.Objects.FindId(k).Geometry.IsClosed]
        check('collective region creates one closed curve',len(closed)==1)
        assert_attributes(closed[0].Attributes,main,'collective')
    finally:b.dispose_geometry()
for name,test in [('object color',lambda d:screenshot(d,False)),('layer color',lambda d:screenshot(d,True)),('collective',collective)]:
    doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
    doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
    try:test(doc)
    except Exception as e:failures.append(name+': '+repr(e))
    finally:doc.Dispose()
report={'passed':len(checks),'checks':checks,'failures':failures}
with open(os.path.join(os.path.dirname(PATH),'work','shape-builder-attribute-tests.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps({'passed':len(checks),'failures':failures}))
if failures:raise AssertionError(str(failures))
