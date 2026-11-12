#! python 3
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('create_phase5_scene_rhino.py')), run_name='__main__')
