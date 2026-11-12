#! python 3
"""Run only in the dedicated RUTBetaValidation Rhino process."""
import json
from pathlib import Path
import sys
import traceback
import Rhino
import scriptcontext as sc
from System import Guid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/phase4-validation'
installation = json.loads((OUT / 'installation.json').read_text())
rhp = Path(installation['plugin_files'][0])
doc = globals().get('__rhino_doc__') or sc.doc
report = {'process': __import__('System').Diagnostics.Process.GetCurrentProcess().Id,
          'rhino': str(Rhino.RhinoApp.Version), 'plugin_path': str(rhp),
          'source_paths_before': [p for p in sys.path if str(ROOT).lower() in p.lower()]}
def source_guard(event, args):
    if event == 'open' and isinstance(args[0], str):
        path = Path(args[0]).resolve()
        if path.suffix.lower() in ('.py', '.pyc') and ROOT in path.parents:
            if OUT not in path.parents and (ROOT / 'packaging') not in path.parents:
                raise PermissionError('Source checkout access disabled for installed-package validation')
sys.addaudithook(source_guard)
try:
    try:
        with open(ROOT / 'layer_tools.py'):
            report['source_access_blocked'] = False
    except PermissionError:
        report['source_access_blocked'] = True
    loaded = Rhino.PlugIns.PlugIn.LoadPlugIn(str(rhp))
    report['load_result'] = str(loaded)
    report['rut_aliases'] = [n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames()
                             if n.upper().startswith('RUT')]
    previous = sc.doc
    sc.doc = doc
    try:
        report['run_show_layers'] = Rhino.RhinoApp.RunScript('_RUTShowAllLayers', False)
    finally:
        sc.doc = previous
    report['modules'] = {name: getattr(module, '__file__', None) for name, module in sys.modules.items()
                         if name in ['rut_runtime.rut_bootstrap', 'layer_tools', 'urbanism_ui',
                                     'block_dialogs', 'floor_area']}
    report['command_history'] = Rhino.RhinoApp.CommandHistoryWindowText[-5000:]
except Exception:
    report['error'] = traceback.format_exc()
(OUT / 'probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
