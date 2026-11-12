# -*- coding: utf-8 -*-
"""IsolateLockLayer command. Shared implementation in layer_tools.py."""
import importlib
import scriptcontext as sc
import layer_tools
importlib.reload(layer_tools)


def main(doc=None):
    doc = doc or sc.doc
    picked = layer_tools.pick_layers(doc, lock=True)
    if picked is None:
        return
    ids, children = picked
    return layer_tools.run_command(lambda: layer_tools.isolate_lock(doc, ids, children))


if __name__ == '__main__':
    main()
