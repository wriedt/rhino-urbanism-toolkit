#! python 3
import json
from pathlib import Path
import traceback
import Rhino
import scriptcontext as sc
OUT = Path(__file__).resolve().parents[1] / 'work/phase4-validation'
doc = globals().get('__rhino_doc__') or sc.doc
assert not list(doc.Objects) and not doc.Modified
report = {}
try:
    Rhino.RhinoApp.RunScript('_RUTFloorArea', False)
    key = 'RUT.FloorArea.' + str(doc.RuntimeSerialNumber)
    controller = sc.sticky[key]
    report['old_document'] = doc.RuntimeSerialNumber
    report['new_command_dispatched'] = Rhino.RhinoApp.RunScript('_-New _None', False)
    report['new_document'] = Rhino.RhinoDoc.ActiveDoc.RuntimeSerialNumber
    report['owner_close_cleans_controller'] = controller.closed and key not in sc.sticky
    report['owner_close_detaches_events'] = not controller.subscriptions
    report['new_document_empty'] = not list(Rhino.RhinoDoc.ActiveDoc.Objects)
except Exception:
    report['error'] = traceback.format_exc()
(OUT/'owner-close.json').write_text(json.dumps(report,indent=2))
