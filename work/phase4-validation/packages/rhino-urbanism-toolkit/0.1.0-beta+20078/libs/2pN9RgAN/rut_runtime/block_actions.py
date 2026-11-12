"""Small, transactional Rhino document actions for the focused block commands."""
import uuid
import Rhino
from System.Collections.Generic import List
import block_versions as naming


def read_definitions(doc):
    return [dict(index=d.Index, id=str(d.Id), name=d.Name,
                 editable=not d.IsReference and d.UpdateType ==
                 Rhino.DocObjects.InstanceDefinitionUpdateType.Static)
            for d in doc.InstanceDefinitions if not d.IsDeleted]


def _temporary_names(doc, rows):
    return ['RUT_Temporary_' + uuid.uuid4().hex for row in rows]


def _rename(doc, row, name):
    definition = doc.InstanceDefinitions[row['index']]
    if definition.IsDeleted or str(definition.Id) != row['id']:
        raise ValueError('A definition changed. Reopen the command.')
    if not doc.InstanceDefinitions.Modify(definition, name, definition.Description,
                                         definition.Url or '', definition.UrlDescription or '', True):
        raise RuntimeError('Could not rename ' + row['old'])


def _validate(doc, rows, snapshot):
    definitions = read_definitions(doc)
    if naming.fingerprint(definitions) != snapshot:
        raise ValueError('Block definitions changed. Reopen the command to review again.')
    naming.validate_targets(definitions, rows)
    for row in rows:
        if not Rhino.DocObjects.ModelComponent.IsValidComponentName(row['new']):
            raise ValueError('Invalid block name: ' + row['new'])


def _restore_names(doc, touched):
    failures = []
    for row, temporary in zip(touched, _temporary_names(doc, touched)):
        try:
            _rename(doc, row, temporary)
        except Exception as error:
            failures.append(str(error))
    for row in touched:
        try:
            _rename(doc, row, row['old'])
        except Exception as error:
            failures.append(str(error))
    return failures


def apply_names(doc, plan):
    rows = plan['renames']
    _validate(doc, rows, plan['snapshot'])
    if not rows:
        return 0
    undo = doc.BeginUndoRecord('Rename block family' if plan['operation'] == 'rename'
                               else 'Consolidate block versions')
    redraw, touched = doc.Views.RedrawEnabled, []
    try:
        doc.Views.RedrawEnabled = False
        for row, temporary in zip(rows, _temporary_names(doc, rows)):
            _rename(doc, row, temporary)
            touched.append(row)
        for row in rows:
            _rename(doc, row, row['new'])
        return len(rows)
    except Exception as error:
        failures = _restore_names(doc, touched)
        if failures:
            raise RuntimeError(str(error) + ' Restoration incomplete; use Undo. ' + '; '.join(failures)) from error
        raise
    finally:
        doc.Views.RedrawEnabled = redraw
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.Redraw()


def editable_instance(doc, obj):
    import block_layers
    return (isinstance(obj, Rhino.DocObjects.InstanceObject) and not obj.IsDeleted
            and not obj.IsInstanceDefinitionGeometry and not block_layers.instance_barrier(doc, obj)
            and block_layers.contents_are_local(obj.InstanceDefinition))


def instance_stamp(obj):
    return (str(obj.Id), str(obj.InstanceDefinition.Id), str(obj.InstanceXform),
            obj.Attributes.ToJSON(Rhino.FileIO.SerializationOptions()))


def version_plan(doc, ids, spec, baseline=None, reserved=()):
    objects = [doc.Objects.FindId(i) for i in ids]
    if not objects or any(not editable_instance(doc, obj) for obj in objects):
        raise ValueError('Select visible, unlocked, local top-level block instances.')
    source = objects[0].InstanceDefinition
    if any(obj.InstanceDefinition.Id != source.Id for obj in objects):
        raise ValueError('Select copies of one definition at a time.')
    definitions = read_definitions(doc)
    snapshot = naming.fingerprint(definitions)
    rows = []
    if baseline:
        row = dict(index=source.Index, id=str(source.Id), old=source.Name, new=baseline)
        rows.append(row)
        naming.validate_targets(definitions, rows)
        definitions = [dict(d, name=baseline) if d['id'] == str(source.Id) else d for d in definitions]
    family = naming.members(definitions, spec)
    if not any(d['id'] == str(source.Id) for d in family):
        raise ValueError('The chosen version part does not match the selected block.')
    name = naming.next_version(definitions, spec, reserved)
    if not Rhino.DocObjects.ModelComponent.IsValidComponentName(name):
        raise ValueError('Invalid version name: ' + name)
    return dict(source_index=source.Index, source_id=str(source.Id), original_name=source.Name,
                new_name=name, ids=list(ids), stamps=[instance_stamp(o) for o in objects],
                snapshot=snapshot, renames=rows)


def apply_versions(doc, plans):
    if not plans:
        return []
    snapshot = naming.fingerprint(read_definitions(doc))
    rows = [r for p in plans for r in p['renames']]
    if any(p['snapshot'] != snapshot for p in plans):
        raise ValueError('Definitions changed. Reopen the command.')
    _validate(doc, rows, snapshot)
    occupied = {r['new'].casefold() for r in rows}
    renamed = {r['id'] for r in rows}
    occupied.update(d['name'].casefold() for d in read_definitions(doc) if d['id'] not in renamed)
    for plan in plans:
        if plan['new_name'].casefold() in occupied:
            raise ValueError('The proposed version name is occupied.')
        occupied.add(plan['new_name'].casefold())
        for object_id, stamp in zip(plan['ids'], plan['stamps']):
            obj = doc.Objects.FindId(object_id)
            if not editable_instance(doc, obj) or instance_stamp(obj) != stamp:
                raise ValueError('A selected copy changed. Reopen the command.')
    undo = doc.BeginUndoRecord('Create block version')
    redraw, created, switched, touched = doc.Views.RedrawEnabled, [], [], []
    try:
        doc.Views.RedrawEnabled = False
        for row, temporary in zip(rows, _temporary_names(doc, rows)):
            _rename(doc, row, temporary)
            touched.append(row)
        for row in rows:
            _rename(doc, row, row['new'])
        for plan in plans:
            source = doc.InstanceDefinitions[plan['source_index']]
            geometry = List[Rhino.Geometry.GeometryBase]()
            attributes = List[Rhino.DocObjects.ObjectAttributes]()
            for obj in source.GetObjects():
                geometry.Add(obj.Geometry.Duplicate())
                attributes.Add(obj.Attributes.Duplicate())
            index = doc.InstanceDefinitions.Add(plan['new_name'], source.Description,
                source.Url or '', source.UrlDescription or '', Rhino.Geometry.Point3d.Origin,
                geometry, attributes)
            if index < 0:
                raise RuntimeError('Could not create ' + plan['new_name'])
            created.append(index)
            strings = source.GetUserStrings()
            if strings:
                for key in strings.AllKeys:
                    if not doc.InstanceDefinitions[index].SetUserString(key, strings[key]):
                        raise RuntimeError('Could not copy definition metadata.')
            for object_id in plan['ids']:
                if not doc.Objects.ReplaceInstanceObject(object_id, index):
                    raise RuntimeError('Could not switch a selected copy.')
                switched.append((object_id, source.Index))
        return [p['new_name'] for p in plans]
    except Exception as error:
        failures = []
        for object_id, index in reversed(switched):
            if not doc.Objects.ReplaceInstanceObject(object_id, index):
                failures.append('instance restoration')
        for index in reversed(created):
            if not doc.InstanceDefinitions.Delete(index, True, True):
                failures.append('definition removal')
        failures.extend(_restore_names(doc, touched))
        if failures:
            raise RuntimeError(str(error) + ' Restoration incomplete; use Undo. ' + '; '.join(failures)) from error
        raise
    finally:
        doc.Views.RedrawEnabled = redraw
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.Redraw()
