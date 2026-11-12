"""Packaging boundaries, dependency closure and context cleanup (no Rhino needed)."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_staged_dependency_closure(self):
        inventory = json.loads((ROOT / 'build/stage/inventory.json').read_text())
        runtime = ROOT / 'build/stage/rut_runtime'
        names = {Path(f).stem for f in inventory['runtime_files']}
        repository_modules = {p.stem for p in ROOT.glob('*.py')}
        for file in runtime.glob('*.py'):
            tree = ast.parse(file.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                imports = ([a.name.split('.')[0] for a in node.names]
                           if isinstance(node, ast.Import) else
                           [node.module.split('.')[0]]
                           if isinstance(node, ast.ImportFrom) and node.module else [])
                for name in imports:
                    if name in repository_modules:
                        self.assertIn(name, names, (file.name, name))

    def test_no_development_files_or_stale_source(self):
        inventory = json.loads((ROOT / 'build/stage/inventory.json').read_text())
        runtime = ROOT / 'build/stage/rut_runtime'
        self.assertEqual({p.name for p in runtime.glob('*.py')}, set(inventory['runtime_files']))
        for name in inventory['runtime_files']:
            if name == '__init__.py':
                self.assertEqual((runtime / name).read_text(), '"""Private runtime library for Rhino Urbanism Toolkit."""\n')
                continue
            source = ROOT / ('packaging/rut_bootstrap.py' if name == 'rut_bootstrap.py' else name)
            self.assertEqual((runtime / name).read_bytes(), source.read_bytes())
        self.assertFalse(any(n.startswith('test_') for n in inventory['runtime_files']))

    def exercise_bootstrap(self, source, filename='fixture.py'):
        spec = importlib.util.spec_from_file_location('bootstrap_test', ROOT / 'packaging/rut_bootstrap.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_doc, command_doc = object(), object()
        context = types.SimpleNamespace(doc=original_doc)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            module.__file__ = str(folder / 'rut_bootstrap.py')
            (folder / 'fixture.py').write_text(source)
            original_path = list(sys.path)
            try:
                with patch.dict(sys.modules, {'scriptcontext': context}):
                    try:
                        return module.run(filename, command_doc), command_doc
                    finally:
                        self.assertIs(context.doc, original_doc)
            finally:
                sys.path[:] = original_path

    def test_bootstrap_uses_injected_document(self):
        result, doc = self.exercise_bootstrap(
            'import scriptcontext as sc\nseen = (sc.doc, __rhino_doc__, __name__)\n')
        self.assertEqual(result['seen'], (doc, doc, '__main__'))

    def test_bootstrap_restores_context_after_failure(self):
        with self.assertRaisesRegex(ValueError, 'fixture error'):
            self.exercise_bootstrap('raise ValueError("fixture error")\n')

    def test_bootstrap_rejects_directory_escape(self):
        with self.assertRaises(ValueError):
            self.exercise_bootstrap('', '../outside.py')


if __name__ == '__main__':
    unittest.main()
