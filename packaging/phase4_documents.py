#! python 3
"""Installed inspector document ownership checks in the isolated empty process."""
import json
from pathlib import Path
import Rhino
import scriptcontext as sc

OUT = Path(__file__).resolve().parents[1] / 'work/phase4-validation'
doc = globals().get('__rhino_doc__') or sc.doc
assert not list(doc.Objects)
report = {}
try:
    Rhino.RhinoApp.RunScript('_RUTFloorArea', False)
    key = 'RUT.FloorArea.' + str(doc.RuntimeSerialNumber)
    controller = sc.sticky[key]
    Rhino.RhinoApp.RunScript('_RUTFloorArea', False)
    report['repeat_reuses_controller'] = sc.sticky[key] is controller
    other = Rhino.RhinoDoc.CreateHeadless(None)
    try:
        # Changes from a different document must not invalidate this inspector.
        controller.dirty = False
        other.Objects.AddPoint(Rhino.Geometry.Point3d.Origin)
        report['other_document_events_ignored'] = not controller.dirty
    finally:
        other.Dispose()
    report['other_document_close_ignored'] = not controller.closed
    controller.form.Close()
    report['close_clears_controller'] = controller.closed and key not in sc.sticky
    report['close_detaches_events'] = not controller.subscriptions
    # Inspect clipboard format names only. Complex clipboard payloads must not
    # be replaced for a test. No live OLE data object is retained/restored.
    from System.Windows import Clipboard
    try:
        data = Clipboard.GetDataObject()
        formats = list(data.GetFormats(False)) if data else []
        del data
        report['clipboard_formats'] = formats
        text_formats = {'Text','UnicodeText','System.String','OEMText','Locale'}
        report['clipboard_test_safe'] = all(f in text_formats for f in formats)
    except Exception as error:
        report['clipboard_test_safe'] = False
        report['clipboard_probe_error'] = str(error)
    report['active_objects_after'] = len(list(doc.Objects))
finally:
    controller = sc.sticky.get('RUT.FloorArea.'+str(doc.RuntimeSerialNumber))
    if controller:
        controller.form.Close()
    (OUT/'document-lifecycle.json').write_text(json.dumps(report,indent=2))
