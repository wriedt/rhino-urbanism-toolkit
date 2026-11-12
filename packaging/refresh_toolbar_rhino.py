#! python 3
"""Refresh only RUT's toolbar; preserve the open validation drawing."""
import json
import re
from pathlib import Path
import Rhino
import scriptcontext as sc
from System import Guid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/phase4-validation'
installation=json.loads((OUT/'installation.json').read_text())
packaged_rui=Path(installation['plugin_files'][0]).with_suffix('.rui')
# A running Rhino 8 plugin keeps its original bound RUI file open. Import a
# standalone review copy to refresh this window without unloading the plugin.
preview=OUT/'toolbar-preview'
preview.mkdir(exist_ok=True)
rui=preview/'RUT.rui'
rui.write_text(re.sub(r' plug_in_guid="[^"]+"','',packaged_rui.read_text(encoding='utf-8')),encoding='utf-8')
doc=globals().get('__rhino_doc__') or sc.doc
def snapshot():
    return (doc.Modified, [(str(o.Id), o.Geometry.DataCRC(0), o.IsSelected(False)) for o in doc.Objects])
before=snapshot()
identifier=Guid('6ac6211b-d98c-47f5-95c0-5a542d379a2c')
previous=[]
for opened in list(Rhino.RhinoApp.ToolbarFiles):
    if 'rhino-urbanism-toolkit' in str(opened.Path).lower() or opened.Id==identifier:
        previous.append({'id':str(opened.Id),'path':str(opened.Path)})
        for index in range(opened.GroupCount):
            opened.GetGroup(index).Visible=False
        opened.Close(False)
toolbar=Rhino.RhinoApp.ToolbarFiles.Open(str(rui))
assert toolbar is not None
for i in range(toolbar.GroupCount):
    toolbar.GetGroup(i).Visible=True
report={'rui':str(rui),'loaded_path':str(toolbar.Path),'previous_files':previous, 'groups':[toolbar.GetGroup(i).Name for i in range(toolbar.GroupCount)],
        'categories':[toolbar.GetToolbar(i).Name for i in range(toolbar.ToolbarCount)],
        'drawing_unchanged':before==snapshot()}
(OUT/'toolbar-categories.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
