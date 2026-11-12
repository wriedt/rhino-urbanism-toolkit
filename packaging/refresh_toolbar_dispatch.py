#! python 3
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('refresh_toolbar_rhino.py')), run_name='__main__')
