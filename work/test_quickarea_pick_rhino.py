"""Exercise direct native selection with no opening confirmation dialog."""
import runpy
import scriptcontext as sc
import Rhino
import Eto.Forms as forms

doc = __rhino_doc__
sc.doc = doc
q = runpy.run_path(r'C:\Projects\rhino-urbanism\QuickArea.py', run_name='qa_pick_test')
selected = [o.Id for o in doc.Objects.GetSelectedObjects(False, False)]
fixture = doc.Objects.AddBrep(Rhino.Geometry.Box(Rhino.Geometry.Plane.WorldXY,
    Rhino.Geometry.Interval(0,1), Rhino.Geometry.Interval(0,1),
    Rhino.Geometry.Interval(0,3)).ToBrep())
doc.Objects.UnselectAll()
messages = []
feed, watchdog = forms.UITimer(), forms.UITimer()
feed.Interval, watchdog.Interval = 0.7, 5.0

def send(sender, event):
    feed.Stop()
    messages.append(('selection_command', Rhino.RhinoApp.RunScript(
        '_SelID ' + str(fixture) + ' _Enter', False)))

def timeout(sender, event):
    watchdog.Stop()
    messages.append(('watchdog',))
    Rhino.RhinoApp.RunScript('!', False)

feed.Elapsed += send
watchdog.Elapsed += timeout
try:
    feed.Start()
    watchdog.Start()
    picked = q['select_objects'](doc)
    watchdog.Stop()
    assert picked == [fixture], picked
    print('DIRECT_PICK_PASS', True)
    print('PRESELECTION_PASS', q['select_objects'](doc) == [fixture])
    print('PICK_COMMANDS', messages)
finally:
    for timer in [feed, watchdog]:
        timer.Stop()
        timer.Dispose()
    doc.Objects.Delete(fixture, True)
    doc.Objects.UnselectAll()
    for object_id in selected:
        doc.Objects.Select(object_id)
    doc.Views.Redraw()
