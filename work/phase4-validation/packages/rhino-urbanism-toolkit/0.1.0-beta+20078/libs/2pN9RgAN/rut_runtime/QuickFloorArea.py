#! python 3
# -*- coding: utf-8 -*-
"""RUTQuickFloorArea: print and copy a complete base-area measurement."""
import os
import sys
import Rhino
import scriptcontext as sc

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
import floor_area as area


def pick(doc):
    ids = area.selected_ids(doc)
    if ids:
        return ids
    getter = Rhino.Input.Custom.GetObject()
    try:
        getter.SetCommandPrompt('Select solids or blocks for QuickFloorArea')
        getter.GeometryFilter = area.SELECTION_TYPES
        getter.SubObjectSelect = False
        getter.GetMultiple(1, 0)
        if getter.CommandResult() != Rhino.Commands.Result.Success:
            return []
        ids = [getter.Object(i).ObjectId for i in range(getter.ObjectCount)]
        # Preserve the picked input while the warning is being inspected.
        for object_id in ids:
            doc.Objects.Select(object_id)
        return ids
    finally:
        getter.Dispose()


def acknowledge():
    getter = Rhino.Input.Custom.GetString()
    try:
        getter.SetCommandPrompt('Inspect coral geometry. Enter to acknowledge, or Esc to cancel')
        getter.AcceptNothing(True)
        getter.Get()
    finally:
        getter.Dispose()


def run(doc, ids, wait=acknowledge, copy=None):
    result = area.measure(doc, ids)
    preview = None
    try:
        if not result.valid:
            Rhino.RhinoApp.WriteLine('QuickFloorArea: measurement failed. No total copied.')
            for object_id, reason in result.issues:
                Rhino.RhinoApp.WriteLine('{}: {}'.format(area.object_label(doc, object_id), reason))
            preview = area.SectionPreview(doc, [])
            preview.set_failures(result.failures)
            preview.Enabled = True
            doc.Views.Redraw()
            wait()
            return False
        text = area.area_value(doc, result.base)
        try:
            (copy or area.ui.copy_text_to_clipboard)(text)
            Rhino.RhinoApp.WriteLine('Base plane area: {} | Value copied to clipboard'.format(text))
        except Exception:
            Rhino.RhinoApp.WriteLine('Base plane area: {} | Clipboard unavailable; value not copied'.format(text))
        return True
    finally:
        if preview:
            preview.Enabled = False
            doc.Views.Redraw()
        result.dispose()


def main():
    doc = sc.doc
    ids = pick(doc)
    if ids:
        run(doc, ids)


if __name__ == '__main__':
    main()
