#! python 3
# -*- coding: utf-8 -*-
"""Legacy toolbar entry point: opens the live FloorArea inspector."""
import os
import sys

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
from FloorArea import main

if __name__ == '__main__':
    main()
