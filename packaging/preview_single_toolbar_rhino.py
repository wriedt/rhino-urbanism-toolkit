#! python 3
"""Review the rebuilt RUI in a running test session without restarting its plugin."""
import json
import re
from pathlib import Path
import Rhino
import scriptcontext as sc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/phase4-validation'
doc = globals().get('__rhino_doc__') or sc.doc
assert not list(doc.Objects), 'Use the empty toolbar-validation drawing only.'
before = doc.Modified
installation = json.loads((OUT/'installation.json').read_text())
rhp = Path(installation['plugin_files'][0])
preview = OUT/'toolbar-preview/RUT-single-toolbar.rui'
preview.parent.mkdir(exist_ok=True)
# A running plugin can retain an older bound RUI. This review-only copy avoids
# that binding, retaining the actual final toolbar, macro and icon definitions.
preview.write_text(re.sub(r' plug_in_guid="[^"]+"', '',
    rhp.with_suffix('.rui').read_text(encoding='utf-8-sig')), encoding='utf-8')
opened = Rhino.RhinoApp.ToolbarFiles.Open(str(preview))
assert opened is not None
report = {'version': installation['active_version'], 'preview': str(preview),
    'loaded_path': str(opened.Path),
    'toolbars': [opened.GetToolbar(i).Name for i in range(opened.ToolbarCount)],
    'document_unchanged': not list(doc.Objects) and doc.Modified == before}
assert len(report['toolbars']) == 1
assert report['toolbars'][0] == 'RUT | Rhino Urbanism Toolkit'
assert report['document_unchanged']
(OUT/'single-toolbar.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
