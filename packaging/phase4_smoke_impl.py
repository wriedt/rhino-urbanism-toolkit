"""Exercise actual installed commands in the dedicated empty validation profile."""
import json
from pathlib import Path
import sys
import time
import traceback
import Rhino
import Eto.Forms as forms
import scriptcontext as sc
from System import Guid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/phase4-validation'
doc = globals().get('__rhino_doc__') or sc.doc
assert not list(doc.Objects), 'Use the empty validation document only.'
assert not [n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames() if n.upper().startswith('RUT')]
installation = json.loads((OUT / 'installation.json').read_text())
runtime = next(Path(installation['plugin_files'][0]).parent.glob('libs/*/rut_runtime'))
sys.path.insert(0, str(runtime))
import layer_tools
import floor_area
import block_dialogs
old_context = sc.doc
sc.doc = doc
owned = []
layers = []
definitions = []
results = []
original_layer = doc.Layers.CurrentLayerIndex
original_modified = doc.Modified
original_ui_copy = floor_area.ui.copy_text_to_clipboard
copied = []


def check(value, name):
    if not value:
        raise AssertionError(name)


def command(name, assertion=None, close_dialog=False):
    started = time.perf_counter()
    state = {'closed': False, 'ticks': 0, 'windows': []}
    timer = forms.UITimer()
    timer.Interval = .2
    def tick(sender, event):
        if state['closed']:
            return
        for window in list(forms.Application.Instance.Windows):
            if 'RUT' in str(window.Title):
                state['windows'].append(str(window.Title))
                if close_dialog:
                    window.Close()
    if close_dialog:
        timer.Elapsed += tick
        timer.Start()
    history = len(Rhino.RhinoApp.CommandHistoryWindowText)
    try:
        ran = Rhino.RhinoApp.RunScript('_' + name, False)
        text = Rhino.RhinoApp.CommandHistoryWindowText[history:]
        check('Traceback' not in text and 'Error occured running command' not in text, name + ': ' + text)
        check(ran, name + ' was not dispatched')
        if assertion:
            assertion()
        results.append({'command': name, 'passed': True, 'windows': state['windows'],
                        'seconds': round(time.perf_counter()-started, 3)})
    except Exception:
        results.append({'command': name, 'passed': False, 'error': traceback.format_exc()})
    finally:
        state['closed'] = True
        timer.Stop()
        if close_dialog:
            timer.Elapsed -= tick
        timer.Dispose()
        (OUT / 'command-smoke.json').write_text(json.dumps(results, indent=2))


def select(ids):
    doc.Objects.UnselectAll()
    for oid in ids:
        doc.Objects.Select(oid)


try:
    for name in ['RUT_Phase4_A', 'RUT_Phase4_B']:
        layer = Rhino.DocObjects.Layer()
        layer.Name = name
        layers.append(doc.Layers.Add(layer))
    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layers[0]
    point = doc.Objects.AddPoint(Rhino.Geometry.Point3d.Origin, attr)
    owned.append(point)
    select([point])
    command('RUTIsolateLayer', lambda: check(not doc.Layers[layers[1]].IsVisible, 'Other layer hidden'))
    command('RUTUnisolateLayer', lambda: check(doc.Layers[layers[1]].IsVisible, 'Visibility restored'))
    select([point])
    command('RUTIsolateLockLayer', lambda: check(doc.Layers[layers[1]].IsLocked, 'Other layer locked'))
    command('RUTUnisolateLockLayer', lambda: check(not doc.Layers[layers[1]].IsLocked, 'Lock restored'))
    for name in ['RUTShowAllLayers', 'RUTUnlockAllLayers', 'RUTShowAndUnlockAllLayers', 'RUTToggleLayerExpansion']:
        command(name)
    index = doc.InstanceDefinitions.Add('RUT_Phase4_Block_01', '', Rhino.Geometry.Point3d.Origin,
        [Rhino.Geometry.Point(Rhino.Geometry.Point3d.Origin)], [Rhino.DocObjects.ObjectAttributes()])
    definitions.append(index)
    block = doc.Objects.AddInstanceObject(index, Rhino.Geometry.Transform.Identity)
    owned.append(block)
    for name in ['RUTCreateBlockVersion', 'RUTConsolidateBlockVersions', 'RUTRenameBlockFamily',
                 'RUTAssignBlockLayer', 'RUTApplyBlockLayers', 'RUTShowBlockLayers']:
        select([block])
        command(name, close_dialog=True)
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    brep = Rhino.Geometry.Brep.CreateFromBox(Rhino.Geometry.BoundingBox(
        Rhino.Geometry.Point3d.Origin, Rhino.Geometry.Point3d(10*scale, 8*scale, 3*scale)))
    box = doc.Objects.AddBrep(brep)
    brep.Dispose()
    owned.append(box)
    select([box])
    floor_area.ui.copy_text_to_clipboard = copied.append
    command('RUTQuickFloorArea', lambda: check(copied[-1] == '80.00 m²', 'Quick area value'))
    command('RUTFloorArea', lambda: check('RUT.FloorArea.'+str(doc.RuntimeSerialNumber) in sc.sticky, 'Live controller exists'))
    controller = sc.sticky.get('RUT.FloorArea.'+str(doc.RuntimeSerialNumber))
    if controller:
        check(controller.result.valid, 'Installed inspector result')
        controller.form.Close()
    # Load both conditional commands using their actual native command classes.
    # Controlled input returns Cancel before any document edit; phase 3 covers
    # the geometry and native preview/picker cleanup separately.
    import importlib.util
    import System
    assembly = next(a for a in System.AppDomain.CurrentDomain.GetAssemblies()
                    if a.GetName().Name == 'rhino-urbanism-toolkit')
    names = [str(n) for n in Rhino.Commands.Command.GetCommandNames(True, False) if str(n).startswith('RUT')]
    check(all(n.startswith('RUT') for n in names) and len(names) == 18, '18 uppercase-prefixed registered commands')
    (OUT / 'registered-commands.json').write_text(json.dumps(sorted(names), indent=2))
finally:
    floor_area.ui.copy_text_to_clipboard = original_ui_copy
    controller = sc.sticky.get('RUT.FloorArea.'+str(doc.RuntimeSerialNumber))
    if controller:
        controller.form.Close()
    doc.Layers.SetCurrentLayerIndex(original_layer, True)
    for oid in reversed(owned):
        obj = doc.Objects.FindId(oid)
        if obj:
            doc.Objects.Unlock(oid, True)
            doc.Objects.Delete(oid, True)
    for index in reversed(definitions):
        doc.InstanceDefinitions.Delete(index, True, True)
    for index in reversed(layers):
        doc.Layers.Delete(index, True)
    doc.Modified = original_modified
    sc.doc = old_context
    doc.Views.Redraw()
    (OUT / 'module-paths.json').write_text(json.dumps({n:getattr(m,'__file__',None)
        for n,m in sys.modules.items() if n in ['layer_tools','block_dialogs','block_layers',
        'block_actions','block_versions','floor_area','urbanism_ui','viewport_ui',
        'rut_runtime.rut_bootstrap']}, indent=2))
print(json.dumps({'passed':sum(r['passed'] for r in results), 'total':len(results),
                  'active_objects_after':len(list(doc.Objects))}))
