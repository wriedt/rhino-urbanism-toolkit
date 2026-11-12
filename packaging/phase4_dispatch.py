#! python 3
"""Reload the current installed-package probe even when Script Editor caches it."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('phase4_probe.py')), run_name='__main__')
