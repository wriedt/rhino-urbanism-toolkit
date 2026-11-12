#! python 3
"""Final package discovery/smoke probe in the dedicated empty release profile."""
import json
from pathlib import Path
import sys
import traceback
import Rhino
import scriptcontext as sc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/phase6-validation'
OUT.mkdir(exist_ok=True)
doc = globals().get('__rhino_doc__') or sc.doc
report = {'explicit_plugin_load': False, 'clipboard_access': False}
try:
    assert not list(doc.Objects), 'Use the empty release-validation document only.'
    report['aliases'] = [n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames() if n.upper().startswith('RUT')]
    assert not report['aliases']
    expected = json.loads((ROOT/'assets/toolbar/v1/manifest.json').read_text())
    report['commands'] = sorted(n for n in Rhino.Commands.Command.GetCommandNames(True, False) if n.startswith('RUT'))
    assert report['commands'] == sorted(e['command'] for e in expected)
    original_modified = doc.Modified
    history = len(Rhino.RhinoApp.CommandHistoryWindowText)
    assert Rhino.RhinoApp.RunScript('_RUTShowAllLayers', False)
    assert Rhino.RhinoApp.RunScript('_RUTUnlockAllLayers', False)
    text = Rhino.RhinoApp.CommandHistoryWindowText[history:]
    assert 'Traceback' not in text and 'Error occured' not in text
    report['dispatch_history'] = text
    import System
    assembly = next(a for a in System.AppDomain.CurrentDomain.GetAssemblies()
        if a.GetName().Name == 'rhino-urbanism-toolkit')
    rhp = Path(assembly.Location)
    normal_root = Path(System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData))/'McNeel/Rhinoceros/packages/8.0/rhino-urbanism-toolkit'
    assert normal_root.resolve() in rhp.resolve().parents, str(rhp)
    report['assembly'] = str(rhp)
    report['version'] = rhp.parent.name
    assert report['version'].startswith('0.1.0-beta1+')
    runtime = next(rhp.parent.glob('libs/*/rut_runtime'))
    sys.path.insert(0, str(runtime))
    def source_guard(event, args):
        if event == 'open' and isinstance(args[0], str):
            path = Path(args[0]).resolve()
            if path.suffix.lower() in ('.py', '.pyc') and ROOT in path.parents:
                if ROOT/'packaging' not in path.parents and ROOT/'work' not in path.parents:
                    raise PermissionError('Source-checkout Python access disabled for release validation')
    sys.addaudithook(source_guard)
    try:
        (ROOT/'floor_area.py').read_text()
        raise AssertionError('Source access should be blocked.')
    except PermissionError:
        report['source_access_blocked'] = True
    import floor_area
    report['floor_area_module'] = floor_area.__file__
    assert normal_root.resolve() in Path(floor_area.__file__).resolve().parents
    test_doc = Rhino.RhinoDoc.CreateHeadless(None)
    try:
        test_doc.ModelUnitSystem = Rhino.UnitSystem.Meters
        brep = Rhino.Geometry.BoundingBox(Rhino.Geometry.Point3d(0,0,0), Rhino.Geometry.Point3d(10,8,3)).ToBrep()
        oid = test_doc.Objects.AddBrep(brep)
        measured = floor_area.measure(test_doc, [oid], sections=True)
        try:
            assert measured.valid and abs(measured.base-80) < 1e-6 and abs(measured.section-80) < 1e-6
            report['measurement'] = {'base': measured.base, 'section': measured.section}
        finally:
            measured.dispose()
            brep.Dispose()
    finally:
        test_doc.Dispose()
    # Check the actual packaged fallback, not a hand-edited UI review file.
    fallback = rhp.with_name('RUT.rui')
    toolbar = Rhino.RhinoApp.ToolbarFiles.Open(str(fallback))
    assert toolbar is not None
    report['fallback_toolbar'] = {'path': str(toolbar.Path),
        'names': [toolbar.GetToolbar(i).Name for i in range(toolbar.ToolbarCount)]}
    assert report['fallback_toolbar']['names'] == ['RUT | Rhino Urbanism Toolkit']
    assert not list(doc.Objects)
    doc.Modified = original_modified
    report['drawing_unchanged'] = True
    report['success'] = True
except Exception:
    report['success'] = False
    report['error'] = traceback.format_exc()
(OUT/'package-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
