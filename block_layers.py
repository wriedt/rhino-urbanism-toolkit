#! python 3
# -*- coding: utf-8 -*-
"""Shared block-layer assignment and cleanup. Run inside Rhino 8.9+."""
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


def _restore_assignment(sender, event):
    """Rhino does not record definition user strings automatically for Undo."""
    definition_id, restore = event.Tag
    doc = event.Document
    definition = doc.InstanceDefinitions.FindId(definition_id)
    if definition is None or definition.IsDeleted:
        return
    current = definition.GetUserString(ASSIGNMENT_KEY)
    doc.AddCustomUndoEvent('Block layer assignment', _restore_assignment,
                           (definition_id, current))
    if not definition.SetUserString(ASSIGNMENT_KEY, restore):
        Rhino.RhinoApp.WriteLine('Could not restore block layer assignment for ' + definition.Name)
    doc.Modified = True


def assign_layer(doc, instance_id, layer_index):
    """Assign one definition, without moving instances or changing the description."""
    obj = doc.Objects.FindId(instance_id)
    if (not isinstance(obj, Rhino.DocObjects.InstanceObject)
            or obj.IsInstanceDefinitionGeometry or obj.IsDeleted):
        raise ValueError('Select a top-level block instance.')
    barrier = instance_barrier(doc, obj)
    if barrier:
        raise ValueError('Cannot assign from a ' + barrier + ' instance.')
    layer = doc.Layers[layer_index] if 0 <= layer_index < doc.Layers.Count else None
    if layer is None or layer.IsDeleted or layer.IsReference:
        raise ValueError('Choose an existing local layer.')
    return bool(save_assignments(doc, {str(obj.InstanceDefinition.Id): str(layer.Id)}))


def definition_inventory(doc, definition_ids=None, include_nested=False):
    """Count used definitions and occurrences, optionally exposing nested rules."""
    wanted = set(str(i) for i in definition_ids) if definition_ids is not None else None
    if include_nested:
        sc.escape_test(False, True)
        rows, nodes = instance_graph(doc)
        if wanted is not None:
            pending = deque(wanted)
            while pending:
                key = pending.popleft()
                for child in nodes.get(key, {}).get('children', []):
                    child_key = str(child.InstanceDefinition.Id)
                    if child_key not in wanted:
                        wanted.add(child_key)
                        pending.append(child_key)
    else:
        rows = [dict(id=o.Id, definition_id=str(o.InstanceDefinition.Id),
                     occurrences=1, eligible=0 if instance_barrier(doc, o) else 1,
                     parent_id=None) for o in top_level_instances(doc)]
    records = {}
    for row in rows:
        key = row['definition_id']
        if wanted is not None and key not in wanted:
            continue
        if key not in records:
            definition = doc.InstanceDefinitions.FindId(Guid(key))
            records[key] = dict(id=key, name=definition.Name, count=0, editable=0,
                top_count=0, nested_count=0,
                raw=definition.GetUserString(ASSIGNMENT_KEY))
        records[key]['count'] += row['occurrences']
        records[key]['nested_count' if row['parent_id'] else 'top_count'] += row['occurrences']
        definition = doc.InstanceDefinitions.FindId(Guid(key))
        if not definition.IsReference:
            records[key]['editable'] += row['eligible']
    return sorted(records.values(), key=lambda r: r['name'].casefold())


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
    No instances move. Protected-only definitions are read-only in the inventory.
    """
    inventory = {r['id']: r for r in definition_inventory(doc, include_nested=True)
                 if r['id'] in changes}
    planned = []
    for key, target_id in changes.items():
        if key not in inventory or not inventory[key]['editable']:
            raise ValueError('A block no longer has a visible, unlocked, editable instance. Refresh the list.')
        definition = doc.InstanceDefinitions.FindId(Guid(key))
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


def plan_cleanup(doc, definition_ids=None, include_nested=True, excluded_definition_ids=()):
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
        try:
            assignment = read_assignment(obj.InstanceDefinition)
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
    undo = doc.BeginUndoRecord('Clean up block layers')
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


def report(rows):
    Rhino.RhinoApp.WriteLine('Block layer cleanup (local nested references included):')
    grouped = {}
    for row in rows:
        key = (row['status'], row['block'], row.get('target_path', row.get('saved_path', '')))
        grouped[key] = grouped.get(key, 0) + 1
    counts = {}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    nested_moves = [r for r in rows if r['status'] == 'moved' and r['parent_id']]
    if nested_moves:
        Rhino.RhinoApp.WriteLine('  {0} nested reference edits affect {1} occurrences.'.format(
            len(nested_moves), sum(r['occurrences'] for r in nested_moves)))
    Rhino.RhinoApp.WriteLine('  ' + (', '.join('{0}: {1}'.format(k, v)
        for k, v in sorted(counts.items())) if counts else 'No block instances found.'))
    for (status, name, path), count in sorted(grouped.items()):
        if status == 'already correct':
            continue
        Rhino.RhinoApp.WriteLine('  {0} | {1} ({2}){3}'.format(
            status, name, count, ' -> ' + path if path else ''))
    for row in rows:
        if row['status'] == 'shared with protected copies':
            Rhino.RhinoApp.WriteLine('  Shared skip: {0} inside {1}; {2} protected occurrences ({3}).'.format(
                row['block'], row['parent_name'], sum(row['protection'].values()),
                ', '.join(sorted(row['protection']))))
    Rhino.RhinoApp.WriteLine('  Unassigned and unresolved blocks stay in place; missing layers require explicit review.')


def missing_targets(doc, definition_ids=None, excluded_definition_ids=()):
    """Group missing full paths once, only for references eligible for cleanup."""
    groups = {}
    for row in plan_cleanup(doc, definition_ids, excluded_definition_ids=excluded_definition_ids):
        if row['status'] != 'missing target layer':
            continue
        path = row['saved_path']
        key = path.casefold()
        if key not in groups:
            groups[key] = dict(key=key, path=path, definitions={}, references=0, occurrences=0)
        group = groups[key]
        definition = doc.InstanceDefinitions.FindId(Guid(row['definition_id']))
        group['definitions'][row['definition_id']] = definition.GetUserString(ASSIGNMENT_KEY)
        group['references'] += 1
        group['occurrences'] += row['occurrences']
    return sorted(groups.values(), key=lambda g: g['key'])


def missing_signature(groups):
    return [(g['key'], g['references'], g['occurrences'], tuple(sorted(g['definitions'].items())))
            for g in sorted(groups, key=lambda g: g['key'])]


def validate_layer_path(path):
    parts = path.split('::')
    if any(not p or p != p.strip() or not Rhino.DocObjects.ModelComponent.IsValidComponentName(p)
           for p in parts):
        raise ValueError('Cannot create the saved layer path "{0}". Choose an existing layer or skip.'.format(path))
    return parts


def _ensure_layer_path(doc, path, created):
    parent = Guid.Empty
    names = []
    for name in validate_layer_path(path):
        names.append(name)
        full = '::'.join(names)
        index = doc.Layers.FindByFullPath(full, -1)
        if index < 0:
            layer = Rhino.DocObjects.Layer()
            layer.Name = name
            layer.ParentLayerId = parent
            index = doc.Layers.Add(layer)
            if index < 0:
                raise RuntimeError('Could not create layer ' + full)
            created.append(doc.Layers[index].Id)
        layer = doc.Layers[index]
        if layer.IsReference:
            raise ValueError('Cannot create or use a target inside a reference layer: ' + full)
        parent = layer.Id
    return doc.Layers[index]


def resolve_missing_targets(doc, groups, choices):
    """Apply reviewed mappings/creation atomically; skip decisions last this run.

    choices: path key -> {'mode': 'skip'|'create'|'existing', 'target_id': ...}.
    No instances move here. Returns created paths, changed rules and skipped IDs.
    """
    ids = {key for group in groups for key in group['definitions']}
    if missing_signature(missing_targets(doc, ids)) != missing_signature(groups):
        raise ValueError('Missing targets changed. Refresh the list before continuing.')
    expected = {}
    skipped = set()
    for group in groups:
        key = group['key']
        choice = choices.get(key, dict(mode='skip'))
        mode = choice.get('mode')
        if mode == 'skip':
            skipped.update(group['definitions'])
        elif mode == 'create':
            parts = validate_layer_path(group['path'])
            for i in range(1, len(parts) + 1):
                index = doc.Layers.FindByFullPath('::'.join(parts[:i]), -1)
                if index >= 0 and doc.Layers[index].IsReference:
                    raise ValueError('A target parent is a reference layer. Choose another layer.')
        elif mode == 'existing':
            try:
                layer = doc.Layers.FindId(Guid(choice['target_id']))
            except Exception:
                raise ValueError('Choose an existing local layer.')
            if layer is None or layer.IsDeleted or layer.IsReference:
                raise ValueError('The chosen layer is no longer available. Choose another layer.')
        else:
            raise ValueError('Unknown missing-layer resolution.')
        expected.update(group['definitions'])
    created = []
    changed = []
    undo = doc.BeginUndoRecord('Resolve missing block layers')
    try:
        changes = {}
        for group in sorted(groups, key=lambda g: (g['path'].count('::'), g['key'])):
            choice = choices.get(group['key'], dict(mode='skip'))
            if choice['mode'] == 'skip':
                continue
            if sc.escape_test(False):
                raise RuntimeError('Layer resolution cancelled; changes rolled back.')
            layer = (_ensure_layer_path(doc, group['path'], created) if choice['mode'] == 'create'
                     else doc.Layers.FindId(Guid(choice['target_id'])))
            changes.update({key: str(layer.Id) for key in group['definitions']})
        changed = save_assignments(doc, changes, expected) if changes else []
        return dict(created=[doc.Layers.FindId(i).FullPath for i in created], changed=changed,
                    skipped=sorted(skipped))
    except Exception:
        failures = []
        for key in changed:
            if not doc.InstanceDefinitions.FindId(Guid(key)).SetUserString(ASSIGNMENT_KEY, expected[key]):
                failures.append('assignment ' + key)
        for layer_id in reversed(created):
            layer = doc.Layers.FindId(layer_id)
            if layer and not layer.IsDeleted and not doc.Layers.Delete(layer.Index, True):
                failures.append('layer ' + layer.FullPath)
        if failures:
            Rhino.RhinoApp.WriteLine('Resolution rollback incomplete; use Undo: ' + ', '.join(failures))
        raise
    finally:
        if undo:
            doc.EndUndoRecord(undo)
