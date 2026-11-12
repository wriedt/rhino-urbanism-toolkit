# -*- coding: utf-8 -*-
"""UnisolateLayer command. Shared implementation in layer_tools.py."""
import importlib
import scriptcontext as sc
import layer_tools
importlib.reload(layer_tools)


def main(doc=None):
    return layer_tools.run_command(lambda: layer_tools.unisolate(doc or sc.doc))


if __name__ == '__main__':
    main()
