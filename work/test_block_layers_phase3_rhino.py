"""Nested-reference integration checks; run through the Rhino 8 MCP runtime."""
import importlib
import importlib.util
import json
import os
import sys
import time

import Rhino
from System import Guid, Array
from System.Collections.Generic import List

ROOT = r'C:\Projects\rhino-urbanism'
sys.path.insert(0, ROOT)
import block_layers as bl
import block_layer_ui as panels
importlib.reload(bl)
importlib.reload(panels)
spec = importlib.util.spec_from_file_location('nested_fixtures', os.path.join(ROOT,'work','test_block_layers_rhino.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def nested(doc, index):
    return next(o for o in doc.InstanceDefinitions[index].GetObjects()
                if isinstance(o, Rhino.DocObjects.InstanceObject))


def set_layer(doc, obj, index):
    a = obj.Attributes.Duplicate()
    a.LayerIndex = index
    assert doc.Objects.ModifyAttributes(obj.Id, a, True)


def run():
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    dialogs = []
    try:
        a = f.layer(doc, 'Leaves')
        b = f.layer(doc, 'Branches')
        hidden_layer = f.layer(doc, 'Hidden', hidden=True)
        leaf = f.definition(doc, 'Leaf_01')
        mid = f.definition(doc, 'Branch_01', leaf)
        root = f.definition(doc, 'Tree_01', mid)
        unused = f.definition(doc, 'Unused_01', leaf)
        roots = [f.instance(doc, root, x=x) for x in [0,20]]
        keys = [str(doc.InstanceDefinitions[i].Id) for i in [root,mid,leaf]]
        mid_id = nested(doc, root).Id
        leaf_id = nested(doc, mid).Id
        nested_crcs = {i:doc.Objects.FindId(i).Geometry.DataCRC(0) for i in [mid_id,leaf_id]}
        ordinary = [(o.Id,o.Attributes.LayerIndex,o.Geometry.DataCRC(0))
                    for i in [root,mid,leaf] for o in doc.InstanceDefinitions[i].GetObjects()
                    if not isinstance(o,Rhino.DocObjects.InstanceObject)]
        graph, nodes = bl.instance_graph(doc)
        check(len(nodes)==3, 'Unused definition excluded from graph')
        check(len(graph)==4, 'One row per stored reference, not per world copy')
        check(next(r for r in graph if r['id']==mid_id)['occurrences']==2, 'Two middle occurrences counted')
        check(next(r for r in graph if r['id']==leaf_id)['occurrences']==2, 'Two deep occurrences counted')
        check(len(bl.definition_inventory(doc))==1, 'Assignment defaults to top-level definitions')
        inventory=bl.definition_inventory(doc, include_nested=True)
        check(len(inventory)==3, 'Nested-only definitions exposed when requested')
        check(next(r for r in inventory if r['id']==keys[2])['nested_count']==2, 'Inventory counts nested occurrences')
        d=panels.AssignmentDialog(doc,[keys[0]]);dialogs.append(d)
        check(not d.nested_box.Checked and len(d.records)==1, 'Include nested toggle defaults off')
        d.nested_box.Checked=True
        check(len(d.records)==3 and len(d.selected_keys())==3, 'Toggle includes and selects reachable nested definitions')
        d.stage_layer(str(doc.Layers[a].Id))
        check(len(d.pending)==3, 'Bulk assignment can stage root and nested definitions')
        d.nested_box.Checked=False
        check(set(d.pending)=={keys[0]} and len(d.records)==1, 'Disabling toggle discards pending nested edits')
        check('Discarded 2' in d.status.Text, 'Discarded nested edits are clearly reported')
        check(all(bl.read_assignment(doc.InstanceDefinitions[i]) is None for i in [root,mid,leaf]), 'Toggle and staging do not mutate model')
        d.Close(False)
        check(set(bl.save_assignments(doc,{keys[1]:str(doc.Layers[b].Id),keys[2]:str(doc.Layers[a].Id)}))
              ==set(keys[1:]), 'Nested-only definitions accept rules')
        original_sc=bl.sc
        class CancelAfterNestedEdit:
            @staticmethod
            def escape_test(throw=False,reset=False):
                return False if reset else (doc.Objects.FindId(mid_id).Attributes.LayerIndex==b or
                                            doc.Objects.FindId(leaf_id).Attributes.LayerIndex==a)
        try:
            bl.sc=CancelAfterNestedEdit
            try:
                bl.cleanup(doc)
                check(False,'Expected partial nested cancellation')
            except RuntimeError as error:
                check('cancelled' in str(error),'Cancellation during nested editing reported')
        finally:
            bl.sc=original_sc
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==0 for i in [mid_id,leaf_id]),
              'Partial nested edits rolled back without rebuilding definitions')
        before_unused=[(o.Id,o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[unused].GetObjects()]
        rows=bl.cleanup(doc)
        check(sum(r['status']=='moved' for r in rows)==2, 'Default cleanup edits both local nesting levels')
        check(doc.Objects.FindId(mid_id).Attributes.LayerIndex==b, 'Middle reference assigned layer applied')
        check(doc.Objects.FindId(leaf_id).Attributes.LayerIndex==a, 'Deep reference assigned layer applied')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==0 for i in roots), 'Unassigned root instances stay put')
        check([(o.Id,o.Attributes.LayerIndex) for o in doc.InstanceDefinitions[unused].GetObjects()]==before_unused,
              'Unused nested references remain untouched')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==layer and doc.Objects.FindId(i).Geometry.DataCRC(0)==crc
                  for i,layer,crc in ordinary), 'Ordinary block geometry remains exact')
        check(nested(doc,root).Id==mid_id and nested(doc,mid).Id==leaf_id,'Nested reference identities preserved')
        check(all(doc.Objects.FindId(i).Geometry.DataCRC(0)==crc for i,crc in nested_crcs.items()),
              'Nested transforms and reference geometry remain exact')
        check(all(r['status']!='move' for r in bl.plan_cleanup(doc)), 'Nested cleanup is repeatable')
        # A shared reference cannot be moved for only its visible occurrences.
        set_layer(doc,doc.Objects.FindId(mid_id),0);set_layer(doc,doc.Objects.FindId(leaf_id),0)
        hidden=f.instance(doc,root,hidden=True);locked=f.instance(doc,root,locked=True)
        rows=bl.plan_cleanup(doc)
        shared=[r for r in rows if r['status']=='shared with protected copies']
        check(len(shared)==2,'Shared references at every depth are protected')
        check(all(r['eligible']==2 and r['occurrences']==4 for r in shared),'Visible and protected copies counted independently')
        check(all(r['protection']=={'hidden':1,'locked':1} for r in shared),'Both hidden and locked ancestry propagated')
        result=bl.cleanup(doc)
        check(not any(r['status']=='moved' for r in result),'Cleanup skips shared edits affecting protected copies')
        check(doc.Objects.FindId(leaf_id).Attributes.LayerIndex==0,'Protected deep instance layer preserved')
        scoped=bl.plan_cleanup(doc,[keys[2]])
        check(len(scoped)==1 and scoped[0]['status']=='shared with protected copies',
              'Scoped preview still accounts for protected out-of-scope ancestors')
        check(doc.Objects.Show(hidden,True) and doc.Objects.Unlock(locked,True),'Unprotect fixture copies')
        result=bl.cleanup(doc)
        check(sum(r['status']=='moved' for r in result)==2,'Previously blocked references move once all copies are editable')
        check(all(r['occurrences']==4 for r in result if r['parent_id']),'Expanded occurrence counts retained')
        # A child used by two distinct parents shares its own internals, not the two parent reference objects.
        other_parent=f.definition(doc,'OtherTree_01',mid)
        hidden_other=f.instance(doc,other_parent,hidden=True)
        other_mid=nested(doc,other_parent).Id
        set_layer(doc,doc.Objects.FindId(mid_id),0);set_layer(doc,doc.Objects.FindId(leaf_id),0)
        rows=bl.plan_cleanup(doc)
        by_id={r['id']:r for r in rows}
        check(by_id[mid_id]['status']=='move','Independent visible parent reference remains editable')
        check(by_id[other_mid]['status']=='hidden','Independent hidden parent reference skipped')
        check(by_id[leaf_id]['status']=='shared with protected copies','Common child internals protected across distinct parents')
        bl.cleanup(doc)
        check(doc.Objects.FindId(mid_id).Attributes.LayerIndex==b and doc.Objects.FindId(other_mid).Attributes.LayerIndex==0,
              'Only the safe parent reference moves')
        check(doc.Objects.FindId(leaf_id).Attributes.LayerIndex==0,'Cross-parent shared internals remain untouched')
        # A nested source layer also protects all descendants.
        set_layer(doc,doc.Objects.FindId(mid_id),hidden_layer)
        check(next(r for r in bl.plan_cleanup(doc) if r['id']==mid_id)['status']=='hidden','Nested hidden source layer respected')
        set_layer(doc,doc.Objects.FindId(mid_id),b)
        # The preview is invalidated by a newly protected ancestor, even if the child itself did not change.
        doc.Objects.Show(hidden_other,True)
        previous=bl.plan_cleanup(doc,[keys[2]])
        doc.Objects.Hide(hidden_other,True)
        try:
            bl.cleanup(doc,[keys[2]],expected=previous)
            check(False,'Expected stale ancestry refusal')
        except ValueError:
            check(True,'Changed ancestor visibility invalidates preview')
        # Linked references can move inside local parents, but their definitions are traversal boundaries.
        source=Rhino.RhinoDoc.CreateHeadless(None)
        source_path=os.path.join(f.OUT,'phase3-linked-source.3dm')
        try:
            inner=f.definition(source,'ExternalInner_01');f.instance(source,inner)
            opts=Rhino.FileIO.FileWriteOptions();opts.SuppressDialogBoxes=True
            check(source.WriteFile(source_path,opts),'Nested external source saved')
        finally:source.Dispose()
        linked=f.definition(doc,'Linked_01')
        check(doc.InstanceDefinitions.ModifySourceArchive(linked,source_path,
            Rhino.DocObjects.InstanceDefinitionUpdateType.Linked,True),'Real linked definition created')
        host=f.definition(doc,'LocalLinkedHost_01',linked);f.instance(doc,host)
        linked_key=str(doc.InstanceDefinitions[linked].Id)
        linked_id=nested(doc,host).Id
        external_before=[(o.Id,o.Attributes.LayerIndex,o.Geometry.DataCRC(0)) for o in doc.InstanceDefinitions[linked].GetObjects()]
        graph,nodes=bl.instance_graph(doc)
        check(nodes[linked_key]['children']==[], 'Linked contents are not traversed')
        check(not any(r['parent_id']==linked_key for r in graph),'No cleanup rows generated inside linked definition')
        check(len(bl.definition_inventory(doc,[str(doc.InstanceDefinitions[host].Id)],True))==2,
              'Nested assignment stops at linked boundary')
        bl.save_assignments(doc,{linked_key:str(doc.Layers[a].Id)})
        bl.cleanup(doc,[linked_key])
        check(doc.Objects.FindId(linked_id).Attributes.LayerIndex==a,'Linked nested reference itself moves')
        check([(o.Id,o.Attributes.LayerIndex,o.Geometry.DataCRC(0)) for o in doc.InstanceDefinitions[linked].GetObjects()]
              ==external_before,'Linked contents remain exact')
        # Keep construction bounded: Rhino itself expands some nested bounds.
        # The cleanup graph must count repeated occurrences without expanding them.
        deep=f.definition(doc,'Deep_000')
        for i in range(1,13):
            deep=f.definition(doc,'Deep_{0:03}'.format(i),deep)
            objects=list(doc.InstanceDefinitions[deep].GetObjects())
            geometries=List[Rhino.Geometry.GeometryBase]([o.Geometry.Duplicate() for o in objects])
            attrs=List[Rhino.DocObjects.ObjectAttributes]([o.Attributes.Duplicate() for o in objects])
            geometries.Add(objects[-1].Geometry.Duplicate());attrs.Add(objects[-1].Attributes.Duplicate())
            assert doc.InstanceDefinitions.ModifyGeometry(deep,geometries,attrs)
        deep_root=f.instance(doc,deep)
        start=time.monotonic();graph,nodes=bl.instance_graph(doc);elapsed=time.monotonic()-start
        check(len(nodes)<90,'Deep graph visits definitions once without recursion')
        check(any(r['id']==deep_root for r in graph),'Deep root remains reachable')
        check(next(r for r in bl.definition_inventory(doc,include_nested=True) if r['name']=='Deep_000')['count']==2**12,
              'Exponential world occurrence counts computed without expansion')
        check(len(graph)<60,'Repeated hierarchy produces only stored-reference rows')
        check(elapsed<10,'Deep used-definition graph completes promptly')
        # Test depth separately, with one nested reference per level.
        chain=f.definition(doc,'Chain_000')
        for i in range(1,71):
            chain=f.definition(doc,'Chain_{0:03}'.format(i),chain)
        f.instance(doc,chain)
        graph,nodes=bl.instance_graph(doc)
        check(any(n['definition'].Name=='Chain_000' for n in nodes.values()),
              'Seventy-level hierarchy traversed without Python recursion')
        # Save/reopen retains the actual edited nested attributes and nested-only rules.
        path=os.path.join(f.OUT,'phase3-persistence.3dm')
        opts=Rhino.FileIO.FileWriteOptions();opts.SuppressDialogBoxes=True
        check(doc.WriteFile(path,opts),'Nested cleanup saved')
        reopened=Rhino.RhinoDoc.OpenHeadless(path)
        try:
            check(reopened.Objects.FindId(mid_id).Attributes.LayerIndex==b,'Nested layer survives reopen')
            check(bl.read_assignment(reopened.InstanceDefinitions.FindId(Guid(keys[2])))['layer_path']=='Leaves',
                  'Nested-only assignment survives reopen')
            check(next(r for r in bl.plan_cleanup(reopened) if r['id']==leaf_id)['status']=='shared with protected copies',
                  'Reopened protected ancestry remains correct')
        finally:reopened.Dispose()
    finally:
        for dialog in dialogs:dialog.Dispose(True)
        doc.Dispose()
    json.dump(dict(passed=len(checks),checks=checks),open(os.path.join(f.OUT,'phase3-results.json'),'w'),indent=2)
    print('BLOCK LAYERS PHASE 3: {0} checks passed'.format(len(checks)))


if __name__=='__main__':
    run()
