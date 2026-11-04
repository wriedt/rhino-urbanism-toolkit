# -*- coding: utf-8 -*-
"""Push/pull a straight section of a planar curve in Rhino 8.

Normal mode extends/trims neighbours, adding a perpendicular connection where
an adjacent segment is collinear. Extrude mode retains the surrounding outline
with connections at both ends. Closed curves support consecutive edge removal;
whole-curve deletion requires confirmation. See PushPullCurve.md for usage.
Mixed polycurves retain exact arcs/splines and permit selecting only straight
components. Their geometry operations live in the adjacent pushpull_mixed module.

Geometry calculation, temporary viewport feedback, native picking, and document
updates are kept separate so the geometry and commit paths can be tested in Rhino.
"""

import math
import os
import sys

import Rhino
import scriptcontext as sc
import System
import System.Drawing

# Rhino's ScriptEditor does not always add the script folder to the import path.
SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
import pushpull_mixed as mixed_curves

# ----------------------------------------------------------------------
# Default settings
# ----------------------------------------------------------------------

DEFAULT_REPLACE_ORIGINAL = True
DEFAULT_ALLOW_COLLAPSE = True
DEFAULT_SHOW_PREVIEW = True
DEFAULT_EXTRUDE = False


def ui_colour(light, dark):
    return System.Drawing.ColorTranslator.FromHtml(
        dark if Rhino.Runtime.HostUtils.RunningInDarkMode else light)


COLOUR_VALID = ui_colour('#246e7b', '#b1e4df')
COLOUR_INVALID = ui_colour('#a34535', '#f0ab99')
COLOUR_GUIDE = ui_colour('#526d76', '#b9d0d5')
COLOUR_SEGMENT = COLOUR_VALID
COLOUR_COLLAPSE = COLOUR_INVALID


# ----------------------------------------------------------------------
# Small 2D vector helpers
# ----------------------------------------------------------------------

def vec2_sub(a, b):
    """Return 2D vector a - b."""
    return (a[0] - b[0], a[1] - b[1])


def vec2_add(a, b):
    """Return 2D vector a + b."""
    return (a[0] + b[0], a[1] + b[1])


def vec2_mul(v, scalar):
    """Return 2D vector v multiplied by scalar."""
    return (v[0] * scalar, v[1] * scalar)


def vec2_dot(a, b):
    """Return dot product between two 2D vectors."""
    return a[0] * b[0] + a[1] * b[1]


def vec2_cross(a, b):
    """Return the scalar cross product of two planar vectors."""
    return a[0] * b[1] - a[1] * b[0]


def vec2_length(v):
    """Return vector length."""
    return math.sqrt(v[0] * v[0] + v[1] * v[1])


def vec2_unit(v):
    """Return unitised vector. Return None if vector is too short."""
    length = vec2_length(v)
    if length <= Rhino.RhinoMath.ZeroTolerance:
        return None
    return (v[0] / length, v[1] / length)


# ----------------------------------------------------------------------
# 2D line intersection
# ----------------------------------------------------------------------

def line_line_intersection_2d(p, r, q, s, tolerance):
    """Intersect infinite planar lines; return success, point, and the two parameters."""

    denominator = vec2_cross(r, s)

    if abs(denominator) <= 1e-12 * vec2_length(r) * vec2_length(s):
        return False, None, None, None

    qp = vec2_sub(q, p)

    t = vec2_cross(qp, s) / denominator
    u = vec2_cross(qp, r) / denominator

    intersection = vec2_add(p, vec2_mul(r, t))

    return True, intersection, t, u


# ----------------------------------------------------------------------
# Plane conversion helpers
# ----------------------------------------------------------------------

def point3d_to_plane_uv(point, plane):
    """Project a world point into the polyline plane coordinates."""

    vector = point - plane.Origin

    u = Rhino.Geometry.Vector3d.Multiply(vector, plane.XAxis)
    v = Rhino.Geometry.Vector3d.Multiply(vector, plane.YAxis)

    return (u, v)


def plane_uv_to_point3d(uv, plane):
    """Convert 2D plane coordinates back into a Rhino 3D point."""
    return plane.Origin + plane.XAxis * uv[0] + plane.YAxis * uv[1]


# ----------------------------------------------------------------------
# Polyline helpers
# ----------------------------------------------------------------------

def get_polyline_without_duplicate_end(polyline):
    """Return unique ordered vertices and closure, using the document tolerance."""

    points = [polyline[i] for i in range(polyline.Count)]

    is_closed = False

    if len(points) >= 3:
        if points[0].DistanceTo(points[-1]) <= sc.doc.ModelAbsoluteTolerance:
            is_closed = True
            points = points[:-1]

    return points, is_closed


def closest_segment_index(points, is_closed, test_point, plane):
    """Find the finite segment nearest the selection point in the curve plane."""

    test_uv = point3d_to_plane_uv(test_point, plane)
    points_uv = [point3d_to_plane_uv(pt, plane) for pt in points]

    if is_closed:
        segment_count = len(points)
    else:
        segment_count = len(points) - 1

    best_index = None
    best_distance_sq = None

    for i in range(segment_count):
        j = (i + 1) % len(points)

        a = points_uv[i]
        b = points_uv[j]

        ab = vec2_sub(b, a)
        ab_len_sq = vec2_dot(ab, ab)

        if ab_len_sq <= Rhino.RhinoMath.ZeroTolerance:
            continue

        # Closest point parameter on finite segment.
        t = vec2_dot(vec2_sub(test_uv, a), ab) / ab_len_sq
        t = max(0.0, min(1.0, t))

        closest = vec2_add(a, vec2_mul(ab, t))
        delta = vec2_sub(test_uv, closest)
        distance_sq = vec2_dot(delta, delta)

        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_index = i

    return best_index


def polyline_2d_to_3d(points_2d, plane, is_closed):
    """Convert plane coordinates to world points, repeating the start for closed curves."""

    pts3d = [plane_uv_to_point3d(uv, plane) for uv in points_2d]

    if is_closed and len(pts3d) > 0:
        pts3d.append(pts3d[0])

    return pts3d


def clean_polyline_points_2d(points_2d, is_closed, tolerance):
    """Remove consecutive duplicate vertices within model tolerance."""

    if not points_2d:
        return []

    cleaned = []

    for pt in points_2d:
        if not cleaned:
            cleaned.append(pt)
            continue

        previous = cleaned[-1]
        delta = vec2_sub(pt, previous)

        if vec2_length(delta) > tolerance:
            cleaned.append(pt)

    if is_closed and len(cleaned) > 1:
        first = cleaned[0]
        last = cleaned[-1]
        delta = vec2_sub(first, last)

        if vec2_length(delta) <= tolerance:
            cleaned.pop()

    return cleaned


def build_collapsed_polyline_points(points_2d, is_closed, segment_index, collapse_point):
    """Replace the selected edge endpoints with their shared collapse point."""

    i = segment_index
    j = (i + 1) % len(points_2d)
    if is_closed and j == 0:
        return [collapse_point] + points_2d[1:-1]
    return [collapse_point if index == i else point
            for index, point in enumerate(points_2d) if index != j]


# ----------------------------------------------------------------------
# Core push/pull calculation
# ----------------------------------------------------------------------

def _compute_local_result(
    points_2d,
    is_closed,
    segment_index,
    pick_point_3d,
    plane,
    tolerance,
    allow_collapse,
    forced_signed_distance=None
):
    """Compute the open-polyline edit with its original trim-past-vertex limits."""

    vertex_count = len(points_2d)

    i = segment_index
    j = (segment_index + 1) % vertex_count

    a = points_2d[i]
    b = points_2d[j]

    segment_vector = vec2_sub(b, a)
    segment_direction = vec2_unit(segment_vector)

    if segment_direction is None:
        return {
            "ok": False,
            "blocked": True,
            "collapse": False,
            "delete_curve": False,
            "message": "Selected segment has zero length.",
            "new_points_2d": None
        }

    perpendicular = (-segment_direction[1], segment_direction[0])

    original_midpoint = vec2_mul(vec2_add(a, b), 0.5)

    if forced_signed_distance is None:
        pick_uv = point3d_to_plane_uv(pick_point_3d, plane)

        signed_distance = vec2_dot(
            vec2_sub(pick_uv, original_midpoint),
            perpendicular
        )
    else:
        signed_distance = forced_signed_distance

    offset_vector = vec2_mul(perpendicular, signed_distance)

    moved_a_raw = vec2_add(a, offset_vector)
    moved_b_raw = vec2_add(b, offset_vector)
    moved_midpoint = vec2_add(original_midpoint, offset_vector)

    moved_segment_direction = vec2_sub(moved_b_raw, moved_a_raw)
    moved_segment_length = vec2_length(moved_segment_direction)

    has_previous = is_closed or i > 0
    has_next = is_closed or j < vertex_count - 1

    can_collapse = allow_collapse and has_previous and has_next

    new_points_2d = list(points_2d)

    new_a = moved_a_raw
    new_b = moved_b_raw

    blocked = False
    message = None

    previous_fixed = None
    previous_direction = None

    next_fixed = None
    next_direction = None

    u_previous_on_moved = None
    u_next_on_moved = None


    if has_previous:
        previous_fixed_index = (i - 1) % vertex_count
        previous_fixed = points_2d[previous_fixed_index]

        previous_direction = vec2_sub(a, previous_fixed)

        ok, intersection, t_prev, u_prev = line_line_intersection_2d(
            previous_fixed,
            previous_direction,
            moved_a_raw,
            moved_segment_direction,
            tolerance
        )

        if not ok:
            blocked = True
            message = "Blocked: previous neighbouring segment is parallel."
        else:
            u_previous_on_moved = u_prev

            if t_prev < -tolerance:
                blocked = True
                message = "Blocked: would trim past previous vertex."
            else:
                new_a = intersection


    if has_next and not blocked:
        next_fixed_index = (j + 1) % vertex_count
        next_fixed = points_2d[next_fixed_index]

        next_direction = vec2_sub(next_fixed, b)

        ok, intersection, t_next, u_next = line_line_intersection_2d(
            b,
            next_direction,
            moved_a_raw,
            moved_segment_direction,
            tolerance
        )

        if not ok:
            blocked = True
            message = "Blocked: next neighbouring segment is parallel."
        else:
            u_next_on_moved = u_next

            if t_next > 1.0 + tolerance:
                blocked = True
                message = "Blocked: would trim past next vertex."
            else:
                new_b = intersection


    # Collapse is determined by endpoint order along the moved edge.
    if can_collapse and not blocked:
        if u_previous_on_moved is not None and u_next_on_moved is not None:

            remaining_length = (
                u_next_on_moved - u_previous_on_moved
            ) * moved_segment_length

            if remaining_length <= tolerance:
                ok_cross, cross_point, t_prev_cross, t_next_cross = line_line_intersection_2d(
                    previous_fixed,
                    previous_direction,
                    b,
                    next_direction,
                    tolerance
                )

                if not ok_cross:
                    cross_point = vec2_mul(vec2_add(new_a, new_b), 0.5)

                collapsed_points_2d = build_collapsed_polyline_points(
                    points_2d,
                    is_closed,
                    segment_index,
                    cross_point
                )

                collapsed_points_2d = clean_polyline_points_2d(
                    collapsed_points_2d,
                    is_closed,
                    tolerance
                )

                delete_curve = False

                if is_closed and len(collapsed_points_2d) < 3:
                    delete_curve = True

                if not is_closed and len(collapsed_points_2d) < 2:
                    delete_curve = True

                return {
                    "ok": True,
                    "blocked": False,
                    "collapse": True,
                    "delete_curve": delete_curve,
                    "message": "Curve deleted" if delete_curve else "Segment removed",
                    "signed_distance": signed_distance,
                    "original_midpoint": original_midpoint,
                    "moved_midpoint": moved_midpoint,
                    "preview_segment_start": cross_point,
                    "preview_segment_end": cross_point,
                    "collapse_point": cross_point,
                    "new_points_2d": None if delete_curve else collapsed_points_2d
                }


    if not blocked:
        new_points_2d[i] = new_a
        new_points_2d[j] = new_b
        preview_segment_start = new_a
        preview_segment_end = new_b
        message = "Distance = {:.3f}".format(abs(signed_distance))
    else:
        preview_segment_start = moved_a_raw
        preview_segment_end = moved_b_raw

    return {
        "ok": not blocked,
        "blocked": blocked,
        "collapse": False,
        "delete_curve": False,
        "message": message,
        "signed_distance": signed_distance,
        "original_midpoint": original_midpoint,
        "moved_midpoint": moved_midpoint,
        "preview_segment_start": preview_segment_start,
        "preview_segment_end": preview_segment_end,
        "new_points_2d": new_points_2d if not blocked else None
    }


def _simple_closed(points, tolerance):
    """Reject crossings, touching non-neighbours and overlapping edges."""
    count = len(points)
    if count < 3:
        return False
    origin = points[0]
    twice_area = sum(vec2_cross(vec2_sub(points[k], origin),
        vec2_sub(points[(k + 1) % count], origin)) for k in range(count))
    perimeter = sum(vec2_length(vec2_sub(points[k], points[(k + 1) % count]))
                    for k in range(count))
    if abs(twice_area) <= tolerance * perimeter:
        return False
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        ab = vec2_sub(b, a)
        length = vec2_length(ab)
        if length <= tolerance:
            return False
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            c, d = points[j], points[(j + 1) % count]
            cd = vec2_sub(d, c)
            other_length = vec2_length(cd)
            if other_length <= tolerance:
                return False
            ok, pt, t, u = line_line_intersection_2d(a, ab, c, cd, tolerance)
            if ok:
                if (-tolerance / length <= t <= 1 + tolerance / length and
                        -tolerance / other_length <= u <= 1 + tolerance / other_length):
                    return False
            elif abs(vec2_cross(vec2_sub(c, a), ab)) / length <= tolerance:
                lo = vec2_dot(vec2_sub(c, a), ab) / length
                hi = vec2_dot(vec2_sub(d, a), ab) / length
                if min(lo, hi) <= length + tolerance and max(lo, hi) >= -tolerance:
                    return False
    return True


def _sweep_hits_boundary(points, va, vb, direction, normal, travel, tolerance):
    """Check the whole motion, including collisions a large typed jump could hide."""
    a, b = points[:2]
    # A non-adjacent corner hitting the interior of the moving edge.
    for corner in points[2:]:
        distance = vec2_dot(vec2_sub(corner, a), normal)
        if tolerance < distance <= travel + tolerance:
            aa = vec2_add(a, vec2_mul(va, distance))
            bb = vec2_add(b, vec2_mul(vb, distance))
            x = vec2_dot(vec2_sub(corner, aa), direction)
            length = vec2_dot(vec2_sub(bb, aa), direction)
            if tolerance < x < length - tolerance:
                return True
    # Either endpoint crossing a stationary edge, rather than its neighbour.
    for start, velocity in [(a, va), (b, vb)]:
        for k in range(2, len(points) - 1):
            c, d = points[k], points[k + 1]
            edge = vec2_sub(d, c)
            ok, pt, distance, u = line_line_intersection_2d(
                start, velocity, c, edge, tolerance)
            if not ok or not (tolerance < distance <= travel + tolerance):
                continue
            margin = tolerance / vec2_length(edge)
            if -margin <= u <= 1 + margin:
                # Reaching the fixed corner of its own neighbour is a local
                # topology event; it is handled by the caller at this distance.
                own_corner = points[-1] if start is a else points[2]
                if vec2_length(vec2_sub(pt, own_corner)) > tolerance:
                    return True
    return False


def _bridge_ends(points, closed, index, extrude):
    """Collinear neighbours need a step; Extrude requests steps at both ends.

    A neighbour already perpendicular to the moving edge is itself a connector;
    retaining the old endpoint there would create redundant or overlapping wires.
    """
    count = len(points)
    j = (index + 1) % count
    direction = vec2_unit(vec2_sub(points[j], points[index]))
    if direction is None:
        return False, False
    normal = (-direction[1], direction[0])
    flags = []
    for exists, vector in [
            (closed or index > 0, vec2_sub(points[index], points[(index - 1) % count])),
            (closed or j < count - 1, vec2_sub(points[(j + 1) % count], points[j]))]:
        length = vec2_length(vector)
        collinear = abs(vec2_cross(vector, direction)) <= 1e-10 * length
        perpendicular = abs(vec2_cross(vector, normal)) <= 1e-10 * length
        flags.append(exists and (collinear or (extrude and not perpendicular)))
    return tuple(flags)


def _compute_open_bridged(points, index, pick, plane, tolerance, distance, bridges):
    """Open-curve variant: preserve free ends and retain existing trim limits."""
    i, j = index, index + 1
    a, b = points[i], points[j]
    direction = vec2_unit(vec2_sub(b, a))
    normal = (-direction[1], direction[0])
    midpoint = vec2_mul(vec2_add(a, b), 0.5)
    if distance is None:
        distance = vec2_dot(vec2_sub(point3d_to_plane_uv(pick, plane), midpoint), normal)
    offset = vec2_mul(normal, distance)
    aa, bb = vec2_add(a, offset), vec2_add(b, offset)
    message = None
    if i > 0 and not bridges[0]:
        edge = vec2_sub(a, points[i-1])
        ok, aa, t, u = line_line_intersection_2d(points[i-1], edge, aa, direction, tolerance)
        if not ok or t < -tolerance / vec2_length(edge):
            message = 'Blocked: would trim past previous vertex.'
    if j < len(points)-1 and not bridges[1]:
        edge = vec2_sub(points[j+1], b)
        ok, bb, t, u = line_line_intersection_2d(b, edge, vec2_add(a, offset), direction, tolerance)
        if not ok or t > 1 + tolerance / vec2_length(edge):
            message = 'Blocked: would trim past next vertex.'
    result_points = points[:i] + ([a] if bridges[0] else []) + [aa, bb] + (
        [b] if bridges[1] else []) + points[j+1:]
    if abs(distance) <= tolerance:
        result_points = list(points)
    if not message and abs(distance) > tolerance:
        # Check swept moving edge against the rest of the open chain by closing
        # a temporary ordered chain only for the continuous collision probe.
        chains = [points[j+1:], list(reversed(points[:i]))]
        for chain in chains:
            ordered = [a,b] + chain
            if not chain:
                continue
            va = vec2_mul(vec2_sub(aa,a), 1 / abs(distance))
            vb = vec2_mul(vec2_sub(bb,b), 1 / abs(distance))
            if _sweep_hits_boundary(ordered, va, vb, direction,
                    vec2_mul(normal, -1 if distance < 0 else 1), abs(distance), tolerance):
                message = 'Blocked: moving edge would cross another part of the curve.'
        # Native intersection check includes the newly added connecting edges.
        curve = Rhino.Geometry.PolylineCurve(polyline_2d_to_3d(result_points, plane, False))
        try:
            hits = Rhino.Geometry.Intersect.Intersection.CurveSelf(curve, tolerance)
            if not curve.IsValid or (hits is not None and hits.Count):
                message = 'Blocked: result would cross or overlap itself.'
        finally:
            curve.Dispose()
    return dict(ok=not message, blocked=bool(message), collapse=False, delete_curve=False,
        signed_distance=distance, original_midpoint=midpoint,
        moved_midpoint=vec2_add(midpoint, offset), preview_segment_start=aa or a,
        preview_segment_end=bb or b, removed_indices=[], added_connectors=sum(bridges),
        message=message or '{} new connecting segment{}'.format(sum(bridges), '' if sum(bridges)==1 else 's'),
        new_points_2d=None if message else result_points)


def compute_push_result(points_2d, is_closed, segment_index, pick_point_3d,
                        plane, tolerance, allow_collapse, forced_signed_distance=None,
                        extrude=False):
    bridges = _bridge_ends(points_2d, is_closed, segment_index, extrude)
    if not is_closed:
        if any(bridges):
            return _compute_open_bridged(points_2d, segment_index, pick_point_3d,
                plane, tolerance, forced_signed_distance, bridges)
        result = _compute_local_result(points_2d, is_closed, segment_index,
            pick_point_3d, plane, tolerance, allow_collapse, forced_signed_distance)
        result['removed_indices'] = [segment_index] if result.get('collapse') else []
        return result

    # Rotate the loop so that the moving edge is always 0 -> 1. Edge labels
    # retain their original indices as the two surrounding chains shorten.
    count = len(points_2d)
    labels = [(segment_index + k) % count for k in range(count)]
    points = [points_2d[k] for k in labels]
    a, b = points[:2]
    direction = vec2_unit(vec2_sub(b, a))
    midpoint = vec2_mul(vec2_add(a, b), 0.5)
    if direction is None:
        return dict(ok=False, blocked=True, collapse=False, delete_curve=False,
                    message='Selected segment has zero length.', new_points_2d=None)
    perpendicular = (-direction[1], direction[0])
    distance = forced_signed_distance
    if distance is None:
        distance = vec2_dot(vec2_sub(point3d_to_plane_uv(pick_point_3d, plane), midpoint), perpendicular)
    sign = -1.0 if distance < 0 else 1.0
    normal = vec2_mul(perpendicular, sign)
    remaining = abs(distance)
    removed = []
    result = dict(ok=True, blocked=False, collapse=False, delete_curve=False,
        signed_distance=distance, original_midpoint=midpoint,
        moved_midpoint=vec2_add(midpoint, vec2_mul(perpendicular, distance)),
        preview_segment_start=a, preview_segment_end=b, removed_indices=removed,
        added_connectors=0)

    def finish(message=None, blocked=False, whole=False):
        result.update(ok=not blocked, blocked=blocked, delete_curve=whole,
            collapse=bool(removed) or whole,
            new_points_2d=None if blocked or whole else list(points))
        if not message:
            if whole:
                message = 'Entire curve will be deleted'
            elif removed:
                message = '{} segment{} will be removed'.format(
                    len(removed), '' if len(removed) == 1 else 's')
            elif result['added_connectors']:
                message = '{} new connecting segment{}'.format(result['added_connectors'],
                    '' if result['added_connectors'] == 1 else 's')
            else:
                message = 'Extrude segment' if extrude else 'Move segment'
        result['message'] = message
        result['preview_segment_start'] = points[0] if points else midpoint
        result['preview_segment_end'] = points[1] if len(points) > 1 else result['preview_segment_start']
        if whole:
            result['removed_indices'] = list(range(count))
        if whole or result.get('movement_stopped'):
            actual_distance = sign * (abs(distance) - remaining)
            result['signed_distance'] = actual_distance
            result['moved_midpoint'] = vec2_add(midpoint, vec2_mul(perpendicular, actual_distance))
        if result.get('movement_stopped'):
            result['preview_segment_start'] = result['collapse_point']
            result['preview_segment_end'] = result['collapse_point']
        return result

    if not _simple_closed(points, tolerance):
        return finish('Use a simple closed polyline without overlapping edges.', blocked=True)
    if remaining <= tolerance:
        return finish()

    def add_bridge(previous):
        if previous:
            points.append(points[0])
            labels.append(None)
        else:
            points.insert(2, points[1])
            labels.insert(1, None)
        result['added_connectors'] += 1

    if bridges[0]:
        add_bridge(True)
    if bridges[1]:
        add_bridge(False)

    # At least one edge disappears at every iteration except the final one.
    # This bound also protects dynamic drawing against malformed input.
    for _step in range(2 * count + 3):
        if len(points) < 3:
            return finish(whole=True)
        a, b = points[:2]
        previous = vec2_sub(a, points[-1])
        following = vec2_sub(points[2], b)

        # A collinear neighbour stays fixed, with a new perpendicular connector.
        # A zero-length virtual connector expands on the first movement step.
        merged = False
        for is_previous, vector in [(True, previous), (False, following)]:
            label = labels[-1] if is_previous else labels[1]
            if label is None and vec2_length(vector) <= tolerance:
                continue
            if abs(vec2_cross(vector, direction)) <= 1e-10 * vec2_length(vector):
                add_bridge(is_previous)
                merged = True
                break
        if merged:
            continue

        # Endpoints move linearly until the next neighbouring edge or the
        # moving edge reaches zero length. Distances use model units.
        shifted = vec2_add(a, normal)
        if labels[-1] is None and vec2_length(previous) <= tolerance:
            aa, tprev = vec2_add(a, normal), 2.0
        else:
            _, aa, tprev, _ = line_line_intersection_2d(points[-1], previous, shifted, direction, tolerance)
        if labels[1] is None and vec2_length(following) <= tolerance:
            bb, tnext = vec2_add(b, normal), -1.0
        else:
            _, bb, tnext, _ = line_line_intersection_2d(b, following, shifted, direction, tolerance)
        va, vb = vec2_sub(aa, a), vec2_sub(bb, b)
        events = []
        prev_rate = tprev - 1.0
        if prev_rate < -1e-12:
            events.append((-1.0 / prev_rate, 'previous'))
        if tnext > 1e-12:
            events.append((1.0 / tnext, 'next'))
        length = vec2_dot(vec2_sub(b, a), direction)
        length_rate = vec2_dot(vec2_sub(vb, va), direction)
        if length_rate < -1e-12:
            events.append((-length / length_rate, 'selected'))
        first = min([value for value, kind in events] or [float('inf')])
        travel = min(remaining, first)
        if _sweep_hits_boundary(points, va, vb, direction, normal, travel, tolerance):
            return finish('Blocked: moving edge would cross another part of the curve.', blocked=True)
        points[0] = vec2_add(a, vec2_mul(va, travel))
        points[1] = vec2_add(b, vec2_mul(vb, travel))
        remaining = max(0.0, remaining - travel)
        hit = [kind for value, kind in events if abs(value - travel) <= tolerance]
        if hit and not allow_collapse:
            return finish('Segment removal is disabled (AllowCollapse=No).', blocked=True)
        if 'selected' in hit:
            # Once the grabbed edge has vanished there is no edge left to
            # push. Stop at this event, keeping the remaining boundary.
            points[0] = vec2_mul(vec2_add(points[0], points[1]), 0.5)
            result['movement_stopped'] = True
            result['collapse_point'] = points[0]
            points.pop(1)
            removed.append(labels.pop(0))
            points[:] = clean_polyline_points_2d(points, True, tolerance)
            if len(points) < 3:
                return finish(whole=True)
            if not _simple_closed(points, tolerance):
                return finish('Blocked: collapse would overlap the remaining boundary.', blocked=True)
            return finish('Selected segment will be removed; movement stops here.')
        if 'previous' in hit:
            points.pop(0)
            points.insert(0, points.pop())
            removed.append(labels.pop())
        if 'next' in hit:
            points.pop(1)
            removed.append(labels.pop(1))
        if len(points) < 3:
            return finish(whole=True)
        if not hit or remaining <= tolerance:
            if not _simple_closed(points, tolerance):
                return finish('Blocked: result would cross or overlap itself.', blocked=True)
            return finish()
    return finish('Blocked: could not resolve the remaining corners.', blocked=True)


# ----------------------------------------------------------------------
# Preview drawing
# ----------------------------------------------------------------------

def draw_polyline_preview(display, pts3d, colour, thickness):
    """Draw temporary straight segments without adding document objects."""

    if not pts3d or len(pts3d) < 2:
        return

    for k in range(len(pts3d) - 1):
        display.DrawLine(pts3d[k], pts3d[k + 1], colour, thickness)


class PushPreview(object):
    """Temporary viewport geometry and a rounded, aqua drawing-office HUD."""
    def __init__(self, points, closed, plane, unit_name):
        self.points, self.closed, self.plane = points, closed, plane
        self.unit_name = unit_name
        self.mixed = None
        self.bitmap = None
        self.key = None

    def dispose(self):
        if self.bitmap is not None:
            self.bitmap.Dispose()
            self.bitmap = None

    def _panel(self, result):
        key = (round(result.get('signed_distance', 0), 3), result['message'], result['blocked'])
        if key == self.key:
            return
        self.dispose()
        from System.Drawing import Bitmap, Graphics, RectangleF, Font, FontStyle, SolidBrush, Pen, PointF
        from System.Drawing.Drawing2D import GraphicsPath, LinearGradientBrush, LinearGradientMode, SmoothingMode
        from System.Drawing.Text import TextRenderingHint
        image = Bitmap(450, 182)
        graphics = Graphics.FromImage(image)
        resources = []
        try:
            graphics.SmoothingMode = SmoothingMode.AntiAlias
            graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
            path = GraphicsPath()
            resources.append(path)
            for x, y, angle in [(1, 1, 180), (424, 1, 270), (424, 156, 0), (1, 156, 90)]:
                path.AddArc(x, y, 24, 24, angle, 90)
            path.CloseFigure()
            gradient = LinearGradientBrush(RectangleF(0, 0, 450, 182),
                ui_colour('#f6f8f8', '#223138'), ui_colour('#e2f1ed', '#294944'),
                LinearGradientMode.ForwardDiagonal)
            border = Pen(ui_colour('#c6d8da', '#49616b'), 1)
            resources.extend([gradient, border])
            graphics.FillPath(gradient, path)
            graphics.DrawPath(border, path)
            ink = ui_colour('#263f4b', '#e9f5f6')
            muted = ui_colour('#526d76', '#b9d0d5')
            warning = result['blocked'] or result.get('collapse', False)
            status_colour = COLOUR_COLLAPSE if warning else COLOUR_VALID

            def text(value, size, colour, x, y, width, height):
                font = Font('Segoe UI', size, FontStyle.Regular, System.Drawing.GraphicsUnit.Pixel)
                brush = SolidBrush(colour)
                resources.extend([font, brush])
                graphics.DrawString(value, font, brush, RectangleF(x, y, width, height))

            text('RUT  /  Push/pull', 13, muted, 20, 15, 410, 22)
            graphics.DrawLine(border, PointF(20, 43), PointF(430, 43))
            text('{:.3f} {}'.format(abs(result.get('signed_distance', 0)), self.unit_name),
                 28, ink, 20, 51, 410, 40)
            text(result['message'], 15, status_colour, 20, 98, 410, 43)
            footer = 'Esc to cancel' if result['blocked'] else (
                'Click or Enter to review deletion  /  Esc to cancel' if result.get('delete_curve') else
                'Click to apply  /  Type a distance  /  Esc to cancel')
            text(footer, 12, muted, 20, 151, 410, 22)
            self.bitmap = Rhino.Display.DisplayBitmap(image)
            self.key = key
        finally:
            for resource in reversed(resources):
                resource.Dispose()
            graphics.Dispose()
            image.Dispose()

    def draw(self, display, result, show_geometry=True):
        if show_geometry:
            if result.get('new_curve') is not None and not result['blocked']:
                display.DrawCurve(result['new_curve'], COLOUR_VALID, 3)
            for fragment in result.get('trimmed_curves', []):
                display.DrawCurve(fragment, COLOUR_COLLAPSE, 4)
            if result.get('new_points_2d') and not result['blocked']:
                draw_polyline_preview(display,
                    polyline_2d_to_3d(result['new_points_2d'], self.plane, self.closed), COLOUR_VALID, 3)
            for index in result.get('removed_indices', []):
                if self.mixed is not None:
                    display.DrawCurve(self.mixed.segments[index], COLOUR_COLLAPSE, 5)
                else:
                    display.DrawLine(plane_uv_to_point3d(self.points[index], self.plane),
                        plane_uv_to_point3d(self.points[(index + 1) % len(self.points)], self.plane),
                        COLOUR_COLLAPSE, 5)
            start = plane_uv_to_point3d(result['preview_segment_start'], self.plane)
            end = plane_uv_to_point3d(result['preview_segment_end'], self.plane)
            if start.DistanceTo(end) > Rhino.RhinoMath.ZeroTolerance:
                display.DrawLine(start, end, COLOUR_INVALID if result['blocked'] else COLOUR_SEGMENT, 5)
            else:
                display.DrawPoint(start, Rhino.Display.PointStyle.RoundActivePoint, 7, COLOUR_COLLAPSE)
            display.DrawLine(plane_uv_to_point3d(result['original_midpoint'], self.plane),
                plane_uv_to_point3d(result['moved_midpoint'], self.plane), COLOUR_GUIDE, 1)
        self._panel(result)
        display.DrawBitmap(self.bitmap, 22, 22)


class TypedPreview(Rhino.Display.DisplayConduit):
    def __init__(self, doc, preview, show_geometry):
        super(TypedPreview, self).__init__()
        self.doc, self.preview, self.show_geometry = doc, preview, show_geometry
        self.result = None

    def DrawForeground(self, event):
        if self.result is not None and event.RhinoDoc == self.doc:
            self.preview.draw(event.Display, self.result, self.show_geometry)


def confirm_curve_deletion(doc):
    import urbanism_ui as ui
    dialog = ui.AquaDialog('Push/pull', 'Curves / Push/pull', 'Delete the entire curve?',
        'This movement collapses the whole closed polyline.')
    keep = ui.button('Keep curve')
    delete = ui.button('Delete curve', primary=True)
    keep.Click += lambda s, e: dialog.Close(False)
    delete.Click += lambda s, e: dialog.Close(True)
    dialog.DefaultButton = keep
    dialog.AbortButton = keep
    dialog.finish(ui.action_row(keep, delete))
    try:
        return bool(dialog.show_for_doc(doc))
    finally:
        dialog.Dispose()


# ----------------------------------------------------------------------
# Option helper
# ----------------------------------------------------------------------

def option_toggle_to_bool(toggle):
    """Return the current bool value of a Rhino OptionToggle."""
    return bool(toggle.CurrentValue)


def create_distance_picker(midpoint, plane):
    """Pick freely in the curve plane; offset is its perpendicular projection.

    A base point normally enables Rhino's Ortho/planar snapping. That would
    redirect the cursor onto a CPlane axis through the edge midpoint before
    DynamicDraw or Point() sees it, producing a different offset on oblique
    edges. Scope the override to this getter, preserving global Rhino settings
    and explicit object snaps.
    """
    gp = Rhino.Input.Custom.GetPoint()
    gp.SetCommandPrompt('Pick push/pull point, or type distance and press Enter')
    gp.SetBasePoint(midpoint, False)
    gp.PermitOrthoSnap(False)
    gp.PermitTabMode(False)
    gp.AcceptNumber(True, True)
    gp.Constrain(plane, False)
    return gp


# ----------------------------------------------------------------------
# Main command
# ----------------------------------------------------------------------

def pick_push_distance(doc, points_2d, is_closed, segment_index, plane,
                       allow_collapse, show_preview, extrude_mode, mixed=None):
    """Run native point/number input, with temporary previews cleaned on every exit."""
    tolerance = doc.ModelAbsoluteTolerance
    i = segment_index
    j = (segment_index + 1) % len(points_2d)

    original_a_3d = plane_uv_to_point3d(points_2d[i], plane)
    original_b_3d = plane_uv_to_point3d(points_2d[j], plane)

    original_midpoint_3d = Rhino.Geometry.Point3d(
        (original_a_3d.X + original_b_3d.X) * 0.5,
        (original_a_3d.Y + original_b_3d.Y) * 0.5,
        (original_a_3d.Z + original_b_3d.Z) * 0.5
    )

    selected_segment_vector = vec2_sub(points_2d[j], points_2d[i])
    selected_segment_direction = vec2_unit(selected_segment_vector)

    if selected_segment_direction is None:
        print("The selected segment has zero length.")
        return Rhino.Commands.Result.Failure, None

    selected_perpendicular = (
        -selected_segment_direction[1],
        selected_segment_direction[0]
    )

    original_mid_uv = vec2_mul(
        vec2_add(points_2d[i], points_2d[j]),
        0.5
    )

    gp = create_distance_picker(original_midpoint_3d, plane)
    extrude_toggle = Rhino.Input.Custom.OptionToggle(extrude_mode, 'No', 'Yes')
    gp.AddOptionToggle('Extrude', extrude_toggle)

    # Mutable state also works in Rhino's IronPython runtime.
    state = {
        "last_current_point": original_midpoint_3d,
        "forced_signed_distance": None,
        "extrude": extrude_mode
    }

    def get_side_sign_from_point(point_3d):
        """Return the cursor side of the edge, defaulting to positive on its line."""

        uv = point3d_to_plane_uv(point_3d, plane)

        side_value = vec2_dot(
            vec2_sub(uv, original_mid_uv),
            selected_perpendicular
        )

        if side_value < 0.0:
            return -1.0

        return 1.0

    preview = PushPreview(points_2d, is_closed, plane, str(doc.ModelUnitSystem))
    preview.mixed = mixed
    typed_preview = TypedPreview(doc, preview, show_preview)
    typed_preview.SpaceFilter = Rhino.DocObjects.ActiveSpace.ModelSpace

    def calculate(point):
        if mixed is not None:
            return mixed.compute(point, state['forced_signed_distance'],
                extrude=state['extrude'], allow_collapse=allow_collapse)
        return compute_push_result(points_2d, is_closed, segment_index,
            point, plane, tolerance, allow_collapse, state["forced_signed_distance"],
            extrude=state['extrude'])

    def dynamic_draw(sender, e):
        state["last_current_point"] = e.CurrentPoint
        if state["forced_signed_distance"] is None:
            result = calculate(e.CurrentPoint)
            try:
                preview.draw(e.Display, result, show_preview)
            finally:
                mixed_curves.dispose_result(result)

    gp.DynamicDraw += dynamic_draw
    final_pick_point = original_midpoint_3d
    try:
        while True:
            get_result = gp.Get()
            if get_result == Rhino.Input.GetResult.Option:
                state['extrude'] = option_toggle_to_bool(extrude_toggle)
                if state["forced_signed_distance"] is not None:
                    mixed_curves.dispose_result(typed_preview.result)
                    typed_preview.result = calculate(original_midpoint_3d)
                doc.Views.Redraw()
                continue
            if get_result == Rhino.Input.GetResult.Number:
                typed_distance = gp.Number()
                side_sign = get_side_sign_from_point(state["last_current_point"])
                if typed_distance < 0.0:
                    side_sign *= -1.0
                state["forced_signed_distance"] = side_sign * abs(typed_distance)
                mixed_curves.dispose_result(typed_preview.result)
                typed_preview.result = calculate(original_midpoint_3d)
                typed_preview.Enabled = True
                gp.AcceptNothing(True)
                gp.SetCommandPrompt("Review distance: Enter or click to apply, type to change, Esc to cancel")
                doc.Views.Redraw()
                continue
            if get_result == Rhino.Input.GetResult.Nothing and state["forced_signed_distance"] is not None:
                break
            if gp.CommandResult() != Rhino.Commands.Result.Success:
                return gp.CommandResult(), None
            final_pick_point = gp.Point()
            break
    finally:
        gp.DynamicDraw -= dynamic_draw
        typed_preview.Enabled = False
        mixed_curves.dispose_result(typed_preview.result)
        preview.dispose()
        gp.Dispose()
        doc.Views.Redraw()

    return Rhino.Commands.Result.Success, calculate(final_pick_point)


def _apply_push_result(doc, rhino_object, final_result, plane, is_closed, replace_original):
    tolerance = doc.ModelAbsoluteTolerance
    if final_result is None:
        print("Push/pull failed.")
        return Rhino.Commands.Result.Failure

    if final_result["blocked"]:
        print(final_result["message"])
        return Rhino.Commands.Result.Failure

    if abs(final_result["signed_distance"]) <= tolerance:
        print("Push/pull distance is too small.")
        return Rhino.Commands.Result.Cancel

    if final_result.get("delete_curve", False):
        if replace_original:
            if not confirm_curve_deletion(doc):
                return Rhino.Commands.Result.Cancel
            if not doc.Objects.Delete(rhino_object, True):
                print("Could not delete the original polyline.")
                return Rhino.Commands.Result.Failure
            doc.Views.Redraw()
            print("Push/pull complete. Curve was deleted.")
            return Rhino.Commands.Result.Success
        else:
            print("Push/pull would delete the curve. No new curve was created because Replace=No.")
            return Rhino.Commands.Result.Cancel

    if final_result.get('new_curve') is not None:
        new_curve = final_result['new_curve'].DuplicateCurve()
    else:
        new_points_2d = final_result["new_points_2d"]

        if new_points_2d is None or len(new_points_2d) < 2:
            print("The resulting polyline does not have enough points.")
            return Rhino.Commands.Result.Failure

        if is_closed and len(new_points_2d) < 3:
            print("The resulting closed polyline does not have enough points.")
            return Rhino.Commands.Result.Failure

        new_points_3d = polyline_2d_to_3d(
            new_points_2d,
            plane,
            is_closed
        )

        new_polyline = Rhino.Geometry.Polyline(new_points_3d)

        if not new_polyline.IsValid:
            print("The resulting polyline is invalid.")
            return Rhino.Commands.Result.Failure

        new_curve = new_polyline.ToPolylineCurve()

    result_id = System.Guid.Empty

    try:
        if replace_original:
            success = doc.Objects.Replace(rhino_object.Id, new_curve)

            if not success:
                print("Could not replace the original curve.")
                return Rhino.Commands.Result.Failure

            result_id = rhino_object.Id

        else:
            attributes = rhino_object.Attributes.Duplicate()
            try:
                result_id = doc.Objects.AddCurve(new_curve, attributes)
            finally:
                attributes.Dispose()

            if result_id == System.Guid.Empty:
                print("Could not add the new curve.")
                return Rhino.Commands.Result.Failure
    finally:
        new_curve.Dispose()

    doc.Objects.UnselectAll()
    doc.Objects.Select(result_id)
    doc.Views.Redraw()

    if final_result.get("collapse", False):
        print("Push/pull complete. {} segment(s) removed.".format(
            len(final_result.get("removed_indices", []))))
    elif final_result.get('added_connectors'):
        print('Push/pull complete. {} connecting segment(s) added.'.format(
            final_result['added_connectors']))
    else:
        print("Push/pull complete.")

    return Rhino.Commands.Result.Success


def apply_push_result(doc, rhino_object, result, plane, is_closed, replace_original=True):
    """Commit one edit, preserving object attributes and grouping it for Undo."""
    record = doc.BeginUndoRecord('Push/pull curve')
    try:
        return _apply_push_result(doc, rhino_object, result, plane, is_closed, replace_original)
    finally:
        if record:
            doc.EndUndoRecord(record)


def main():
    """Select a straight curve section, preview the edit, then commit it."""
    replace_toggle = Rhino.Input.Custom.OptionToggle(
        DEFAULT_REPLACE_ORIGINAL,
        "No",
        "Yes"
    )

    collapse_toggle = Rhino.Input.Custom.OptionToggle(
        DEFAULT_ALLOW_COLLAPSE,
        "No",
        "Yes"
    )

    preview_toggle = Rhino.Input.Custom.OptionToggle(
        DEFAULT_SHOW_PREVIEW,
        "No",
        "Yes"
    )
    extrude_toggle = Rhino.Input.Custom.OptionToggle(DEFAULT_EXTRUDE, "No", "Yes")

    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt("Click a straight curve section to push/pull")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.SubObjectSelect = False
    go.EnablePreSelect(False, True)

    go.AddOptionToggle("Replace", replace_toggle)
    go.AddOptionToggle("AllowCollapse", collapse_toggle)
    go.AddOptionToggle("ShowPreview", preview_toggle)
    go.AddOptionToggle("Extrude", extrude_toggle)

    mixed = None
    result = None
    try:
        while True:
            get_result = go.Get()
            if get_result == Rhino.Input.GetResult.Option:
                continue
            if go.CommandResult() != Rhino.Commands.Result.Success:
                return go.CommandResult()
            obj_ref = go.Object(0)
            rhino_object = obj_ref.Object()
            curve = obj_ref.Curve()
            if curve is None:
                return Rhino.Commands.Result.Failure
            success, plane = curve.TryGetPlane()
            if not success:
                print('Select a planar curve.')
                go.ClearObjects()
                continue
            selection_point = obj_ref.SelectionPoint()
            if not selection_point.IsValid:
                print('Could not read the curve selection point.')
                return Rhino.Commands.Result.Failure
            success, polyline = curve.TryGetPolyline()
            if success and polyline is not None:
                points_3d, is_closed = get_polyline_without_duplicate_end(polyline)
                if len(points_3d) < (3 if is_closed else 2):
                    print('The polyline does not have enough vertices.')
                    return Rhino.Commands.Result.Failure
                segment_index = closest_segment_index(points_3d,is_closed,selection_point,plane)
                if segment_index is None:
                    return Rhino.Commands.Result.Failure
                points_2d = [point3d_to_plane_uv(point,plane) for point in points_3d]
            else:
                mixed = mixed_curves.MixedCurveEdit(curve,plane,sc.doc.ModelAbsoluteTolerance)
                if not mixed.select_line(selection_point):
                    print('Curved sections cannot be moved. Click a straight section.')
                    mixed.dispose()
                    mixed = None
                    go.ClearObjects()
                    continue
                points_2d = mixed.line_points_2d()
                is_closed, segment_index = mixed.closed, 0
            break
        replace_original = option_toggle_to_bool(replace_toggle)
        outcome, result = pick_push_distance(sc.doc,points_2d,is_closed,segment_index,plane,
            option_toggle_to_bool(collapse_toggle),option_toggle_to_bool(preview_toggle),
            option_toggle_to_bool(extrude_toggle),mixed=mixed)
        if outcome != Rhino.Commands.Result.Success:
            return outcome
        return apply_push_result(sc.doc,rhino_object,result,plane,is_closed,replace_original)
    finally:
        mixed_curves.dispose_result(result)
        if mixed is not None:
            mixed.dispose()
        go.Dispose()


if __name__ == '__main__':
    main()
