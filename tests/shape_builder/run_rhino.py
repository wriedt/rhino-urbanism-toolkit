#! python 3
# -*- coding: utf-8 -*-
"""Run Shape Builder regression suites in Rhino 8 without editing the live drawing."""
import json
import os
import Rhino
import scriptcontext as sc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SUITES = (
    'test_shape_builder_rhino.py',
    'test_shape_builder_hatches_rhino.py',
    'test_shape_builder_masters_rhino.py',
    'test_shape_builder_types_rhino.py',
    'test_shape_builder_leftovers_rhino.py',
    'test_shape_builder_edge_erase_rhino.py',
    'test_shape_builder_attributes_rhino.py',
)


def snapshot(doc):
    if doc is None:
        return None
    options = Rhino.FileIO.SerializationOptions()
    return {str(obj.Id): (obj.Geometry.DataCRC(0), obj.Attributes.ToJSON(options),
                          obj.IsSelected(False)) for obj in doc.Objects}


def run(doc=None):
    before = snapshot(doc)
    results = []
    os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)
    try:
        for filename in SUITES:
            path = os.path.join(HERE, filename)
            namespace = {'__name__': 'regression_suite', '__file__': path}
            try:
                with open(path, encoding='utf-8') as source:
                    exec(compile(source.read(), path, 'exec'), namespace)
                report = namespace['report']
                results.append({'suite': filename, 'passed': report['passed'],
                                'failures': report.get('failures', [])})
            except Exception as error:
                results.append({'suite': filename, 'passed': 0, 'failures': [str(error)]})
    finally:
        if snapshot(doc) != before:
            raise AssertionError('The active drawing changed during testing.')
    report = {'passed': sum(r['passed'] for r in results), 'suites': results,
              'drawing_unchanged': True}
    with open(os.path.join(ROOT, 'work', 'shape-builder-regression-tests.json'),
              'w', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
    print(json.dumps(report))
    if any(r['failures'] for r in results):
        raise AssertionError('Shape Builder regression tests failed; see the report.')
    return report


if __name__ == '__main__':
    run(globals().get('__rhino_doc__') or sc.doc)
