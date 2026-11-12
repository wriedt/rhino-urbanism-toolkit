# -*- coding: utf-8 -*-
"""Isolate selected objects' layers, including child layers by default."""
import importlib
import scriptcontext as sc
import layer_tools
importlib.reload(layer_tools)


def main(doc=None):
    doc = doc or sc.doc
    picked = layer_tools.pick_layers(doc)
    if picked is None:
        return
    ids, children = picked
    return layer_tools.run_command(lambda: layer_tools.isolate(doc, ids, children))


if __name__ == '__main__':
    main()
