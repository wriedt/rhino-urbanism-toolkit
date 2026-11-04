#! python 3
# -*- coding: utf-8 -*-
"""Clean up assigned local block references at every nesting level. Rhino 8.9+."""
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
    doc = doc or sc.doc
    try:
        resolution = block_layer_ui.resolve_missing_layers(doc)
        if resolution is None:
            Rhino.RhinoApp.WriteLine('Cleanup cancelled; no layers or instances changed.')
            return
        rows = block_layers.cleanup(doc, excluded_definition_ids=resolution['skipped'])
        block_layers.report(rows)
        return rows
    except Exception as error:
        Rhino.RhinoApp.WriteLine('CleanUpBlockLayers: ' + str(error))


if __name__ == '__main__':
    main(globals().get('__rhino_doc__'))
