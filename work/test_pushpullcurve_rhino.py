"""Run in the intended Rhino document through MCP. Creates no document geometry."""
import importlib.util
import math
import Rhino
import scriptcontext as sc

spec = importlib.util.spec_from_file_location('pushpull_test', r'C:\Projects\rhino-urbanism\PushPullCurve.py')
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)
plane = Rhino.Geometry.Plane.WorldXY
checks = []


def check(value, message):
    if not value:
        raise AssertionError(message)
    checks.append(message)


def calculate(points, distance, index=0, allow=True, closed=True, tol=0.001):
    result = pp.compute_push_result(points, closed, index, Rhino.Geometry.Point3d.Origin,
        plane, tol, allow, distance)
    if result['ok'] and not result['delete_curve']:
        curve = Rhino.Geometry.PolylineCurve(pp.polyline_2d_to_3d(result['new_points_2d'], plane, closed))
        check(curve.IsValid, 'Rhino valid result')
        check(curve.IsClosed == closed, 'Rhino closure preserved')
        if closed:
            events = Rhino.Geometry.Intersect.Intersection.CurveSelf(curve, tol)
            check(events is None or events.Count == 0, 'Rhino no self intersections')
        curve.Dispose()
    return result


square = [(0., 0.), (10., 0.), (10., 10.), (0., 10.)]
stairs = [(0.,0.),(10.,0.),(10.,2.),(12.,4.),(12.,6.),(14.,8.),
          (14.,12.),(-4.,12.),(-4.,8.),(-2.,6.),(-2.,4.),(0.,2.)]
check(calculate(square, 2)['new_points_2d'][:2] == [(0.,2.),(10.,2.)], 'ordinary inward move')
check(calculate(square, -3)['new_points_2d'][:2] == [(0.,-3.),(10.,-3.)], 'ordinary outward move')
for distance in [10.,12.]:
    check(calculate(square, distance)['delete_curve'], 'rectangle full collapse')
triangle = [(0.,0.),(10.,0.),(5.,5.)]
check(not calculate(triangle, 4)['delete_curve'], 'triangle before collapse')
check(calculate(triangle, 6)['delete_curve'], 'triangle beyond collapse')
for distance, removed in [(1.,0),(2.,2),(3.,2),(4.,4),(5.,4),(6.,6),(7.,6),(9.,8)]:
    r = calculate(stairs, distance)
    check(r['ok'] and len(r['removed_indices']) == removed, 'stairs removal at {}'.format(distance))
    check(abs(r['new_points_2d'][0][1] - distance) < 0.001, 'moves to requested distance')
for shift in range(len(stairs)):
    rotated = stairs[shift:] + stairs[:shift]
    r = calculate(rotated, 7, (-shift) % len(stairs))
    check(r['ok'] and len(r['removed_indices']) == 6, 'seam-independent result')
reverse = list(reversed(stairs))
check(len(calculate(reverse, -7, len(stairs)-2)['removed_indices']) == 6, 'clockwise loop')
check(calculate(stairs, 7, allow=False)['blocked'], 'AllowCollapse=No blocks removal')
check(calculate(square, 11, allow=False)['blocked'], 'AllowCollapse=No blocks full collapse')
cut_corner = [(0.,2.),(2.,0.),(10.,0.),(10.,10.),(0.,10.)]
r = calculate(cut_corner, -4)
check(r['ok'] and not r['delete_curve'] and r['removed_indices'] == [0], 'selected edge collapse keeps rest')
check(len(r['new_points_2d']) == 4, 'selected edge collapse has four remaining edges')
u_shape = [(0.,0.),(10.,0.),(10.,10.),(6.,10.),(6.,3.),(4.,3.),(4.,10.),(0.,10.)]
check(calculate(u_shape, 2)['ok'], 'concave loop before collision')
check(calculate(u_shape, 4)['blocked'], 'nonlocal collision blocked')
check(calculate(u_shape, 20)['blocked'], 'large typed jump cannot tunnel through boundary')
check(calculate([(0.,0.),(10.,10.),(0.,10.),(10.,0.)], 2)['blocked'], 'self-crossing input rejected')
for scale in [0.01, 1000.]:
    scaled = [(x * scale + 100000, y * scale - 80000) for x,y in stairs]
    check(len(calculate(scaled, 7*scale, tol=0.00001*scale)['removed_indices']) == 6,
          'scale and translation robustness')
open_points = [(0.,5.),(0.,0.),(10.,0.),(10.,5.)]
check(calculate(open_points, 2, index=1, closed=False)['ok'], 'open polyline regression')
check(calculate(open_points, 2, index=0, closed=False)['ok'], 'open end regression')

# Pick projection on a tilted plane must produce the same planar result.
tilted = Rhino.Geometry.Plane(Rhino.Geometry.Point3d(10,20,30), Rhino.Geometry.Vector3d(1,2,3))
point = pp.plane_uv_to_point3d((5,7), tilted)
r = pp.compute_push_result(stairs, True, 0, point, tilted, 0.001, True)
check(r['ok'] and len(r['removed_indices']) == 6, 'tilted plane spatial pick')

print('PUSHPULL: {} checks passed in Rhino {}'.format(len(checks), Rhino.RhinoApp.Version))

# Offset follows the cursor anywhere along an oblique edge, including beyond
# its endpoints. Tangential movement must never change perpendicular distance.
oblique = [(0.,0.), (8.,6.), (2.,14.), (-6.,8.)]
tangent, normal = (0.8,0.6), (-0.6,0.8)
for test_plane in [plane, tilted]:
    for along in [-20., -4., 0., 4., 20.]:
        for offset in [-2., 0.5, 2.]:
            uv = (4 + along*tangent[0] + offset*normal[0],
                  3 + along*tangent[1] + offset*normal[1])
            pick = pp.plane_uv_to_point3d(uv, test_plane)
            r = pp.compute_push_result(oblique, True, 0, pick, test_plane, 0.001, True)
            check(abs(r['signed_distance'] - offset) < 1e-8, 'off-midpoint perpendicular offset')
            start, end = r['preview_segment_start'], r['preview_segment_end']
            check(abs(pp.vec2_cross(pp.vec2_sub(uv,start), pp.vec2_unit(pp.vec2_sub(end,start)))) < 1e-8,
                  'preview support line passes through cursor')

ortho_before = Rhino.ApplicationSettings.ModelAidSettings.Ortho
picker = pp.create_distance_picker(Rhino.Geometry.Point3d.Origin, tilted)
picker.Dispose()
check(Rhino.ApplicationSettings.ModelAidSettings.Ortho == ortho_before, 'global Ortho setting preserved')
print('PUSHPULL OFFSET: {} total checks passed'.format(len(checks)))


def extrusion(points, distance, index=0, explicit=False, closed=True, allow=True):
    r = pp.compute_push_result(points, closed, index, Rhino.Geometry.Point3d.Origin,
        plane, 0.001, allow, distance, extrude=explicit)
    if r['ok'] and not r['delete_curve']:
        curve = Rhino.Geometry.PolylineCurve(pp.polyline_2d_to_3d(r['new_points_2d'], plane, closed))
        check(curve.IsValid and curve.IsClosed == closed, 'extrusion Rhino valid and closure preserved')
        events = Rhino.Geometry.Intersect.Intersection.CurveSelf(curve, 0.001)
        check(events is None or events.Count == 0, 'extrusion Rhino no self intersections')
        curve.Dispose()
    return r


split = [(0.,0.),(5.,0.),(10.,0.),(12.,8.),(-2.,8.)]
for distance in [-2.,2.]:
    r = extrusion(split, distance)
    check(r['ok'] and r['added_connectors'] == 1, 'automatic collinear connector')
    check(r['removed_indices'] == [], 'collinear neighbour retained')
    check(r['new_points_2d'][1:4] == [(5.,distance),(5.,0.),(10.,0.)], 'shared vertex and neighbour fixed')
    check(r['new_points_2d'][0] == (-distance/4.,distance), 'angled neighbour extends normally')
    check(extrusion(split, distance, allow=False)['ok'], 'adding connector independent of AllowCollapse')
    r = extrusion(split, distance, explicit=True)
    check(r['ok'] and r['added_connectors'] == 2, 'explicit includes angled end and collinear end')
    check(r['new_points_2d'][0] == (0.,distance), 'explicit start translates perpendicularly')

middle_split = [(0.,0.),(3.,0.),(7.,0.),(10.,0.),(12.,8.),(-2.,8.)]
for distance in [-2.,2.]:
    r = extrusion(middle_split, distance, index=1)
    check(r['ok'] and r['added_connectors']==2, 'automatic connectors on both collinear ends')
    check(len(r['new_points_2d'])==len(middle_split)+2, 'two new vertices')

sloped = [(0.,0.),(10.,0.),(12.,8.),(-2.,8.)]
for distance in [-3.,2.]:
    r = extrusion(sloped, distance, explicit=True)
    check(r['ok'] and r['added_connectors']==2, 'explicit two perpendicular connectors')
    check(r['new_points_2d'] == [(0.,distance),(10.,distance),(10.,0.),(12.,8.),(-2.,8.),(0.,0.)],
          'explicit preserves every stationary vertex')
    for shift in range(len(sloped)):
        rotated = sloped[shift:]+sloped[:shift]
        check(extrusion(rotated,distance,(-shift)%len(sloped),True)['ok'], 'explicit across closure seam')
    reverse = list(reversed(sloped))
    check(extrusion(reverse,-distance,len(sloped)-2,True)['added_connectors']==2, 'clockwise explicit extrusion')

for distance in [-2.,2.]:
    check(extrusion(square,distance,explicit=True)['ok'], 'existing perpendicular sides remain valid')
check(extrusion(u_shape,20,explicit=True)['blocked'], 'explicit cannot tunnel across boundary')
check(extrusion(sloped,0,explicit=True)['new_points_2d']==sloped, 'zero distance leaves original vertices')
open_split = [(-2.,8.),(0.,0.),(5.,0.),(10.,0.),(12.,8.)]
check(extrusion(open_split,-2,index=1,closed=False)['added_connectors']==1, 'open automatic connector')
check(extrusion(open_split,2,index=1,closed=False,explicit=True)['added_connectors']==2, 'open explicit connectors')
check(extrusion([(0.,0.),(5.,0.),(10.,4.)],-2,index=0,closed=False,explicit=True)['ok'], 'open free endpoint')

print('PUSHPULL EXTRUSION: {} total checks passed'.format(len(checks)))

# Exercise native Rhino option registration alongside numeric point input.
picker = pp.create_distance_picker(Rhino.Geometry.Point3d.Origin, plane)
toggle = Rhino.Input.Custom.OptionToggle(False, 'No', 'Yes')
try:
    registered = picker.AddOptionToggle('Extrude', toggle)
    check(registered[0] > 0, 'native Extrude toggle registers')
    registered[1].CurrentValue = True
    check(pp.option_toggle_to_bool(toggle), 'native Extrude toggle value readable')
finally:
    picker.Dispose()
print('PUSHPULL FINAL: {} total checks passed'.format(len(checks)))
