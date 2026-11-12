#! python 3
"""Load the candidate only in the explicitly opened phase 5 practice document."""
import json
from pathlib import Path
import Rhino
import scriptcontext as sc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/phase5-validation'
doc = globals().get('__rhino_doc__') or sc.doc
assert Path(doc.Path).resolve() == (OUT/'RUT-beta-hands-on.3dm').resolve()
aliases = [n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames() if n.upper().startswith('RUT')]
assert not aliases, 'Use a clean test profile; leave normal aliases alone.'
before = [(str(o.Id), o.Geometry.DataCRC(0)) for o in doc.Objects]
installation = json.loads((ROOT/'work/phase4-validation/installation.json').read_text())
rhp = Path(installation['plugin_files'][0])
loaded = Rhino.PlugIns.PlugIn.LoadPlugIn(str(rhp))
assert loaded
toolbar = Rhino.RhinoApp.ToolbarFiles.FindByPath(str(rhp.with_suffix('.rui')))
if toolbar is None:
    toolbar = Rhino.RhinoApp.ToolbarFiles.Open(str(rhp.with_suffix('.rui')))
assert toolbar is not None
Rhino.RhinoApp.RunScript('_SetView _World _Top', False)
Rhino.RhinoApp.RunScript('_Zoom _Extents', False)
if hasattr(doc.Views.ActiveView, 'Maximized'):
    doc.Views.ActiveView.Maximized = True
doc.Views.Redraw()
assert before == [(str(o.Id), o.Geometry.DataCRC(0)) for o in doc.Objects]
names = [n for n in Rhino.Commands.Command.GetCommandNames(True, False) if n.startswith('RUT')]
assert len(names) == 18
report = {'version': installation['active_version'], 'plugin': str(rhp),
    'rhino': str(Rhino.RhinoApp.Version), 'drawing': doc.Path,
    'commands': names, 'aliases': aliases, 'geometry_unchanged': True,
    'manual_acceptance': 'Pending', 'setup_issue': 'Floating-toolbar setup crash remains unresolved'}
(OUT/'handoff.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
Rhino.RhinoApp.WriteLine('RUT phase 5: practice drawing ready. Follow BETA_HANDS_ON_TESTS.md.')
