"""Prepare the explicit beta command/library allowlist; no Rhino imports needed."""
import ast
import base64
import json
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'rhino-urbanism-toolkit.rhproj'
STAGE = ROOT / 'build' / 'stage'
NAMESPACE = uuid.UUID('6ac6211b-d98c-47f5-95c0-5a542d379a2c')
HELPERS = ['layer_tools', 'block_actions', 'block_dialogs', 'block_layers',
           'block_versions', 'floor_area', 'urbanism_ui', 'viewport_ui',
           'pushpull_mixed', 'shape_builder_leftovers']
DOCS = ['START_HERE.txt']


def commands():
    result = json.loads((ROOT / 'assets/toolbar/v1/manifest.json').read_text())
    for entry in result:
        if not entry['command'].startswith('RUT'):
            raise ValueError('Every packaged command must use the uppercase RUT prefix: ' + entry['command'])
        name = entry['command'][3:]
        entry['source'] = name + '.py'
    return result


def prepare():
    entries = commands()
    assert len(entries) == 18 and len({e['command'] for e in entries}) == 18
    runtime = STAGE / 'rut_runtime'
    wrappers = ROOT / 'packaging' / 'commands'
    runtime.mkdir(parents=True, exist_ok=True)
    wrappers.mkdir(parents=True, exist_ok=True)
    allowed = {e['source'] for e in entries} | {h + '.py' for h in HELPERS}
    allowed.add('rut_bootstrap.py')
    allowed.add('__init__.py')
    # Never distribute stale files from an earlier scope. Only this generated
    # directory is cleaned; check every resolved target before removing a file.
    for file in runtime.rglob('*'):
        if file.is_file() and file.name not in allowed:
            file.resolve().relative_to(runtime.resolve())
            file.unlink()
    for name in allowed - {'rut_bootstrap.py', '__init__.py'}:
        ast.parse((ROOT / name).read_text(encoding='utf-8-sig'), filename=name)
        shutil.copyfile(ROOT / name, runtime / name)
    shutil.copyfile(ROOT / 'packaging/rut_bootstrap.py', runtime / 'rut_bootstrap.py')
    (runtime / '__init__.py').write_text('"""Private runtime library for Rhino Urbanism Toolkit."""\n', encoding='utf-8')
    project = json.loads(PROJECT.read_text(encoding='utf-8-sig'))
    assert project['id'] == str(NAMESPACE), 'Keep the existing plugin identity'
    project['identity']['version'] = json.loads(
        (ROOT/'packaging/release.json').read_text())['version']
    project['settings']['buildTarget'] = {
        'host': {'name': 'Rhino3D', 'version': '8.36', 'os': 'windows'},
        'title': 'Rhino3D (8.36 - Windows)', 'slug': 'rh8_36-win'}
    project['codes'] = []
    language = {'id': '*.*.python', 'version': '3.*.*'}
    for entry in entries:
        command = entry['command']
        wrapper = wrappers / (command + '.py')
        wrapper.write_text(
            '#! python 3\n# -*- coding: utf-8 -*-\n'
            '"""Generated package entry point; edit packaging/prepare.py."""\n'
            'from rut_runtime import rut_bootstrap\n'
            f'rut_bootstrap.run({entry["source"]!r}, __rhino_doc__)\n',
            encoding='utf-8')
        image = {}
        for mode, relative in entry['icons'].items():
            svg = ROOT / 'assets/toolbar/v1' / relative
            image[mode] = {'type': 'svg', 'data': base64.b64encode(svg.read_bytes()).decode('ascii')}
        project['codes'].append({
            'id': str(uuid.uuid5(NAMESPACE, command)), 'language': language,
            'title': command, 'uri': wrapper.relative_to(ROOT).as_posix(),
            'image': image
        })
    project['libraries'] = [{'type': 'uri', 'library': {
        'base': 'build/stage/rut_runtime/', 'language': language}}]
    # Resources have an explicit allowlist; development drawings and work/ are
    # never traversed by the builder.
    resources = []
    for name in ['LICENSE'] + DOCS:
        assert (ROOT / name).is_file(), name
        resources.append({'id': str(uuid.uuid5(NAMESPACE, name)), 'uri': name})
    project['resources'] = resources
    PROJECT.write_text(json.dumps(project, indent=2) + '\n', encoding='utf-8')
    report = {'commands': [e['command'] for e in entries],
              'conditional': [e['command'] for e in entries if e['conditional']],
              'runtime_files': sorted(allowed), 'resources': ['LICENSE'] + DOCS,
              'phase': 'Release preparation; see PHASE6_RELEASE_REVIEW.md for validation and approval status'}
    (STAGE / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Prepared {len(entries)} commands, {len(allowed)} runtime files and {len(resources)} resources.')


if __name__ == '__main__':
    prepare()
