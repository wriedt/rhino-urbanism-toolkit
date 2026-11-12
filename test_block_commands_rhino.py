"""Focused commands: real document operations and failure paths in an isolated document."""
import importlib
import json
from pathlib import Path
import Rhino
import scriptcontext as sc
from System import Guid
from System.Collections.Generic import List
import block_versions as naming
import block_actions as actions
import block_layers as rules
for module in (naming, actions, rules):
    importlib.reload(module)


def run():
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    previous = sc.doc
    sc.doc = doc
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def reject(callback, label):
        try:
            callback()
        except (ValueError, RuntimeError):
            check(True, label)
            return
        raise AssertionError(label)

    def add(name, child=None):
        geo, attrs = List[Rhino.Geometry.GeometryBase](), List[Rhino.DocObjects.ObjectAttributes]()
        geo.Add(Rhino.Geometry.Point(Rhino.Geometry.Point3d.Origin) if child is None else
                Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[child].Id,
                                                         Rhino.Geometry.Transform.Identity))
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.Name = 'Member'; attr.SetUserString('part', 'keep')
        attrs.Add(attr)
        index = doc.InstanceDefinitions.Add(name, 'description', Rhino.Geometry.Point3d.Origin, geo, attrs)
        assert index >= 0
        doc.InstanceDefinitions[index].SetUserString('metadata', 'keep')
        return index

    def place(index):
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.Name = 'Copy'; attr.SetUserString('instance', 'keep')
        return doc.Objects.AddInstanceObject(index, Rhino.Geometry.Transform.Translation(3,4,5), attr)

    def spec(index, token):
        return naming.describe(doc.InstanceDefinitions[index].Name, token)

    try:
        first, last = add('House_001'), add('House_008')
        ids = [place(first) for _ in range(3)]
        before = [actions.instance_stamp(doc.Objects.FindId(i)) for i in ids]
        p = actions.version_plan(doc, ids[:2], spec(first,'001'))
        check(p['new_name']=='House_009', 'highest unused version participates')
        check(doc.Objects.FindId(ids[0]).InstanceDefinition.Index==first, 'version plan has no side effects')
        actions.apply_versions(doc,[p])
        new = doc.Objects.FindId(ids[0]).InstanceDefinition
        check(new.Name=='House_009' and doc.Objects.FindId(ids[1]).InstanceDefinition.Id==new.Id,
              'selected copies share one new independent definition')
        check(doc.Objects.FindId(ids[2]).InstanceDefinition.Index==first, 'unselected copy stays on source')
        check(new.Id!=doc.InstanceDefinitions[first].Id, 'new version has independent identity')
        check(new.GetUserString('metadata')=='keep' and new.Description=='description', 'definition metadata preserved')
        check(new.GetObjects()[0].Attributes.GetUserString('part')=='keep', 'member attributes preserved')
        obj=doc.Objects.FindId(ids[0])
        check(obj.Attributes.GetUserString('instance')=='keep' and obj.Attributes.Name=='Copy', 'instance attributes preserved')
        check(obj.InstanceXform==Rhino.Geometry.Transform.Translation(3,4,5), 'transform preserved')
        p=actions.version_plan(doc,[ids[2]],spec(first,'001'))
        attr=doc.Objects.FindId(ids[2]).Attributes.Duplicate(); attr.Name='Changed'
        doc.Objects.ModifyAttributes(ids[2],attr,True)
        reject(lambda:actions.apply_versions(doc,[p]), 'stale selected copy rejected')
        p=actions.version_plan(doc,[ids[2]],spec(first,'001'))
        add('Unrelated')
        reject(lambda:actions.apply_versions(doc,[p]), 'stale definition review rejected')

        plain=add('Unversioned'); plain_id=place(plain)
        p=actions.version_plan(doc,[plain_id],naming.describe('Unversioned_v01','v01'),baseline='Unversioned_v01')
        actions.apply_versions(doc,[p])
        check(doc.InstanceDefinitions[plain].Name=='Unversioned_v01' and
              doc.Objects.FindId(plain_id).InstanceDefinition.Name=='Unversioned_v02','explicit starting name supported')
        alpha=add('Letter_Z'); alpha_id=place(alpha)
        actions.apply_versions(doc,[actions.version_plan(doc,[alpha_id],spec(alpha,'Z'))])
        check(doc.Objects.FindId(alpha_id).InstanceDefinition.Name=='Letter_AA','alphabetic carry supported in document')

        a,b,c,d=[add('Gap_'+suffix) for suffix in ('12','12 01','13','14')]
        plan=naming.consolidation_plan(actions.read_definitions(doc),spec(a,'12'),True)
        actions.apply_names(doc,plan)
        check([doc.InstanceDefinitions[i].Name for i in (a,b,c,d)]==['Gap_12','Gap_13','Gap_14','Gap_15'],
              'duplicate branches become sequential independent definitions')
        check(doc.InstanceDefinitions[b].GetUserString('metadata')=='keep','consolidation preserves metadata')
        plan=naming.rename_plan(actions.read_definitions(doc),spec(a,'12'),'Court_','')
        actions.apply_names(doc,plan)
        check([doc.InstanceDefinitions[i].Name for i in (a,b,c,d)]==['Court_12','Court_13','Court_14','Court_15'],
              'family rename includes unused definitions and preserves versions')
        reject(lambda:actions.apply_names(doc,plan),'stale rename plan rejected')

        # Inject failure after staging: transaction must restore all original names.
        plan=naming.rename_plan(actions.read_definitions(doc),spec(a,'12'),'Failed_','')
        original_rename=actions._rename
        def fail_rename(doc,row,name):
            if name=='Failed_13':
                raise RuntimeError('test failure')
            return original_rename(doc,row,name)
        actions._rename=fail_rename
        try:
            reject(lambda:actions.apply_names(doc,plan),'rename failure surfaced')
        finally:
            actions._rename=original_rename
        check([doc.InstanceDefinitions[i].Name for i in (a,b,c,d)]==['Court_12','Court_13','Court_14','Court_15'],
              'failed rename restores every original name')

        layer=Rhino.DocObjects.Layer(); layer.Name='Home'; target=doc.Layers.Add(layer)
        home=str(doc.Layers[target].Id)
        child=add('Child_01'); parent=add('Parent_01',child)
        roots=[place(parent),place(parent)]
        nested=doc.InstanceDefinitions[parent].GetObjects()[0]
        key=lambda i:str(doc.InstanceDefinitions[i].Id)
        rules.save_assignments(doc,{key(parent):home,key(child):home,key(a):home})
        check(rules.read_assignment(doc.InstanceDefinitions[a])['layer_id']==home,'unused definition can receive home rule')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex!=target for i in roots),'saving rules moves no copies')
        top=rules.plan_cleanup(doc,include_nested=False)
        check(len([r for r in top if r['status']=='move'])==2,'top-level review excludes nested references')
        deep=rules.plan_cleanup(doc,include_nested=True)
        row=next(r for r in deep if r['id']==nested.Id)
        check(row['status']=='move' and row['occurrences']==2,'nested reference records both occurrences')
        rules.cleanup(doc,expected=top,include_nested=False)
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==target for i in roots),'apply moves all top-level copies')
        check(doc.Objects.FindId(nested.Id).Attributes.LayerIndex!=target,'top-level apply leaves nested layer intact')
        doc.Objects.Lock(roots[1],True)
        deep=rules.plan_cleanup(doc,include_nested=True)
        check(next(r for r in deep if r['id']==nested.Id)['status']=='shared with protected copies',
              'shared nested reference protected by locked parent')
        doc.Objects.Unlock(roots[1],True)
        deep=rules.plan_cleanup(doc,include_nested=True)
        rules.cleanup(doc,expected=deep,include_nested=True)
        check(doc.Objects.FindId(nested.Id).Attributes.LayerIndex==target,'nested apply moves child onto its own home layer')
        raw=doc.InstanceDefinitions[child].GetUserString(rules.ASSIGNMENT_KEY)
        rules.save_assignments(doc,{key(child):None},{key(child):raw})
        check(rules.read_assignment(doc.InstanceDefinitions[child]) is None,'removing home rule supported')
        reject(lambda:rules.save_assignments(doc,{key(child):home},{key(child):raw}),'stale assignment rejected')
        missing=json.dumps(dict(version=1,layer_id=str(Guid.NewGuid()),layer_path='Gone'))
        doc.InstanceDefinitions[parent].SetUserString(rules.ASSIGNMENT_KEY,missing)
        check(any(r['status']=='missing target layer' for r in rules.plan_cleanup(doc,include_nested=False)),
              'missing home layer is reported without creation')
        doc.InstanceDefinitions[parent].SetUserString(rules.ASSIGNMENT_KEY,'broken')
        check(any(r['status']=='invalid assignment' for r in rules.plan_cleanup(doc)), 'invalid home rule safely reported')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==target for i in roots),'unresolved rules do not move copies')

        # Linked definitions with legacy rules must never move or expose contents.
        import tempfile
        import os
        handle,path=tempfile.mkstemp(suffix='.3dm'); os.close(handle)
        try:
            source=Rhino.FileIO.File3dm()
            source.Objects.AddPoint(Rhino.Geometry.Point3d.Origin)
            check(source.Write(path,8),'linked source fixture written')
            linked=add('Linked_01')
            check(doc.InstanceDefinitions.ModifySourceArchive(linked,path,
                Rhino.DocObjects.InstanceDefinitionUpdateType.Linked,True),'real linked definition created')
            linked_id=place(linked)
            linked_definition=doc.InstanceDefinitions[linked]
            linked_definition.SetUserString(rules.ASSIGNMENT_KEY,
                json.dumps(dict(version=1,layer_id=home,layer_path='Home')))
            row=next(r for r in rules.plan_cleanup(doc,include_nested=True) if r['id']==linked_id)
            check(row['status']=='linked/reference block','linked instance with saved home rule is skipped')
            rules.cleanup(doc,include_nested=True)
            check(doc.Objects.FindId(linked_id).Attributes.LayerIndex!=target,'linked block stays on original layer')
            reject(lambda:rules.save_assignments(doc,{key(linked):home}),'linked home-rule editing rejected')
            reject(lambda:actions.version_plan(doc,[linked_id],spec(linked,'01')),'linked version creation rejected')
        finally:
            if os.path.exists(path):
                os.remove(path)
        print('PASSED {} document checks'.format(len(checks)))
        return checks
    finally:
        sc.doc=previous
        doc.Dispose()


if __name__=='__main__':
    run()
