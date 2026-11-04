"""Phase 2 integration checks. Run inside Rhino 8, not system Python."""
import importlib.util
import importlib
import json
import os
import sys

import Rhino
from System import Guid

ROOT = r'C:\Projects\rhino-urbanism'
sys.path.insert(0, ROOT)
import block_layers as bl
import block_layer_ui as panels
importlib.reload(bl)
importlib.reload(panels)
spec = importlib.util.spec_from_file_location('bl_fixtures', os.path.join(ROOT,'work','test_block_layers_rhino.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
checks = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def run():
    doc = Rhino.RhinoDoc.CreateHeadless(None)
    dialogs = []
    try:
        target = fixtures.layer(doc, 'Target')
        other = fixtures.layer(doc, 'Other')
        definitions = [fixtures.definition(doc, name) for name in ['A_01','B_01','Outside_01','Protected_01']]
        a, b, outside, protected = [fixtures.instance(doc,i) for i in definitions]
        extra = fixtures.instance(doc, definitions[0], x=20)
        hidden = fixtures.instance(doc, definitions[0], hidden=True)
        locked = fixtures.instance(doc, definitions[3], locked=True)
        doc.Objects.Delete(protected, True)
        unused = fixtures.definition(doc, 'Unused_01')
        keys = [str(doc.InstanceDefinitions[i].Id) for i in definitions]
        target_id, other_id = str(doc.Layers[target].Id), str(doc.Layers[other].Id)
        inventory = bl.definition_inventory(doc)
        check(len(inventory)==4, 'Only used top-level definitions listed')
        check(next(r for r in inventory if r['id']==keys[0])['count']==3, 'Shared definition counted once')
        check(next(r for r in inventory if r['id']==keys[0])['editable']==2, 'Hidden copies excluded from editable count')
        check(next(r for r in inventory if r['id']==keys[3])['editable']==0, 'Protected-only row is read-only')
        d = panels.AssignmentDialog(doc, keys[:2]);dialogs.append(d)
        check(len(d.records)==2 and len(d.selected_keys())==2, 'Selected definitions initially selected in editor')
        d.stage_layer(target_id)
        check(len(d.pending)==2, 'One action stages several definitions')
        check(all(bl.read_assignment(doc.InstanceDefinitions[i]) is None for i in definitions), 'Staging never mutates model')
        d.search.Text='B_'
        check(len(d.visible_records)==1 and len(d.pending)==2, 'Filtering retains offscreen pending changes')
        d.search.Text=''
        d.grid.SelectAll();d.revert_selected()
        check(not d.pending and not d.save_button.Enabled, 'Revert clears staged changes')
        d.stage_layer(target_id)
        d.Close(False)
        check(all(bl.read_assignment(doc.InstanceDefinitions[i]) is None for i in definitions), 'Cancel discards unsaved edits')
        expected = {k: None for k in keys[:2]}
        changed = bl.save_assignments(doc, {k:target_id for k in keys[:2]}, expected)
        check(set(changed)==set(keys[:2]), 'Bulk save writes distinct definitions')
        check(doc.Objects.FindId(a).Attributes.LayerIndex==0, 'Bulk save does not move copies')
        check(bl.read_assignment(doc.InstanceDefinitions[definitions[2]]) is None, 'Unselected definition unchanged')
        check(bl.save_assignments(doc,{k:target_id for k in keys[:2]})==[], 'Repeated bulk save is a no-op')
        try:
            bl.save_assignments(doc,{keys[0]:other_id},expected={keys[0]:None})
            check(False,'Expected stale assignment rejection')
        except ValueError:
            check(True,'Stale assignment edits rejected')
        before = doc.InstanceDefinitions[definitions[0]].GetUserString(bl.ASSIGNMENT_KEY)
        try:
            bl.save_assignments(doc,{keys[0]:other_id,keys[1]:str(Guid.NewGuid())})
            check(False,'Expected invalid target rejection')
        except ValueError:
            check(doc.InstanceDefinitions[definitions[0]].GetUserString(bl.ASSIGNMENT_KEY)==before,
                  'Bad target rejects entire batch before writing')
        try:
            bl.save_assignments(doc,{keys[3]:target_id})
            check(False,'Expected protected-only rejection')
        except ValueError:
            check(True,'Protected-only definition cannot be edited')
        bl.save_assignments(doc,{keys[2]:other_id})
        preview = panels.CleanupPreview(doc,keys[:2]);dialogs.append(preview)
        check(len(preview.rows)==4,'Preview includes copies outside initial selection')
        check(sum(r['status']=='move' for r in preview.rows)==3,'Preview counts all eligible moves')
        check(sum(r['status']=='hidden' for r in preview.rows)==1,'Preview explicitly reports hidden skips')
        check(all(r['definition_id']!=keys[2] for r in preview.rows),'Preview excludes unrelated assigned definitions')
        preview.Close(False)
        check(doc.Objects.FindId(a).Attributes.LayerIndex==0,'Cancel preview does not move instances')
        check(bl.read_assignment(doc.InstanceDefinitions[definitions[0]]) is not None,'Cancel preview keeps saved assignments')
        stale = bl.plan_cleanup(doc,keys[:2])
        bl.save_assignments(doc,{keys[0]:other_id})
        try:
            bl.cleanup(doc,keys[:2],expected=stale)
            check(False,'Expected stale preview rejection')
        except ValueError:
            check(doc.Objects.FindId(b).Attributes.LayerIndex==0,'Stale preview rejected without partial moves')
        refreshed = bl.plan_cleanup(doc, keys[:2])
        applied=bl.cleanup(doc,keys[:2],expected=refreshed)
        check(sum(r['status']=='moved' for r in applied)==3,'Scoped preview applies its three moves')
        check(doc.Objects.FindId(a).Attributes.LayerIndex==other,'Reassigned target honored')
        check(doc.Objects.FindId(extra).Attributes.LayerIndex==other,'Extra copy follows definition')
        check(doc.Objects.FindId(b).Attributes.LayerIndex==target,'Different targets supported in same batch')
        check(doc.Objects.FindId(outside).Attributes.LayerIndex==0,'Apply now leaves unrelated definitions alone')
        check(doc.Objects.FindId(hidden).Attributes.LayerIndex==0,'Hidden copy remains untouched')
        bl.save_assignments(doc,{keys[0]:None,keys[1]:None})
        check(all(bl.read_assignment(doc.InstanceDefinitions[i]) is None for i in definitions[:2]),'Bulk removal clears assignments')
        check(doc.Objects.FindId(a).Attributes.LayerIndex==other,'Removal does not move instances')
        # A changed source layer also invalidates a previously shown preview.
        bl.save_assignments(doc,{keys[0]:target_id})
        previous=bl.plan_cleanup(doc,[keys[0]])
        attr=doc.Objects.FindId(a).Attributes.Duplicate();attr.LayerIndex=0
        doc.Objects.ModifyAttributes(a,attr,True)
        try:
            bl.cleanup(doc,[keys[0]],expected=previous)
            check(False,'Expected source change rejection')
        except ValueError:
            check(True,'Changed instance layer invalidates preview')
        # Unsupported metadata is visible and can be explicitly replaced or removed.
        doc.InstanceDefinitions[definitions[1]].SetUserString(bl.ASSIGNMENT_KEY,'broken')
        repair=panels.AssignmentDialog(doc,[keys[1]]);dialogs.append(repair)
        check(repair.describe(repair.records[0])[1]=='Needs assignment','Broken metadata flagged in editor')
        repair.stage_layer(None);repair.save()
        check(bl.read_assignment(doc.InstanceDefinitions[definitions[1]]) is None,'Explicit removal repairs broken metadata')
        # Save followed by preview cancellation is intentional and persistent.
        save=panels.AssignmentDialog(doc,keys[:2]);dialogs.append(save)
        save.stage_layer(other_id);save.apply_box.Checked=True;save.save()
        check(save.Result and save.apply_requested,'Editor Save honors Apply now choice')
        check(keys[1] in save.changed_ids,'Editor reports changed definition IDs')
        path=os.path.join(fixtures.OUT,'phase2-persistence.3dm')
        opts=Rhino.FileIO.FileWriteOptions();opts.SuppressDialogBoxes=True
        check(doc.WriteFile(path,opts),'Phase 2 assignments saved')
        reopened=Rhino.RhinoDoc.OpenHeadless(path)
        try:
            check(all(bl.read_assignment(reopened.InstanceDefinitions.FindId(Guid(k)))['layer_path']=='Other'
                      for k in keys[:2]),'Bulk assignments survive reopening')
        finally:
            reopened.Dispose()
    finally:
        for dialog in dialogs:
            dialog.Dispose(True)
        doc.Dispose()
    with open(os.path.join(fixtures.OUT,'phase2-results.json'),'w') as stream:
        json.dump(dict(passed=len(checks),checks=checks),stream,indent=2)
    print('BLOCK LAYERS PHASE 2: {0} checks passed'.format(len(checks)))


if __name__=='__main__':
    run()
