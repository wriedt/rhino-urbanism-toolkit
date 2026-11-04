"""Create a small, labelled playground in the connected test Rhino document."""
import json
import os
import sys

import Rhino
from System import Guid
from System.Collections.Generic import List
from System.Drawing import Color

sys.path.insert(0,r'C:\Projects\rhino-urbanism')
import block_layers as rules

doc=__rhino_doc__
if any(not d.IsDeleted and d.Name.startswith('BLX_') for d in doc.InstanceDefinitions):
    raise ValueError('The examples already exist. Reopen block-layer-examples.3dm for a fresh start.')


def layer(path, colour):
    parent=Guid.Empty
    parts=[]
    for name in path.split('::'):
        parts.append(name)
        index=doc.Layers.FindByFullPath('::'.join(parts),-1)
        if index<0:
            value=Rhino.DocObjects.Layer();value.Name=name;value.ParentLayerId=parent
            value.Color=colour
            index=doc.Layers.Add(value)
            assert index>=0
        parent=doc.Layers[index].Id
    return index


def attributes(index,name=''):
    a=Rhino.DocObjects.ObjectAttributes();a.LayerIndex=index;a.Name=name
    return a


def circle(x,y,r):
    return Rhino.Geometry.Circle(Rhino.Geometry.Point3d(x,y,0),r).ToNurbsCurve()


def rectangle(x,y,w,h):
    return Rhino.Geometry.Rectangle3d(Rhino.Geometry.Plane.WorldXY,
        Rhino.Geometry.Interval(x,x+w),Rhino.Geometry.Interval(y,y+h)).ToNurbsCurve()


def line(x1,y1,x2,y2):
    return Rhino.Geometry.LineCurve(Rhino.Geometry.Point3d(x1,y1,0),Rhino.Geometry.Point3d(x2,y2,0))


def definition(name,geometry,nested=None):
    geo=List[Rhino.Geometry.GeometryBase](geometry)
    attrs=List[Rhino.DocObjects.ObjectAttributes]()
    for _ in geometry:
        a=attributes(geometry_layer);a.ColorSource=Rhino.DocObjects.ObjectColorSource.ColorFromParent
        attrs.Add(a)
    if nested is not None:
        geo.Add(Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[nested].Id,
            Rhino.Geometry.Transform.Translation(0,0,0)))
        attrs.Add(attributes(source_layer))
    index=doc.InstanceDefinitions.Add(name,'Block layer assignment playground',Rhino.Geometry.Point3d.Origin,geo,attrs)
    assert index>=0
    return index


def place(index,x,y,hidden=False):
    a=attributes(source_layer,doc.InstanceDefinitions[index].Name)
    if hidden:a.Mode=Rhino.DocObjects.ObjectMode.Hidden
    object_id=doc.Objects.AddInstanceObject(index,Rhino.Geometry.Transform.Translation(x,y,0),a)
    assert object_id!=Guid.Empty
    return object_id


def assign(index,path):
    target=doc.Layers.FindByFullPath(path,-1)
    target_id=doc.Layers[target].Id if target>=0 else Guid.NewGuid()
    doc.InstanceDefinitions[index].SetUserString(rules.ASSIGNMENT_KEY,
        json.dumps(dict(version=1,layer_id=str(target_id),layer_path=path)))


def text(value,x,y,size=1.0):
    plane=Rhino.Geometry.Plane(Rhino.Geometry.Point3d(x,y,0),Rhino.Geometry.Vector3d.ZAxis)
    assert doc.Objects.AddText(value,plane,size,'Arial',False,False,attributes(instructions_layer))!=Guid.Empty


def panel(x,y,title,subtitle,notes):
    doc.Objects.AddCurve(rectangle(x,y,64,30),attributes(instructions_layer))
    text(title,x+2,y+26,1.35)
    text(subtitle,x+2,y+22.5,0.95)
    for n,note in enumerate(notes):text(note,x+2,y+4.5-n*1.6,0.85)


undo=doc.BeginUndoRecord('Set up block layer examples')
redraw=doc.Views.RedrawEnabled
try:
    doc.Views.RedrawEnabled=False
    source_layer=layer('BL Examples::Source',Color.FromArgb(216,95,76))
    geometry_layer=layer('BL Examples::Geometry',Color.FromArgb(50,75,85))
    instructions_layer=layer('BL Examples::Instructions',Color.FromArgb(34,65,76))
    vehicle_layer=layer('BL Examples::Targets::Vehicles',Color.FromArgb(27,130,151))
    tree_layer=layer('BL Examples::Targets::Trees',Color.FromArgb(37,135,99))
    garden_layer=layer('BL Examples::Targets::Gardens',Color.FromArgb(57,104,181))
    furniture_layer=layer('BL Examples::Targets::Furniture',Color.FromArgb(132,88,174))
    tree_geometry=[circle(0,0,2.7),circle(0,0,0.55),line(-1.9,-1.9,1.9,1.9),line(-1.9,1.9,1.9,-1.9)]
    car_geometry=[rectangle(-4,-1.8,8,3.6),rectangle(-1.8,-1.4,3.6,2.8),
        circle(-2.5,-2,0.6),circle(2.5,-2,0.6),circle(-2.5,2,0.6),circle(2.5,2,0.6)]
    bench_geometry=[rectangle(-3,-1.3,6,2.6),line(-3,0,3,0),line(-2,-1.3,-2,1.3),line(2,-1.3,2,1.3)]
    text('Block layer examples',30,110,2.3)
    text('Run CleanUpBlockLayers. Coral = starting layer. Labels explain what to try.',30,106,1.0)

    panel(30,72,'1. Create a missing target','Two trees share one missing target path.',[
        'Enable Create missing target layers in the review.',
        'Target: BL Example Targets::Landscape::Trees'])
    create=definition('BLX_CreateTree_01',tree_geometry)
    assign(create,'BL Example Targets::Landscape::Trees')
    place(create,46,84);place(create,64,84)

    panel(100,72,'2. Choose an existing layer','The intended vehicle layer is missing.',[
        'Choose existing layer -> BL Examples::Targets::Vehicles.',
        'The saved rule will change to that existing target.'])
    car=definition('BLX_MapCar_01',car_geometry)
    assign(car,'BL Example Targets::Vehicles')
    place(car,119,84)

    panel(30,38,'3. Skip a missing target','Keep this tree on its current layer for this run.',[
        'Select its path in the review and click Skip selected.',
        'Target: BL Example Targets::Skipped'])
    skip=definition('BLX_SkipTree_01',tree_geometry)
    assign(skip,'BL Example Targets::Skipped')
    place(skip,49,50)

    panel(100,38,'4. Nested blocks','Two garden copies share one nested tree reference.',[
        'Cleanup moves the gardens to Gardens, nested trees to Trees.',
        'In Assign, Include nested definitions reveals the tree rule.'])
    nested_tree=definition('BLX_NestedTree_01',tree_geometry)
    assign(nested_tree,'BL Examples::Targets::Trees')
    garden=definition('BLX_Garden_01',[rectangle(-5,-4,10,8)],nested_tree)
    assign(garden,'BL Examples::Targets::Gardens')
    place(garden,115,50);place(garden,143,50)

    panel(30,4,'5. No assignment yet','This bench has no saved layer rule.',[
        'Cleanup reports it as unassigned and leaves it alone.',
        'Try Assign -> BL Examples::Targets::Furniture, then Apply now.'])
    bench=definition('BLX_UnassignedBench_01',bench_geometry)
    place(bench,49,16)

    panel(100,4,'6. A shared, protected copy','A second copy of this garden is hidden.',[
        'The nested tree is skipped: its reference is shared with a hidden copy.',
        'Run Show, then Cleanup again to allow the nested tree to move.'])
    protected_tree=definition('BLX_ProtectedTree_01',tree_geometry)
    assign(protected_tree,'BL Examples::Targets::Trees')
    protected_garden=definition('BLX_ProtectedGarden_01',[rectangle(-5,-4,10,8)],protected_tree)
    assign(protected_garden,'BL Examples::Targets::Gardens')
    place(protected_garden,115,16)
    hidden=place(protected_garden,143,16,hidden=True)
    text('Hidden copy here',135,23,0.85)
    doc.Objects.AddCurve(rectangle(138,12,10,8),attributes(instructions_layer))
    text('Reset: reopen the saved block-layer-examples.3dm file.',30,-1,1.0)
    doc.Modified=True
finally:
    doc.Views.RedrawEnabled=redraw
    if undo:doc.EndUndoRecord(undo)

doc.Objects.UnselectAll()
view=doc.Views.Find('Top',False)
if view:
    doc.Views.ActiveView=view
    view.Maximized=True
    view.ActiveViewport.ZoomBoundingBox(Rhino.Geometry.BoundingBox(
        Rhino.Geometry.Point3d(25,-5,-1),Rhino.Geometry.Point3d(169,117,1)))
doc.Views.Redraw()
groups=rules.missing_targets(doc)
assert len(groups)==3
assert sorted(g['occurrences'] for g in groups)==[1,1,2]
rows=rules.plan_cleanup(doc)
assert any(r['status']=='shared with protected copies' and r['block']=='BLX_ProtectedTree_01' for r in rows)
assert any(r['status']=='unassigned' and r['block']=='BLX_UnassignedBench_01' for r in rows)
out=r'C:\Projects\rhino-urbanism\work\block-layer-examples.3dm'
options=Rhino.FileIO.FileWriteOptions();options.SuppressDialogBoxes=True;options.UpdateDocumentPath=True
assert doc.WriteFile(out,options)
print('Example scene ready:',out)
print('Missing target paths:',[g['path'] for g in groups])
