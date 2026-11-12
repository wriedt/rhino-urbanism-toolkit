#! python 3
"""Phase 3 regression runner; use Rhino Python 3, pass the owning live doc."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import time
import traceback
import Rhino
import scriptcontext as sc

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'work' / 'phase3-validation'


def snapshot(doc):
    options = Rhino.FileIO.SerializationOptions()
    return {
        'objects': {str(o.Id): [o.Geometry.DataCRC(0), o.Attributes.ToJSON(options),
                              o.IsSelected(False)] for o in doc.Objects},
        'layers': {str(l.Id): [l.FullPath, l.IsVisible, l.IsLocked,
                              l.GetPersistentVisibility(), l.GetPersistentLocking()]
                   for l in doc.Layers if not l.IsDeleted},
        'current_layer': str(doc.Layers.CurrentLayer.Id),
        'definitions': {str(d.Id): d.Name for d in doc.InstanceDefinitions if not d.IsDeleted},
        'units': str(doc.ModelUnitSystem), 'modified': doc.Modified,
        'camera': [list(v.ActiveViewport.CameraLocation),
                   list(v.ActiveViewport.CameraTarget)] if (v := doc.Views.ActiveView) else None,
    }


def run(doc):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    before = snapshot(doc)
    sc.sticky['RUT.Phase3.baseline'] = before
    previous = sc.doc
    sc.doc = doc
    results = []
    suites = [
        ('test_layer_tools_rhino.py', False),
        ('test_layer_lock_tools_rhino.py', False),
        ('test_layer_zero_rhino.py', False),
        ('test_block_commands_rhino.py', False),
        ('tests/shape_builder/run_rhino.py', True),
    ]
    try:
        for filename, needs_doc in suites:
            started = time.perf_counter()
            output = io.StringIO()
            result = {'suite': filename}
            try:
                with contextlib.redirect_stdout(output):
                    namespace = runpy.run_path(str(ROOT / filename), run_name='phase3_suite')
                    report = namespace['run'](doc) if needs_doc else namespace['run']()
                result.update(passed=len(report) if isinstance(report, list) else report['passed'],
                              error=None)
            except Exception:
                result.update(passed=0, error=traceback.format_exc())
            result['seconds'] = round(time.perf_counter() - started, 3)
            result['drawing_unchanged'] = snapshot(doc) == before
            if not result['drawing_unchanged']:
                result['error'] = (result['error'] or '') + '\nActive drawing state changed.'
            result['log'] = output.getvalue()
            results.append(result)
            if not result['drawing_unchanged']:
                break
    finally:
        sc.doc = previous
    final = {'rhino': str(Rhino.RhinoApp.Version), 'suites': results,
             'passed': sum(r['passed'] for r in results),
             'drawing_unchanged': snapshot(doc) == before}
    (OUTPUT / 'regressions.json').write_text(json.dumps(final, indent=2), encoding='utf-8')
    print(json.dumps({**final, 'suites': [{k: v for k, v in r.items() if k != 'log'} for r in results]}))
    return final


if __name__ == '__main__':
    run(__rhino_doc__)
