#! python 3
# -*- coding: utf-8 -*-
"""Bulk-assign block layers from a selection. Rhino 8.9+, Python 3."""
import os
import sys
import importlib

import Rhino
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import block_layers
import block_layer_ui

# ScriptEditor retains imports between command runs, including after file updates.
importlib.reload(block_layers)
importlib.reload(block_layer_ui)


def main(doc=None):
    doc = doc or sc.doc
    picker = Rhino.Input.Custom.GetObject()
    picker.SetCommandPrompt('Select block instances to assign their definitions to layers')
    picker.GeometryFilter = Rhino.DocObjects.ObjectType.InstanceReference
    picker.SubObjectSelect = False
    picker.GroupSelect = False
    try:
        picker.GetMultiple(1, 0)
        if picker.CommandResult() != Rhino.Commands.Result.Success:
            return
        definition_ids = list({str(picker.Object(i).Object().InstanceDefinition.Id)
                               for i in range(picker.ObjectCount)})
    finally:
        picker.Dispose()
    try:
        block_layer_ui.edit_assignments(doc, definition_ids)
    except Exception as error:
        Rhino.RhinoApp.WriteLine('AssignBlockLayer: ' + str(error))


if __name__ == '__main__':
    main(globals().get('__rhino_doc__'))
