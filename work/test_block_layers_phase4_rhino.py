"""Missing-layer integration checks. Run only inside Rhino through MCP."""
import importlib
import importlib.util
import json
import os
import sys

import Rhino
from System import Guid, Array
from System.Drawing import Color

ROOT=r'C:\Projects\rhino-urbanism'
sys.path.insert(0,ROOT)
import block_layers as bl
import block_layer_ui as panels
importlib.reload(bl);importlib.reload(panels)
spec=importlib.util.spec_from_file_location('missing_fixtures',os.path.join(ROOT,'work','test_block_layers_rhino.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
checks=[]


def check(value,label):
    if not value:raise AssertionError(label)
    checks.append(label)


def missing_rule(doc,index,path):
    raw=json.dumps(dict(version=1,layer_id=str(Guid.NewGuid()),layer_path=path))
    assert doc.InstanceDefinitions[index].SetUserString(bl.ASSIGNMENT_KEY,raw)
    return raw


def live_layers(doc):
    return {str(l.Id) for l in doc.Layers if not l.IsDeleted}


def run():
    doc=Rhino.RhinoDoc.CreateHeadless(None)
    dialogs=[]
    try:
        target=f.layer(doc,'Vehicles')
        layer=doc.Layers[target];layer.Color=Color.Coral;doc.Layers.Modify(layer,target,True)
        target_snapshot=(layer.Color.ToArgb(),layer.IsVisible,layer.IsLocked,layer.ParentLayerId)
        defs={};ids={};raws={}
        for name,path in [('TreeA','Landscape::Trees'),('TreeB','landscape::trees'),
                          ('Parent','Landscape'),('Car','Traffic::Cars'),('Hidden','Protected::Missing')]:
            defs[name]=f.definition(doc,name+'_01')
            ids[name]=f.instance(doc,defs[name],hidden=name=='Hidden')
            raws[name]=missing_rule(doc,defs[name],path)
        f.instance(doc,defs['TreeA'],x=10)
        leaf=f.definition(doc,'Shrub_01')
        parent=f.definition(doc,'Garden_01',leaf)
        f.instance(doc,parent);f.instance(doc,parent,x=20)
        missing_rule(doc,leaf,'Landscape::Shrubs')
        groups=bl.missing_targets(doc)
        by_path={g['key']:g for g in groups}
        check(len(groups)==4,'Missing paths grouped once across definitions and nested references')
        check(len(by_path['landscape::trees']['definitions'])==2,'Case variants share one missing-path decision')
        check(by_path['landscape::trees']['occurrences']==3,'Shared path counts all top-level copies')
        check(by_path['landscape::shrubs']['occurrences']==2,'Missing nested path counts world occurrences')
        check('protected::missing' not in by_path,'Protected-only references do not request layer creation')
        before_layers=live_layers(doc)
        dialog=panels.MissingLayerDialog(doc,groups);dialogs.append(dialog)
        check(not dialog.create_box.Checked,'Creation toggle defaults off')
        check(all(c['mode']=='skip' for c in dialog.decisions().values()),'Default decisions skip missing targets')
        dialog.create_box.Checked=True
        check(all(c['mode']=='create' for c in dialog.decisions().values()),'Creation toggle applies to unresolved paths')
        dialog.Close(False)
        check(live_layers(doc)==before_layers,'Cancel creates no layers')
        check(all(doc.InstanceDefinitions[defs[n]].GetUserString(bl.ASSIGNMENT_KEY)==raws[n] for n in defs),
              'Cancel changes no saved rules')
        dialog=panels.MissingLayerDialog(doc,groups);dialogs.append(dialog)
        parent_row=next(i for i,g in enumerate(groups) if g['key']=='landscape')
        dialog.grid.SelectedRows=Array[int]([parent_row]);dialog.set_choice(dict(mode='skip'))
        dialog.create_box.Checked=True
        check(dialog.decisions()['landscape']['mode']=='skip','Explicit skip survives enabling creation')
        car_row=next(i for i,g in enumerate(groups) if g['key']=='traffic::cars')
        dialog.grid.SelectedRows=Array[int]([car_row])
        dialog.set_choice(dict(mode='existing',target_id=str(doc.Layers[target].Id)))
        check(dialog.decisions()['traffic::cars']['mode']=='existing','Existing mapping survives global creation toggle')
        decisions=dialog.decisions()
        result=bl.resolve_missing_targets(doc,groups,decisions)
        check(len(result['created'])==3,'Only one shared parent and two intended child layers created')
        check(len(result['changed'])==4,'Creation and mapping update all affected definition rules')
        check(result['skipped']==[str(doc.InstanceDefinitions[defs['Parent']].Id)],'Skip result records the affected definition')
        tree_layer=bl.find_target(doc,bl.read_assignment(doc.InstanceDefinitions[defs['TreeA']]))
        shrub_layer=bl.find_target(doc,bl.read_assignment(doc.InstanceDefinitions[leaf]))
        check(tree_layer.ParentLayerId==shrub_layer.ParentLayerId,'Sibling paths reuse the same parent')
        check(tree_layer.Color.ToArgb()==Rhino.DocObjects.Layer().Color.ToArgb()
              and tree_layer.IsVisible and not tree_layer.IsLocked,'Created target uses default layer settings')
        check((doc.Layers[target].Color.ToArgb(),doc.Layers[target].IsVisible,doc.Layers[target].IsLocked,
               doc.Layers[target].ParentLayerId)==target_snapshot,'Existing mapped layer settings unchanged')
        check(doc.Layers.FindByFullPath('Traffic',-1)<0,'Mapping does not create the old intended parent')
        check(doc.Layers.FindByFullPath('Protected',-1)<0,'Hidden-only path never created')
        check(doc.InstanceDefinitions[defs['Parent']].GetUserString(bl.ASSIGNMENT_KEY)==raws['Parent'],
              'Skipped definition keeps its original rule')
        rows=bl.cleanup(doc,excluded_definition_ids=result['skipped'])
        check(doc.Objects.FindId(ids['Parent']).Attributes.LayerIndex==0,
              'Skip holds even when another decision creates its target as a parent')
        check(next(r for r in rows if r['id']==ids['Parent'])['status']=='skipped missing target',
              'Skipped target is clearly reported for this run')
        check(doc.Objects.FindId(ids['Car']).Attributes.LayerIndex==target,'Mapped instance moves to chosen existing layer')
        check(all(doc.Objects.FindId(ids[n]).Attributes.LayerIndex==tree_layer.Index for n in ['TreeA','TreeB']),
              'Both definitions sharing a created path move correctly')
        nested=next(o for o in doc.InstanceDefinitions[parent].GetObjects() if isinstance(o,Rhino.DocObjects.InstanceObject))
        check(nested.Attributes.LayerIndex==shrub_layer.Index,'Missing nested target resolved and cleaned')
        check(doc.Objects.FindId(ids['Hidden']).Attributes.LayerIndex==0,'Hidden copy remains untouched')
        # Reopening a command may use a target created as a parent in the preceding run.
        check(next(r for r in bl.plan_cleanup(doc) if r['id']==ids['Parent'])['status']=='move',
              'Skip affects only the current cleanup run')
        # Existing parent appearance and visibility must be preserved during child creation.
        hidden_parent=f.layer(doc,'HiddenParent',hidden=True)
        index=f.definition(doc,'HiddenTarget_01');obj=f.instance(doc,index)
        missing_rule(doc,index,'HiddenParent::Child')
        scoped=[str(doc.InstanceDefinitions[index].Id)]
        g=bl.missing_targets(doc,scoped)
        r=bl.resolve_missing_targets(doc,g,{g[0]['key']:dict(mode='create')})
        check(len(r['created'])==1,'Existing parent reused during creation')
        check(not doc.Layers[hidden_parent].IsVisible,'Hidden parent is never unhidden')
        check(next(r for r in bl.plan_cleanup(doc,scoped) if r['id']==obj)['status']=='target hidden',
              'Created child under hidden parent does not cause an instance move')
        # A failed assignment save must roll back every newly created prefix.
        failing=f.definition(doc,'Failure_01');f.instance(doc,failing)
        raw=missing_rule(doc,failing,'RollbackParent::Child')
        scope=[str(doc.InstanceDefinitions[failing].Id)];g=bl.missing_targets(doc,scope)
        original_save=bl.save_assignments
        def fail(*a,**k):raise RuntimeError('Simulated assignment save failure')
        try:
            bl.save_assignments=fail
            try:
                bl.resolve_missing_targets(doc,g,{g[0]['key']:dict(mode='create')})
                check(False,'Expected injected failure')
            except RuntimeError:
                check(doc.Layers.FindByFullPath('RollbackParent',-1)<0,'Failed resolution rolls back new parent layers')
                check(doc.InstanceDefinitions[failing].GetUserString(bl.ASSIGNMENT_KEY)==raw,'Failed resolution preserves original rule')
        finally:bl.save_assignments=original_save
        # Invalid paths are rejected before a mixed batch writes anything.
        bad=f.definition(doc,'InvalidPath_01');f.instance(doc,bad)
        missing_rule(doc,bad,'Bad::::Path')
        groups_bad=bl.missing_targets(doc,scope+[str(doc.InstanceDefinitions[bad].Id)])
        layers_before=live_layers(doc)
        try:
            bl.resolve_missing_targets(doc,groups_bad,{g['key']:dict(mode='create') for g in groups_bad})
            check(False,'Expected invalid path refusal')
        except ValueError:
            check(live_layers(doc)==layers_before,'Invalid create path rejects entire batch without layer changes')
        # A deleted replacement and a concurrently appearing target invalidate the review.
        gone=f.layer(doc,'DeletedReplacement')
        choices={g['key']:dict(mode='existing',target_id=str(doc.Layers[gone].Id)) for g in groups_bad}
        doc.Layers.Delete(gone,True)
        try:
            bl.resolve_missing_targets(doc,groups_bad,choices)
            check(False,'Expected deleted replacement refusal')
        except ValueError:check(True,'Deleted replacement layer rejected')
        f.layer(doc,'RollbackParent')
        fresh=bl.missing_targets(doc,scope)
        f.layer(doc,'Child',doc.Layers.FindByFullPath('RollbackParent',-1))
        try:
            bl.resolve_missing_targets(doc,fresh,{fresh[0]['key']:dict(mode='create')})
            check(False,'Expected stale review refusal')
        except ValueError:check(True,'Concurrently created target invalidates review')
        # Refreshing the review reconciles changed missing paths without guessing.
        stale=panels.MissingLayerDialog(doc,groups_bad,scope);dialogs.append(stale)
        stale.refresh_groups()
        check(not stale.groups,'Refresh removes targets that now exist')
        # Preview prevents cleanup until each missing path is resolved or skipped.
        preview=panels.CleanupPreview(doc,[str(doc.InstanceDefinitions[bad].Id)]);dialogs.append(preview)
        check(preview.resolve_button.Visible and not preview.apply_button.Enabled,
              'Preview exposes resolution and blocks unresolved cleanup')
        group=bl.missing_targets(doc,[str(doc.InstanceDefinitions[bad].Id)])
        resolved=bl.resolve_missing_targets(doc,group,{group[0]['key']:dict(mode='existing',target_id=str(doc.Layers[target].Id))})
        preview.refresh_preview()
        check(not preview.resolve_button.Visible and preview.apply_button.Enabled,'Resolved preview enables Apply')
        # Explicit skips remain skips after preview refresh.
        preview.excluded_ids.add(str(doc.InstanceDefinitions[bad].Id));preview.refresh_preview()
        check(preview.rows[0]['status']=='skipped missing target' and not preview.apply_button.Enabled,
              'Preview remembers skip decisions through refresh')
        # Persistence stores the created layer IDs rather than only a fallback path.
        path=os.path.join(f.OUT,'phase4-persistence.3dm')
        opts=Rhino.FileIO.FileWriteOptions();opts.SuppressDialogBoxes=True
        check(doc.WriteFile(path,opts),'Resolved targets and assignments saved')
        reopened=Rhino.RhinoDoc.OpenHeadless(path)
        try:
            definition=reopened.InstanceDefinitions.FindId(doc.InstanceDefinitions[defs['TreeA']].Id)
            assignment=bl.read_assignment(definition)
            check(reopened.Layers.FindId(Guid(assignment['layer_id'])).FullPath.casefold()=='landscape::trees',
                  'Created layer ID survives save and reopen')
        finally:reopened.Dispose()
    finally:
        for dlg in dialogs:dlg.Dispose(True)
        doc.Dispose()
    json.dump(dict(passed=len(checks),checks=checks),open(os.path.join(f.OUT,'phase4-results.json'),'w'),indent=2)
    print('BLOCK LAYERS PHASE 4: {0} checks passed'.format(len(checks)))


if __name__=='__main__':run()
