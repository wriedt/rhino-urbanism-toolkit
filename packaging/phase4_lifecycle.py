#! python 3
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('phase4_lifecycle_impl.py')), run_name='__main__')
