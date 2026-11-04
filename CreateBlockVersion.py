#! python 3
# -*- coding: utf-8 -*-
"""Create a numbered, independent version of selected Rhino 8 blocks.

Run in ScriptEditor (Python 3). Enter accepts the proposed version; Number
chooses which digit group is the version. Nested definitions remain shared.
"""
import re

import Rhino
import scriptcontext as sc
from System.Collections.Generic import List


def digit_groups(name):
    return list(re.finditer(r"[0-9]+", name))


def next_name(name, names, group=-1):
    """Exact prefix/suffix family, case insensitive; width is a minimum."""
    match = digit_groups(name)[group]
    prefix, suffix = name[:match.start()], name[match.end():]
    pattern = re.compile(r"^" + re.escape(prefix) + r"([0-9]+)" +
                         re.escape(suffix) + r"$", re.IGNORECASE)
    highest = int(match.group())
    for other in names:
        found = pattern.fullmatch(other)
        if found:
            highest = max(highest, int(found.group(1)))
    return prefix + str(highest + 1).zfill(len(match.group())) + suffix


def definition_names(doc):
    return [d.Name for d in doc.InstanceDefinitions if not d.IsDeleted]


def make_plan(doc, object_ids, group=-1, baseline=None, reserved=()):
    """Read-only preflight for instances of one source definition."""
    objects = [doc.Objects.FindId(i) for i in object_ids]
    if not objects or any(not isinstance(o, Rhino.DocObjects.InstanceObject)
                          or o.IsInstanceDefinitionGeometry or o.IsLocked
                          or o.IsReference for o in objects):
        raise ValueError("Select editable, top-level block instances.")
    source = objects[0].InstanceDefinition
    if any(o.InstanceDefinition.Id != source.Id for o in objects):
        raise ValueError("Each plan must contain instances of the same definition.")
    if source.IsReference or source.UpdateType != Rhino.DocObjects.InstanceDefinitionUpdateType.Static:
        raise ValueError("Linked/reference blocks are not supported by this prototype.")
    names = definition_names(doc) + list(reserved)
    source_name = source.Name
    if baseline is not None:
        if digit_groups(source_name):
            raise ValueError("A starting name is only needed for unnumbered blocks.")
        baseline = baseline.strip()
        if not Rhino.DocObjects.ModelComponent.IsValidComponentName(baseline):
            raise ValueError("The starting block name is invalid.")
        if not digit_groups(baseline):
            raise ValueError("The starting name must include a version number.")
        if baseline.casefold() in [n.casefold() for n in names]:
            raise ValueError("That starting block name already exists.")
        source_name = baseline
    if not digit_groups(source_name):
        raise ValueError("Choose a numbered starting name first.")
    return dict(source_index=source.Index, original_name=source.Name,
                baseline=baseline, new_name=next_name(source_name, names, group),
                ids=[o.Id for o in objects])


def apply_plans(doc, plans):
    """Apply prepared plans in one undo record; roll back on failure."""
    created, renamed, switched = [], [], []
    undo = doc.BeginUndoRecord("Create block version")
    redraw = doc.Views.RedrawEnabled
    try:
        doc.Views.RedrawEnabled = False
        occupied = {n.casefold() for n in definition_names(doc)}
        for plan in plans:
            if plan['new_name'].casefold() in occupied:
                raise ValueError("The proposed name is already in use. Run again.")
            occupied.add(plan['new_name'].casefold())
            source = doc.InstanceDefinitions[plan['source_index']]
            if source.IsDeleted or source.Name != plan['original_name']:
                raise ValueError("The source definition changed. Run again.")
            if plan['baseline']:
                if plan['baseline'].casefold() in occupied:
                    raise ValueError("The starting name is already in use.")
                if not doc.InstanceDefinitions.Modify(source, plan['baseline'], source.Description, True):
                    raise RuntimeError("Could not rename the original definition.")
                renamed.append(plan)
                occupied.add(plan['baseline'].casefold())
            geometry = List[Rhino.Geometry.GeometryBase]()
            attributes = List[Rhino.DocObjects.ObjectAttributes]()
            for obj in source.GetObjects():
                geometry.Add(obj.Geometry.Duplicate())
                attributes.Add(obj.Attributes.Duplicate())
            index = doc.InstanceDefinitions.Add(plan['new_name'], source.Description,
                source.Url or '', source.UrlDescription or '', Rhino.Geometry.Point3d.Origin,
                geometry, attributes)
            if index < 0:
                raise RuntimeError("Could not create " + plan['new_name'])
            created.append(index)
            strings = source.GetUserStrings()
            if strings:
                for key in strings.AllKeys:
                    doc.InstanceDefinitions[index].SetUserString(key, strings[key])
            for object_id in plan['ids']:
                obj = doc.Objects.FindId(object_id)
                if obj is None or obj.InstanceDefinition.Index != source.Index:
                    raise RuntimeError("A selected instance changed. Run again.")
                if not doc.Objects.ReplaceInstanceObject(object_id, index):
                    raise RuntimeError("Could not switch a selected instance.")
                switched.append((object_id, source.Index))
        return [p['new_name'] for p in plans]
    except Exception:
        failures = []
        for object_id, source_index in reversed(switched):
            if not doc.Objects.ReplaceInstanceObject(object_id, source_index):
                failures.append('instance restore')
        for index in reversed(created):
            if not doc.InstanceDefinitions.Delete(index, True, True):
                failures.append('new definition removal')
        for plan in reversed(renamed):
            source = doc.InstanceDefinitions[plan['source_index']]
            if not doc.InstanceDefinitions.Modify(source, plan['original_name'], source.Description, True):
                failures.append('original name restore')
        if failures:
            Rhino.RhinoApp.WriteLine("Rollback incomplete: " + ', '.join(failures) + ". Use Undo.")
        raise
    finally:
        doc.Views.RedrawEnabled = redraw
        if undo:
            doc.EndUndoRecord(undo)
        doc.Views.Redraw()


def choose_group(name):
    matches = digit_groups(name)
    choices = Rhino.Input.Custom.GetOption()
    choices.SetCommandPrompt("Choose version number in " + name)
    mapping = {}
    for i, match in enumerate(matches):
        label = name[:match.start()] + '[' + match.group() + ']' + name[match.end():]
        Rhino.RhinoApp.WriteLine("Group{0}: {1}".format(i + 1, label))
        mapping[choices.AddOption('Group' + str(i + 1))] = i
    try:
        if choices.Get() != Rhino.Input.GetResult.Option:
            return None
        return mapping[choices.OptionIndex()]
    finally:
        choices.Dispose()


def prompt_baseline(name):
    options = Rhino.Input.Custom.GetOption()
    options.SetCommandPrompt('Rename original "{0}" to a numbered name and create its next version?'.format(name))
    yes = options.AddOption('RenameAndCreate')
    options.AddOption('Cancel')
    try:
        if options.Get() != Rhino.Input.GetResult.Option or options.OptionIndex() != yes:
            return None
    finally:
        options.Dispose()
    result, value = Rhino.Input.RhinoGet.GetString(
        'Starting name (renames the definition for ALL its existing instances)', False, name + '_01')
    return value if result == Rhino.Commands.Result.Success else None


def main(doc=None):
    doc = doc or sc.doc
    picker = Rhino.Input.Custom.GetObject()
    picker.SetCommandPrompt('Select block instances to create a new version')
    picker.GeometryFilter = Rhino.DocObjects.ObjectType.InstanceReference
    picker.SubObjectSelect = False
    picker.GroupSelect = False
    try:
        picker.GetMultiple(1, 0)
        if picker.CommandResult() != Rhino.Commands.Result.Success:
            return
        grouped = {}
        for i in range(picker.ObjectCount):
            obj = picker.Object(i).Object()
            grouped.setdefault(obj.InstanceDefinition.Index, []).append(obj.Id)
    finally:
        picker.Dispose()
    plans, reserved = [], []
    try:
        for source_index, ids in grouped.items():
            source = doc.InstanceDefinitions[source_index]
            baseline = None
            if not digit_groups(source.Name):
                baseline = prompt_baseline(source.Name)
                if baseline is None:
                    return
            group = -1
            while True:
                plan = make_plan(doc, ids, group, baseline, reserved)
                options = Rhino.Input.Custom.GetOption()
                options.SetCommandPrompt('{0} -> {1} ({2} selected). Enter to create'.format(
                    source.Name, plan['new_name'], len(ids)))
                options.AcceptNothing(True)
                create = options.AddOption('Create')
                number = options.AddOption('Number')
                try:
                    result = options.Get()
                    option = options.OptionIndex() if result == Rhino.Input.GetResult.Option else None
                finally:
                    options.Dispose()
                if result == Rhino.Input.GetResult.Nothing or option == create:
                    break
                if option != number:
                    return
                group = choose_group(baseline or source.Name)
                if group is None:
                    return
            plans.append(plan)
            reserved.append(plan['new_name'])
            if baseline:
                reserved.append(baseline)
        names = apply_plans(doc, plans)
        for plan, name in zip(plans, names):
            for object_id in plan['ids']:
                obj = doc.Objects.FindId(object_id)
                if obj:
                    obj.Select(True)
            Rhino.RhinoApp.WriteLine('Created {0}: {1} selected instance(s).'.format(name, len(plan['ids'])))
        doc.Views.Redraw()
    except Exception as error:
        Rhino.RhinoApp.WriteLine('CreateBlockVersion: ' + str(error))


if __name__ == '__main__':
    main(globals().get('__rhino_doc__'))
