#! python 3
# -*- coding: utf-8 -*-
"""Review, bulk-edit and remove layer assignments for used top-level blocks."""
import os
import sys
import importlib

import Rhino
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import block_layers
import block_layer_ui

importlib.reload(block_layers)
importlib.reload(block_layer_ui)


def main(doc=None):
    try:
        block_layer_ui.edit_assignments(doc or sc.doc)
    except Exception as error:
        Rhino.RhinoApp.WriteLine('ManageBlockLayers: ' + str(error))


if __name__ == '__main__':
    main(globals().get('__rhino_doc__'))
