"""Read-only checks and native preview captures on the user's actual curves."""
import importlib.util
import Rhino
import System.Drawing
import System.Drawing.Imaging

spec=importlib.util.spec_from_file_location('pp_live_mixed',r'C:\Projects\rhino-urbanism\PushPullCurve.py')
pp=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
doc=__rhino_doc__
before={obj.Id for obj in doc.Objects}
view=doc.Views.ActiveView
vp=view.ActiveViewport
camera_before=(vp.CameraLocation,vp.CameraDirection,vp.CameraUp,vp.CameraTarget)
cases=0
preview_source=None
preview_distance=None

for obj in list(doc.Objects):
    curve=obj.Geometry
    if not isinstance(curve,Rhino.Geometry.Curve) or curve.TryGetPolyline()[0]:continue
    ok,plane=curve.TryGetPlane()
    if not ok:continue
    context=pp.mixed_curves.MixedCurveEdit(curve,plane,doc.ModelAbsoluteTolerance)
    try:
        distance=curve.GetBoundingBox(True).Diagonal.Length*0.04
        for index,segment in enumerate(context.segments):
            if not context.linear[index]:continue
            pick=segment.PointAtNormalizedLength(0.5)
            assert context.select_line(pick)
            for signed in [-distance,distance]:
                for explicit in [False,True]:
                    result=context.compute(pick,signed,explicit)
                    try:
                        assert result['blocked'] or (result['new_curve'].IsValid and
                            result['new_curve'].IsClosed==curve.IsClosed)
                        if (preview_source is None and not explicit and result['ok'] and
                                result['trimmed_curves']):
                            preview_source=(obj.Id,index,pick,plane)
                            preview_distance=signed
                        cases+=1
                    finally:pp.mixed_curves.dispose_result(result)
    finally:context.dispose()

if preview_source is not None:
    obj_id,index,pick,plane=preview_source
    context=pp.mixed_curves.MixedCurveEdit(doc.Objects.FindId(obj_id).Geometry,plane,doc.ModelAbsoluteTolerance)
    context.select_line(pick)
    preview=pp.PushPreview(context.line_points_2d(),context.closed,plane,str(doc.ModelUnitSystem))
    preview.mixed=context
    conduit=pp.TypedPreview(doc,preview,True)
    try:
        for explicit,name in [(False,'trim'),(True,'extrude')]:
            conduit.result=context.compute(pick,preview_distance,explicit)
            try:
                assert conduit.result['ok'],conduit.result['message']
                conduit.Enabled=True
                doc.Views.Redraw()
                bitmap=view.CaptureToBitmap(System.Drawing.Size(1280,720))
                try:bitmap.Save(r'C:\Projects\rhino-urbanism\work\pushpull-mixed-'+name+'.png',System.Drawing.Imaging.ImageFormat.Png)
                finally:bitmap.Dispose()
            finally:
                conduit.Enabled=False
                pp.mixed_curves.dispose_result(conduit.result)
    finally:
        conduit.Enabled=False
        preview.dispose()
        context.dispose()
        doc.Views.Redraw()
assert before=={obj.Id for obj in doc.Objects}
assert camera_before==(vp.CameraLocation,vp.CameraDirection,vp.CameraUp,vp.CameraTarget)
print('PUSHPULL LIVE MIXED: {} cases checked; model and camera preserved'.format(cases))
