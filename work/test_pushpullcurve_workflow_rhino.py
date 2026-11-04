"""Final Rhino workflow checks. Only test-created objects are edited/deleted."""
import importlib.util
import os
import Rhino
import scriptcontext as sc
import System

doc = __rhino_doc__
original_context = sc.doc
sc.doc = doc
spec = importlib.util.spec_from_file_location('pp_workflow', r'C:\Projects\rhino-urbanism\PushPullCurve.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
# Optional one-time comparison; future workflow runs need no archived source.
baseline = None
baseline_path = os.path.join(os.environ['TEMP'], 'rhino-pushpull-cleanup-before.py')
if os.path.exists(baseline_path):
    baseline_spec = importlib.util.spec_from_file_location('pp_before_cleanup', baseline_path)
    baseline = importlib.util.module_from_spec(baseline_spec)
    baseline_spec.loader.exec_module(baseline)
plane = Rhino.Geometry.Plane.WorldXY
square = [(0.,0.),(10.,0.),(10.,10.),(0.,10.)]
split = [(0.,0.),(5.,0.),(10.,0.),(12.,8.),(-2.,8.)]
stairs = [(0.,0.),(10.,0.),(10.,2.),(12.,4.),(12.,6.),(14.,8.),
          (14.,12.),(-4.,12.),(-4.,8.),(-2.,6.),(-2.,4.),(0.,2.)]
selection = [obj.Id for obj in doc.Objects.GetSelectedObjects(False, False)]
original_ids = {obj.Id for obj in doc.Objects}
fixtures = []
checks = []


def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def compute(points, distance, explicit=False):
    return pp.compute_push_result(points, True, 0, Rhino.Geometry.Point3d.Origin,
        plane, doc.ModelAbsoluteTolerance, True, distance, extrude=explicit)


def fixture(points):
    attributes = Rhino.DocObjects.ObjectAttributes()
    attributes.Name = 'PUSHPULL_CLEANUP_TEST'
    attributes.SetUserString('preserve', 'metadata')
    curve = Rhino.Geometry.PolylineCurve(pp.polyline_2d_to_3d(points, plane, True))
    try:
        obj_id = doc.Objects.AddCurve(curve, attributes)
        fixtures.append(obj_id)
        return doc.Objects.FindId(obj_id)
    finally:
        attributes.Dispose()
        curve.Dispose()


class EventHook:
    def __init__(self):
        self.handlers = []
    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self
    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self


class ScriptedPointInput:
    """Feed command outcomes to the real picker workflow; no Windows input."""
    def __init__(self, events):
        self.events = list(events)
        self.DynamicDraw = EventHook()
        self.disposed = False
        self.kind = None
    def AddOptionToggle(self, name, toggle):
        self.toggle = toggle
    def Get(self):
        self.kind, self.value = self.events.pop(0)
        if self.kind == 'Raise':
            raise RuntimeError('simulated input failure')
        if self.kind == 'Option':
            self.toggle.CurrentValue = self.value
        return getattr(Rhino.Input.GetResult, self.kind)
    def Number(self):
        return self.value
    def Point(self):
        return pp.plane_uv_to_point3d(self.value, plane)
    def CommandResult(self):
        return Rhino.Commands.Result.Cancel if self.kind == 'Cancel' else Rhino.Commands.Result.Success
    def AcceptNothing(self, value):
        pass
    def SetCommandPrompt(self, value):
        pass
    def Dispose(self):
        self.disposed = True


native_picker = pp.create_distance_picker
native_conduit = pp.TypedPreview
native_preview = pp.PushPreview
native_confirm = pp.confirm_curve_deletion
previews, conduits = [], []


def track_preview(*args):
    result = native_preview(*args)
    previews.append(result)
    return result


def track_conduit(*args):
    # Its IronPython-compatible super() refers to the exported class name.
    pp.TypedPreview = native_conduit
    try:
        result = native_conduit(*args)
    finally:
        pp.TypedPreview = track_conduit
    conduits.append(result)
    return result


try:
    # Compare the geometry contract with the exact pre-cleanup source, including
    # seam indices, directions, removal limits and explicit extrusion settings.
    for points in [square,split,stairs] if baseline is not None else []:
        for index in range(len(points)):
            for distance in [-20.,-2.,0.,2.,20.]:
                for explicit in [False,True]:
                    args = (points,True,index,Rhino.Geometry.Point3d.Origin,plane,
                            doc.ModelAbsoluteTolerance,True,distance)
                    check(pp.compute_push_result(*args,extrude=explicit) ==
                          baseline.compute_push_result(*args,extrude=explicit),
                          'pre-cleanup geometry preserved')

    obj = fixture(split)
    original_id = obj.Id
    check(pp.apply_push_result(doc,obj,compute(split,-2),plane,True) == Rhino.Commands.Result.Success,
          'replace commits automatic connector')
    edited = doc.Objects.FindId(original_id)
    check(edited.Id == original_id and edited.Attributes.GetUserString('preserve') == 'metadata',
          'replacement preserves identity and metadata')
    check(edited.Geometry.IsClosed and edited.Geometry.PointCount == 7, 'replacement geometry has connector')

    obj = fixture(split)
    before_copy = {item.Id for item in doc.Objects}
    check(pp.apply_push_result(doc,obj,compute(split,-2,True),plane,True,False) == Rhino.Commands.Result.Success,
          'copy commits explicit extrusion')
    copy_ids = {item.Id for item in doc.Objects} - before_copy
    fixtures.extend(copy_ids)
    check(len(copy_ids)==1, 'copy adds exactly one curve')
    copy = doc.Objects.FindId(next(iter(copy_ids)))
    check(copy.Attributes.GetUserString('preserve')=='metadata' and copy.Geometry.PointCount==8,
          'copy preserves attributes and both connectors')
    check(doc.Objects.FindId(obj.Id).Geometry.PointCount==6, 'copy retains original geometry')

    obj = fixture(square)
    pp.confirm_curve_deletion = lambda document: False
    check(pp.apply_push_result(doc,obj,compute(square,20),plane,True)==Rhino.Commands.Result.Cancel,
          'declining whole-curve deletion cancels')
    check(doc.Objects.FindId(obj.Id) is not None, 'declined deletion keeps curve')
    pp.confirm_curve_deletion = lambda document: True
    check(pp.apply_push_result(doc,obj,compute(square,20),plane,True)==Rhino.Commands.Result.Success,
          'confirmed whole-curve deletion commits')
    check(doc.Objects.FindId(obj.Id) is None, 'confirmed deletion removes curve')
    obj = fixture(square)
    check(pp.apply_push_result(doc,obj,compute(square,20),plane,True,False)==Rhino.Commands.Result.Cancel,
          'whole-curve collapse with Replace=No keeps original')
    check(pp.apply_push_result(doc,obj,compute(square,0),plane,True)==Rhino.Commands.Result.Cancel,
          'zero-distance commit cancels')

    pp.PushPreview, pp.TypedPreview = track_preview, track_conduit
    for events, connectors in [
            ([('Point',(2.5,-2.))],1),
            ([('Number',-2.),('Nothing',None)],1),
            ([('Number',-2.),('Option',True),('Nothing',None)],2),
            ([('Option',True),('Number',-2.),('Nothing',None)],2),
            ([('Cancel',None)],None)]:
        picker = ScriptedPointInput(events)
        pp.create_distance_picker = lambda *args: picker
        outcome, result = pp.pick_push_distance(doc,split,True,0,plane,True,True,False)
        if connectors is None:
            check(outcome==Rhino.Commands.Result.Cancel and result is None, 'Escape cancels picker')
        else:
            check(outcome==Rhino.Commands.Result.Success and result['added_connectors']==connectors,
                  'click/number/Extrude review workflow')
        check(picker.disposed and not picker.DynamicDraw.handlers, 'point picker and event handler cleaned')
        check(not conduits[-1].Enabled and previews[-1].bitmap is None, 'temporary preview cleaned')

    picker = ScriptedPointInput([('Number',-2.),('Raise',None)])
    pp.create_distance_picker = lambda *args: picker
    try:
        pp.pick_push_distance(doc,split,True,0,plane,True,False,False)
        raise AssertionError('Expected simulated exception')
    except RuntimeError:
        check(picker.disposed and not conduits[-1].Enabled and previews[-1].bitmap is None,
              'input error cleans preview and picker')
finally:
    pp.create_distance_picker, pp.TypedPreview, pp.PushPreview = native_picker,native_conduit,native_preview
    pp.confirm_curve_deletion = native_confirm
    for conduit in conduits:
        conduit.Enabled = False
    for preview in previews:
        preview.dispose()
    for obj_id in fixtures:
        if doc.Objects.FindId(obj_id):
            doc.Objects.Delete(obj_id,True)
    doc.Objects.UnselectAll()
    for obj_id in selection:
        doc.Objects.Select(obj_id)
    doc.Views.Redraw()
    sc.doc = original_context

check({obj.Id for obj in doc.Objects} == original_ids, 'original document objects preserved')
print('PUSHPULL WORKFLOW: {} checks passed; all fixtures and overlays removed'.format(len(checks)))
