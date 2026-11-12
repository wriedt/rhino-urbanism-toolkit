"""Run packaged scripts with real file paths and the command's Rhino document."""
from pathlib import Path
import runpy
import sys


def run(source, doc):
    import scriptcontext as sc
    directory = Path(__file__).resolve().parent
    target = (directory / source).resolve()
    target.relative_to(directory)
    if not target.is_file() or target.suffix != '.py':
        raise RuntimeError('RUT installation is incomplete. Reinstall this package.')
    # Prefer packaged modules over a source checkout on Rhino's search path.
    location = str(directory)
    if location in sys.path:
        sys.path.remove(location)
    sys.path.insert(0, location)
    old_doc = sc.doc
    try:
        sc.doc = doc
        return runpy.run_path(str(target), run_name='__main__',
                             init_globals={'__rhino_doc__': doc})
    finally:
        sc.doc = old_doc
