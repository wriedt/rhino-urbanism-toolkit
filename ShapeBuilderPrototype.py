#! python 3
# -*- coding: utf-8 -*-
"""Compatibility launcher for buttons that still reference the prototype filename."""
import os
import runpy

if __name__ == '__main__':
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ShapeBuilder.py'),
                   run_name='__main__',
                   init_globals={'__rhino_doc__': globals().get('__rhino_doc__')})
