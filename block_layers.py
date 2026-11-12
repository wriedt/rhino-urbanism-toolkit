#! python 3
# -*- coding: utf-8 -*-
"""Definition home-layer rules and reviewed instance movements. Rhino 8.9+."""
import json
from collections import Counter, deque

import Rhino
import scriptcontext as sc
from System import Guid


ASSIGNMENT_KEY = 'Urbanism.BlockLayer'


def read_assignment(definition):
    """None means unassigned; malformed/unsupported data must never be guessed."""
    raw = definition.GetUserString(ASSIGNMENT_KEY)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if (not isinstance(value, dict) or value.get('version') != 1
                or not isinstance(value.get('layer_path'), str)
                or not value['layer_path'].strip()
                or not isinstance(value.get('layer_id'), str)):
            raise ValueError()
        try:
            Guid(value['layer_id'])
        except Exception:
            raise ValueError('Invalid layer ID')
        return value
    except (ValueError, TypeError):
        raise ValueError('Invalid or unsupported saved layer assignment.')


def find_target(doc, assignment):
    """Prefer identity (survives renaming); full path is the transfer fallback."""
    layer = doc.Layers.FindId(Guid(assignment['layer_id']))
    if layer is not None and not layer.IsDeleted:
        return layer
    index = doc.Layers.FindByFullPath(assignment['layer_path'], -1)
    return doc.Layers[index] if index >= 0 else None


def layer_barrier(doc, layer):
    """Walk ancestors explicitly: a visible child can have a hidden parent."""
    seen = set()
    hidden, locked = False, False
    while layer is not None and not layer.IsDeleted:
        if layer.Id in seen:
            return 'invalid layer hierarchy'
        seen.add(layer.Id)
        hidden = hidden or not layer.IsVisible
        locked = locked or layer.IsLocked
        if layer.ParentLayerId == Guid.Empty:
            break
        layer = doc.Layers.FindId(layer.ParentLayerId)
    if hidden:
        return 'hidden'
    if locked:
        return 'locked'
    return None


def instance_barrier(doc, obj):
    if obj.IsHidden:
        return 'hidden'
    if obj.IsLocked:
        return 'locked'
    barrier = layer_barrier(doc, doc.Layers[obj.Attributes.LayerIndex])
    if barrier:
        return barrier
    if obj.IsReference:
        return 'reference object'
    return None


def _restore_assignments(sender, event):
    doc = event.Document
    inverse = []
    for definition_id, raw in event.Tag:
        definition = doc.InstanceDefinitions.FindId(Guid(definition_id))
        if definition is not None and not definition.IsDeleted:
            inverse.append((definition_id, definition.GetUserString(ASSIGNMENT_KEY)))
    doc.AddCustomUndoEvent('Block layer assignments', _restore_assignments, inverse)
    for definition_id, raw in event.Tag:
        definition = doc.InstanceDefinitions.FindId(Guid(definition_id))
        if definition is not None and not definition.IsDeleted:
            if not definition.SetUserString(ASSIGNMENT_KEY, raw):
                Rhino.RhinoApp.WriteLine('Could not restore assignment for ' + definition.Name)
    doc.Modified = True


def save_assignments(doc, changes, expected=None):
    """Batch rules by definition ID -> layer ID (None removes); atomic with Undo.

    expected contains original raw rule strings to reject edits from a stale list.
    No instances move. Local unused definitions can also receive rules.
    """
    planned = []
    for key, target_id in changes.items():
        definition = doc.InstanceDefinitions.FindId(Guid(key))
        if definition is None or definition.IsDeleted or not contents_are_local(definition):
            raise ValueError('Choose an existing local block definition. Linked/reference definitions are skipped.')
        before = definition.GetUserString(ASSIGNMENT_KEY)
        if expected is not None and (key not in expected or before != expected[key]):
            raise ValueError('An assignment changed since the list opened. Reopen it before saving.')
        raw = None
        if target_id is not None:
            layer = doc.Layers.FindId(Guid(target_id))
            if layer is None or layer.IsDeleted or layer.IsReference:
                raise ValueError('A target layer is no longer available. Choose an existing local layer.')
            raw = json.dumps(dict(version=1, layer_id=str(layer.Id),
                                 layer_path=layer.FullPath), sort_keys=True)
        if raw != before:
            planned.append((key, before, raw))
    if not planned:
        return []
    undo = doc.BeginUndoRecord('Assign block layers')
    changed = []
    try:
        if not doc.AddCustomUndoEvent('Block layer assignments', _restore_assignments,
                                      [(key, before) for key, before, raw in planned]):
            raise RuntimeError('Could not register assignment Undo; nothing changed.')
        for key, before, raw in planned:
            definition = doc.InstanceDefinitions.FindId(Guid(key))
            if not definition.SetUserString(ASSIGNMENT_KEY, raw):
                raise RuntimeError('Could not save assignment for ' + definition.Name)
            changed.append((key, before))
        doc.Modified = True
    except Exception:
        failures = []
        for key, before in reversed(changed):
            if not doc.InstanceDefinitions.FindId(Guid(key)).SetUserString(ASSIGNMENT_KEY, before):
                failures.append(key)
        if failures:
            Rhino.RhinoApp.WriteLine('Assignment rollback incomplete; use Undo. ' + ', '.join(failures))
        raise
    finally:
        if undo:
            doc.EndUndoRecord(undo)
    return [key for key, before, raw in planned]


def top_level_instances(doc):
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.ObjectTypeFilter = Rhino.DocObjects.ObjectType.InstanceReference
    settings.NormalObjects = True
    settings.HiddenObjects = True
    settings.LockedObjects = True
    settings.ReferenceObjects = True
    settings.IdefObjects = False
    settings.DeletedObjects = False
    return doc.Objects.GetObjectList(settings)


def contents_are_local(definition):
    return (not definition.IsReference and definition.UpdateType ==
            Rhino.DocObjects.InstanceDefinitionUpdateType.Static)


def instance_graph(doc):
    """Visit each used definition once, then propagate occurrence counts on its DAG.

    Never opens linked contents or unused definitions. Protected ancestry is
    propagated even when that ancestor's own rule is unassigned or out of scope.
    No recursive expansion into every world-space copy is needed.
    """
    roots = list(top_level_instances(doc))
    nodes = {}
    queue = deque(o.InstanceDefinition for o in roots)
    while queue:
        if sc.escape_test(False):
            raise RuntimeError('Cleanup cancelled; nothing changed.')
        definition = queue.popleft()
        key = str(definition.Id)
        if key in nodes:
            continue
        children = ([o for o in definition.GetObjects()
                     if isinstance(o, Rhino.DocObjects.InstanceObject) and not o.IsDeleted]
                    if contents_are_local(definition) else [])
        nodes[key] = dict(definition=definition, children=children,
                          contexts=Counter(), incoming=0)
        queue.extend(o.InstanceDefinition for o in children)
    for node in nodes.values():
        for child in node['children']:
            nodes[str(child.InstanceDefinition.Id)]['incoming'] += 1
    rows = []
    for obj in roots:
        reason = instance_barrier(doc, obj)
        nodes[str(obj.InstanceDefinition.Id)]['contexts'][reason or 'eligible'] += 1
        rows.append(dict(id=obj.Id, definition_id=str(obj.InstanceDefinition.Id),
            parent_id=None, parent_name='', occurrences=1, eligible=0 if reason else 1,
            protection={reason: 1} if reason else {}))
    ready = deque(k for k, node in nodes.items() if node['incoming'] == 0)
    processed = set()
    while ready:
        if sc.escape_test(False):
            raise RuntimeError('Cleanup cancelled; nothing changed.')
        key = ready.popleft()
        processed.add(key)
        node = nodes[key]
        for obj in node['children']:
            reason = instance_barrier(doc, obj)
            contexts = Counter()
            for inherited, count in node['contexts'].items():
                contexts[reason if inherited == 'eligible' and reason else inherited] += count
            protection = {r: n for r, n in contexts.items() if r != 'eligible' and n}
            child_key = str(obj.InstanceDefinition.Id)
            rows.append(dict(id=obj.Id, definition_id=child_key,
                parent_id=key, parent_name=node['definition'].Name,
                occurrences=sum(contexts.values()), eligible=contexts['eligible'],
                protection=protection))
            child_node = nodes[child_key]
            child_node['contexts'].update(contexts)
            child_node['incoming'] -= 1
            if child_node['incoming'] == 0:
                ready.append(child_key)
    # Rhino normally disallows cycles. Treat malformed cyclic imports conservatively.
    for key in nodes.keys() - processed:
        for obj in nodes[key]['children']:
            rows.append(dict(id=obj.Id, definition_id=str(obj.InstanceDefinition.Id),
                parent_id=key, parent_name=nodes[key]['definition'].Name,
                occurrences=0, eligible=0, protection={'cyclic nesting': 1}))
    return rows, nodes


def plan_cleanup(doc, definition_ids=None, include_nested=True, excluded_definition_ids=(),
                 assignment_overrides=None):
    """Plan edits to references, skipping a shared edit if any occurrence is protected."""
    sc.escape_test(False, True)
    rows = []
    excluded = set(str(i) for i in excluded_definition_ids)
    wanted = set(str(i) for i in definition_ids) if definition_ids is not None else None
    if include_nested:
        references, _ = instance_graph(doc)
    else:
        references = [dict(id=o.Id, definition_id=str(o.InstanceDefinition.Id),
            parent_id=None, parent_name='', occurrences=1, eligible=0 if instance_barrier(doc, o) else 1,
            protection={instance_barrier(doc, o): 1} if instance_barrier(doc, o) else {})
            for o in top_level_instances(doc)]
    for reference in references:
        if wanted is not None and reference['definition_id'] not in wanted:
            continue
        if sc.escape_test(False):
            raise RuntimeError('Cleanup cancelled; nothing changed.')
        obj = doc.Objects.FindId(reference['id'])
        row = dict(reference, block=obj.InstanceDefinition.Name,
            before=obj.Attributes.LayerIndex, target=None,
            source_path=doc.Layers[obj.Attributes.LayerIndex].FullPath)
        rows.append(row)
        if not contents_are_local(obj.InstanceDefinition):
            row['status'] = 'linked/reference block'
            continue
        try:
            assignment = (assignment_overrides[reference['definition_id']]
                          if assignment_overrides is not None and reference['definition_id'] in assignment_overrides
                          else read_assignment(obj.InstanceDefinition))
        except ValueError:
            row['status'] = 'invalid assignment'
            continue
        if assignment is None:
            row['status'] = 'unassigned'
            continue
        row['saved_path'] = assignment['layer_path']
        if row['definition_id'] in excluded:
            row['status'] = 'skipped missing target'
            continue
        protection = row['protection']
        barrier = ('shared with protected copies' if protection and row['eligible']
                   else ', '.join(sorted(protection)))
        if barrier:
            row['status'] = barrier
            continue
        target = find_target(doc, assignment)
        if target is None:
            row['status'] = 'missing target layer'
            continue
        row['target'] = target.Index
        row['target_id'] = str(target.Id)
        row['target_path'] = target.FullPath
        if target.IsReference:
            row['status'] = 'reference target layer'
        elif target.Index == row['before']:
            row['status'] = 'already correct'
        else:
            barrier = layer_barrier(doc, target)
            row['status'] = 'target ' + barrier if barrier else 'move'
    return rows


def preview_signature(rows):
    return sorted((str(r['id']), r['definition_id'], r['status'], r['before'],
                   r['source_path'], r.get('target_id'), r.get('target_path'),
                   r.get('saved_path'), r['parent_id'], r['occurrences'],
                   r['eligible'], tuple(sorted(r['protection'].items()))) for r in rows)


def cleanup(doc, definition_ids=None, expected=None, include_nested=True, excluded_definition_ids=()):
    """Preflight then change only instance LayerIndex, with one Undo and rollback."""
    rows = plan_cleanup(doc, definition_ids, include_nested=include_nested,
                        excluded_definition_ids=excluded_definition_ids)
    if expected is not None and preview_signature(rows) != preview_signature(expected):
        raise ValueError('The model changed. Refresh the preview before applying cleanup.')
    moves = [r for r in rows if r['status'] == 'move']
    if not moves:
        return rows
    undo = doc.BeginUndoRecord('Apply block home layers')
    redraw = doc.Views.RedrawEnabled
    changed = []
    try:
        doc.Views.RedrawEnabled = False
        for row in moves:
            if sc.escape_test(False):
                raise RuntimeError('Cleanup cancelled; layer moves rolled back.')
            obj = doc.Objects.FindId(row['id'])
            if (obj is None or obj.Attributes.LayerIndex != row['before']
                    or instance_barrier(doc, obj)):
                raise RuntimeError('An instance changed during cleanup; layer moves rolled back.')
            target = doc.Layers[row['target']]
            if target.IsDeleted or target.IsReference or layer_barrier(doc, target):
                raise RuntimeError('A target layer changed during cleanup; layer moves rolled back.')
            before = obj.Attributes.Duplicate()
            attributes = before.Duplicate()
            attributes.LayerIndex = row['target']
            if not doc.Objects.ModifyAttributes(obj, attributes, True):
                raise RuntimeError('Could not move ' + row['block'] + '; layer moves rolled back.')
            changed.append((row['id'], before))
            row['status'] = 'moved'
    except Exception:
        failed = [str(object_id) for object_id, attrs in reversed(changed)
                  if not doc.Objects.ModifyAttributes(object_id, attrs, True)]
        if failed:
            Rhino.RhinoApp.WriteLine('Rollback incomplete. Use Undo. Objects: ' + ', '.join(failed))
        raise
    finally:
        doc.Views.RedrawEnabled = redraw
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.Redraw()
    return rows
