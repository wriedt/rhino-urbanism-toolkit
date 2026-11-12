#! python 3
"""Synthetic drawing benchmarks in a disposable Rhino document; no live edits."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import Rhino

ROOT = Path(__file__).resolve().parents[1]


def run(sizes=(10, 20)):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location('sb_benchmark', ROOT / 'ShapeBuilder.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = []
    for n in sizes:
        doc = Rhino.RhinoDoc.CreateHeadless(None)
        doc.ModelAbsoluteTolerance = .001
        inputs, builder = [], None
        try:
            for i in range(n + 1):
                inputs.extend([
                    Rhino.Geometry.LineCurve(Rhino.Geometry.Point3d(i*10, 0, 0), Rhino.Geometry.Point3d(i*10, n*10, 0)),
                    Rhino.Geometry.LineCurve(Rhino.Geometry.Point3d(0, i*10, 0), Rhino.Geometry.Point3d(n*10, i*10, 0))])
            started = time.perf_counter()
            builder = module.Builder(doc, inputs)
            prepared = time.perf_counter() - started
            assert len(builder.cells) == n*n
            started = time.perf_counter()
            builder.begin_stroke()
            for index in range(len(builder.cells)):
                builder.touch(index)
            builder.apply_stroke()
            merged = time.perf_counter() - started
            assert len(builder.groups) == 1
            started = time.perf_counter()
            builder.undo()
            undone = time.perf_counter() - started
            assert len(builder.groups) == n*n
            results.append({'input_lines': len(inputs), 'regions': n*n,
                            'prepare_seconds': round(prepared, 3),
                            'merge_seconds': round(merged, 3),
                            'stroke_undo_seconds': round(undone, 3)})
            # Avoid escalating into a lengthy UI-blocking benchmark.
            if prepared + merged > 10:
                break
        finally:
            if builder:
                builder.dispose_geometry()
            for curve in inputs:
                curve.Dispose()
            doc.Dispose()
    path = ROOT / 'work/phase3-validation/shape-builder-performance.json'
    path.write_text(json.dumps({'synthetic_only': True, 'cases': results}, indent=2))
    print(json.dumps(results))
    return results


if __name__ == '__main__':
    run()
