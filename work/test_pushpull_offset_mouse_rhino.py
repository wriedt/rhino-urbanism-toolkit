"""Interactive integration probe: click empty viewport space; no model edits."""
import importlib.util
import Rhino
import scriptcontext as sc
import clr
clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import Cursor

spec = importlib.util.spec_from_file_location('pp_mouse_test', r'C:\Projects\rhino-urbanism\PushPullCurve.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
plane = Rhino.Geometry.Plane.WorldXY
mode = sc.sticky.get('pushpull_mouse_test_mode', 'fixed')
if mode == 'baseline':
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetBasePoint(Rhino.Geometry.Point3d.Origin, False)
    gp.Constrain(plane, False)
else:
    gp = pp.create_distance_picker(Rhino.Geometry.Point3d.Origin, plane)
gp.SetCommandPrompt('Cursor regression check: click empty space away from the axes')
try:
    outcome = gp.Get()
    if outcome == Rhino.Input.GetResult.Point:
        view = __rhino_doc__.Views.ActiveView
        client = view.ScreenToClient(Cursor.Position)
        ray = view.ActiveViewport.ClientToWorld(client)
        ok, parameter = Rhino.Geometry.Intersect.Intersection.LinePlane(ray, plane)
        assert ok
        expected = ray.PointAt(parameter)
        actual = gp.Point()
        error = expected.DistanceTo(actual)
        print('{}: raw plane point={}, picked={}, error={:.9f}, global Ortho={}'.format(
            mode, expected, actual, error, Rhino.ApplicationSettings.ModelAidSettings.Ortho))
        sc.sticky['pushpull_mouse_test_' + mode] = error
        if mode == 'fixed':
            assert error < 1e-6, 'Picked point must match cursor projected onto curve plane'
    else:
        print('Mouse test cancelled')
finally:
    gp.Dispose()
