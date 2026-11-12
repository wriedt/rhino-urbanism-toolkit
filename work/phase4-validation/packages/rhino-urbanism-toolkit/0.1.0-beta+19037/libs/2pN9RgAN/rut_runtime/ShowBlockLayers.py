#! python 3
# -*- coding: utf-8 -*-
"""RUTShowBlockLayers: a focused Rhino 8 block command (stable script filename)."""
import os
import sys
import importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scriptcontext as sc
import urbanism_ui
import block_versions
import block_actions
import block_layers
import block_dialogs
for helper in (urbanism_ui, block_versions, block_actions, block_layers, block_dialogs):
    importlib.reload(helper)


def main(doc=None):
    return block_dialogs.run_layers(doc or sc.doc, 'show')


if __name__ == '__main__':
    main(globals().get('__rhino_doc__'))
