#! python 3
"""Leave the tested private candidate ready in the isolated validation window."""
import json
from pathlib import Path
import Rhino
import scriptcontext as sc
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/phase4-validation'
installation = json.loads((OUT/'installation.json').read_text())
rhp = Path(installation['plugin_files'][0])
doc = globals().get('__rhino_doc__') or sc.doc
assert not list(doc.Objects)
loaded = Rhino.PlugIns.PlugIn.LoadPlugIn(str(rhp))
Rhino.RhinoApp.RunScript('_RUTShowAllLayers', False)
rui = rhp.with_suffix('.rui')
toolbar = Rhino.RhinoApp.ToolbarFiles.FindByPath(str(rui))
if toolbar is None:
    toolbar = Rhino.RhinoApp.ToolbarFiles.Open(str(rui))
for i in range(toolbar.GroupCount):
    toolbar.GetGroup(i).Visible = True
path = OUT/'RUT-beta-validation.3dm'
if not path.exists():
    options = Rhino.FileIO.FileWriteOptions()
    options.UpdateDocumentPath = True
    options.SuppressDialogBoxes = True
    assert doc.WriteFile(str(path), options)
doc.Modified = False
report = {'version':installation['active_version'], 'load':str(loaded),
          'commands': [n for n in Rhino.Commands.Command.GetCommandNames(True,False) if n.startswith('RUT')],
          'rut_aliases':[n for n in Rhino.ApplicationSettings.CommandAliasList.GetNames() if n.upper().startswith('RUT')],
          'toolbar': str(rui), 'active_objects':len(list(doc.Objects)),
          'test_drawing':str(path), 'document_name':doc.Name}
(OUT/'handoff.json').write_text(json.dumps(report,indent=2))
Rhino.RhinoApp.WriteLine('RUT beta candidate ready. Use copies of drawings for phase 5 checks.')
