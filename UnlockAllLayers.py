# -*- coding: utf-8 -*-
"""UnlockAllLayers command. Shared implementation in layer_tools.py."""
import importlib
import scriptcontext as sc
import layer_tools
importlib.reload(layer_tools)


def main(doc=None):
    return layer_tools.run_command(lambda: layer_tools.update_all(doc or sc.doc, unlock=True))


if __name__ == '__main__':
    main()
