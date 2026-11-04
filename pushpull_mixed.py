# -*- coding: utf-8 -*-
"""Exact line edits inside planar mixed curves. No document changes or UI.

Arcs and splines are duplicated or trimmed in their original parameter domains;
they are never sampled into polylines. All returned geometry belongs to the
result and must be released with dispose_result().
"""

import Rhino


def dispose_result(result):
    if result:
        for geometry in result.pop('_owned_geometry', []):
            geometry.Dispose()


def _dot(a, b):
    return Rhino.Geometry.Vector3d.Multiply(a, b)


def _flatten(curve):
    """Retain component boundaries, including tangent joins and nested polycurves."""
    pieces = curve.DuplicateSegments()
    if not pieces:
        return [curve.DuplicateCurve()]
    result = []
    for piece in pieces:
        if isinstance(piece, (Rhino.Geometry.PolyCurve, Rhino.Geometry.PolylineCurve)):
            children = piece.DuplicateSegments()
            if children and len(children) > 1:
                try:
                    for child in children:
                        result.extend(_flatten(child))
                finally:
                    for child in children:
                        child.Dispose()
                    piece.Dispose()
                continue
            if children:
                for child in children:
                    child.Dispose()
        result.append(piece)
    return result


class MixedCurveEdit(object):
    """Own exact source components; edit a selected straight one in its plane."""
    def __init__(self, curve, plane, tolerance):
        self.plane, self.tolerance = plane, tolerance
        self.closed = curve.IsClosed
        self.segments = _flatten(curve)
        self.linear = [segment.IsLinear(tolerance) for segment in self.segments]
        self.selected_index = None
        self._critical = None

    def dispose(self):
        for segment in self.segments:
            segment.Dispose()
        self.segments = []

    def select_line(self, point):
        """Reject clicks on curved components rather than selecting a distant line."""
        nearest = []
        for index, segment in enumerate(self.segments):
            ok, parameter = segment.ClosestPoint(point)
            if ok:
                nearest.append((segment.PointAt(parameter).DistanceTo(point), index))
        if not nearest:
            return False
        nearest.sort()
        best = nearest[0][0]
        for distance, index in nearest:
            if distance > best + self.tolerance:
                break
            if self.linear[index]:
                self.selected_index = index
                self._critical = None
                return True
        return False

    def line_points_2d(self):
        segment = self.segments[self.selected_index]
        return [self._uv(segment.PointAtStart), self._uv(segment.PointAtEnd)]

    def _uv(self, point):
        delta = point - self.plane.Origin
        return (_dot(delta, self.plane.XAxis), _dot(delta, self.plane.YAxis))

    def _frame(self):
        line = self.segments[self.selected_index]
        a, b = line.PointAtStart, line.PointAtEnd
        direction = b - a
        direction.Unitize()
        normal = Rhino.Geometry.Vector3d.CrossProduct(self.plane.Normal, direction)
        normal.Unitize()
        return a, b, direction, normal

    def _end(self, indices, next_end, moved_a, normal, extrude, allow_collapse):
        """Walk the remaining contour until a neighbour can meet the moved line."""
        tolerance = self.tolerance
        removed = []
        for index in indices:
            segment = self.segments[index]
            a, b = segment.PointAtStart, segment.PointAtEnd
            anchor = a if next_end else b
            vector = b - a
            length = vector.Length
            # Existing perpendicular lines already act as connections. Otherwise
            # Extrude keeps the original component and adds a normal connector.
            perpendicular = self.linear[index] and abs(_dot(vector, normal)) >= length * (1 - 1e-10)
            if extrude and not perpendicular:
                return dict(index=index, parameter=None, anchor=anchor,
                    point=anchor + normal * _dot(moved_a-anchor, normal), removed=removed)
            if self.linear[index]:
                denominator = _dot(vector, normal)
                if abs(denominator) <= length * 1e-10:
                    return dict(index=index, parameter=None, anchor=anchor,
                        point=anchor + normal * _dot(moved_a-anchor, normal), removed=removed)
                fraction = _dot(moved_a-a, normal) / denominator
                margin = tolerance / max(length, tolerance)
                exhausted = fraction >= 1-margin if next_end else fraction <= margin
                if exhausted:
                    if not allow_collapse:
                        raise ValueError('Segment removal is disabled (AllowCollapse=No).')
                    removed.append(index)
                    continue
                point = a + vector * fraction
                return dict(index=index, parameter=fraction, point=point, anchor=None, removed=removed)
            cut_plane = Rhino.Geometry.Plane(moved_a, normal)
            events = Rhino.Geometry.Intersect.Intersection.CurvePlane(segment, cut_plane, tolerance)
            parameters = []
            if events:
                try:
                    for event in events:
                        if event.IsOverlap:
                            raise ValueError('Blocked: a curved section overlaps the moved line.')
                        parameters.append(event.ParameterA)
                finally:
                    events.Dispose()
            if not parameters:
                return dict(index=index, parameter=None, anchor=anchor,
                    point=anchor + normal * _dot(moved_a-anchor, normal), removed=removed)
            parameter = min(parameters) if next_end else max(parameters)
            point = segment.PointAt(parameter)
            far_end = b if next_end else a
            if point.DistanceTo(far_end) <= tolerance:
                if not allow_collapse:
                    raise ValueError('Segment removal is disabled (AllowCollapse=No).')
                removed.append(index)
                continue
            return dict(index=index, parameter=parameter, point=point, anchor=None, removed=removed)
        raise ValueError('Blocked: the remaining mixed curve would collapse.')

    def _critical_distances(self, normal, midpoint):
        """Topology can change at extrema, vertices, or endpoint-path crossings."""
        if self._critical is not None:
            return self._critical
        points = []
        bounds = Rhino.Geometry.BoundingBox.Empty
        for segment in self.segments:
            bounds.Union(segment.GetBoundingBox(True))
            points.extend([segment.PointAtStart, segment.PointAtEnd])
            for parameter in segment.ExtremeParameters(normal) or []:
                points.append(segment.PointAt(parameter))
        reach = max(bounds.Diagonal.Length * 3, self.tolerance * 100)
        paths = []
        for segment, linear in zip(self.segments, self.linear):
            anchor = segment.PointAtStart
            paths.append(Rhino.Geometry.Line(anchor-normal*reach, anchor+normal*reach))
            if linear:
                direction = segment.PointAtEnd-anchor
                direction.Unitize()
                paths.append(Rhino.Geometry.Line(anchor-direction*reach, anchor+direction*reach))
        for path in paths:
            for segment in self.segments:
                events = Rhino.Geometry.Intersect.Intersection.CurveLine(
                    segment, path, self.tolerance, self.tolerance)
                if events:
                    try:
                        points.extend(event.PointA for event in events if event.IsPoint)
                    finally:
                        events.Dispose()
        values = sorted(_dot(point-midpoint,normal) for point in points)
        unique = []
        for value in values:
            if not unique or value-unique[-1] > self.tolerance:
                unique.append(value)
        self._critical = unique
        return unique

    def compute(self, pick, distance=None, extrude=False, allow_collapse=True, check_motion=True):
        a, b, direction, normal = self._frame()
        midpoint = a + (b-a)*0.5
        if distance is None:
            distance = _dot(pick-midpoint,normal)
        moved_a, moved_b = a+normal*distance, b+normal*distance
        owned = []
        result = dict(ok=False, blocked=True, collapse=False, delete_curve=False,
            signed_distance=distance, original_midpoint=self._uv(midpoint),
            moved_midpoint=self._uv(midpoint+normal*distance),
            preview_segment_start=self._uv(moved_a), preview_segment_end=self._uv(moved_b),
            new_points_2d=None, new_curve=None, removed_indices=[], trimmed_curves=[],
            added_connectors=0, _owned_geometry=owned)
        n, selected = len(self.segments), self.selected_index
        if self.closed:
            rest = [(selected+k)%n for k in range(1,n)]
            next_indices, previous_indices = rest, list(reversed(rest))
        else:
            rest = list(range(n))
            next_indices = list(range(selected+1,n))
            previous_indices = list(range(selected-1,-1,-1))
        try:
            if abs(distance) <= self.tolerance:
                joined = self._join([segment.DuplicateCurve() for segment in self.segments])
                owned.append(joined)
                result.update(ok=True, blocked=False, new_curve=joined, message='Move line segment')
                return result
            end_b = self._end(next_indices, True, moved_a, normal, extrude, allow_collapse) if next_indices else None
            end_a = self._end(previous_indices, False, moved_a, normal, extrude, allow_collapse) if previous_indices else None
            if end_a:
                moved_a = end_a['point']
            if end_b:
                moved_b = end_b['point']
            result.update(preview_segment_start=self._uv(moved_a), preview_segment_end=self._uv(moved_b))
            if _dot(moved_b-moved_a,direction) <= self.tolerance:
                raise ValueError('Blocked: the selected line would collapse in a mixed curve.')
            removed = set((end_a['removed'] if end_a else []) + (end_b['removed'] if end_b else []))
            result['removed_indices'] = sorted(removed)
            result['collapse'] = bool(removed)
            # Keep a contiguous original parameter interval. Two cuts on the
            # same curved component (the U-shaped example) retain its middle.
            if self.closed:
                start, end = rest.index(end_b['index']), rest.index(end_a['index'])
                if start > end:
                    raise ValueError('Blocked: cuts would split or erase the remaining outline.')
                retained = rest[start:end+1]
            else:
                retained = [k for k in range(n) if k not in removed and k != selected]
            pieces = []
            try:
                for index in retained:
                    segment = self.segments[index]
                    domain = segment.Domain
                    lo, hi = domain.T0, domain.T1
                    start_point, end_point = segment.PointAtStart, segment.PointAtEnd
                    if end_b and index == end_b['index'] and end_b['parameter'] is not None:
                        if self.linear[index]:
                            start_point = moved_b
                        else:
                            lo = end_b['parameter']
                    if end_a and index == end_a['index'] and end_a['parameter'] is not None:
                        if self.linear[index]:
                            end_point = moved_a
                        else:
                            hi = end_a['parameter']
                    if self.linear[index]:
                        piece = Rhino.Geometry.LineCurve(start_point,end_point)
                    else:
                        if hi <= lo:
                            raise ValueError('Blocked: cuts would erase the curved section.')
                        piece = segment.Trim(lo,hi)
                        for t0,t1 in [(domain.T0,lo),(hi,domain.T1)]:
                            if t1>t0:
                                fragment = segment.Trim(t0,t1)
                                if fragment:
                                    owned.append(fragment)
                                    result['trimmed_curves'].append(fragment)
                    if piece is None or not piece.IsValid or piece.GetLength()<=self.tolerance:
                        if piece:
                            piece.Dispose()
                        raise ValueError('Blocked: the remaining section is too short.')
                    pieces.append((index,piece))
                line = Rhino.Geometry.LineCurve(moved_a,moved_b)
                chain = [(selected,line)]
                def connector(start_point,end_point):
                    if start_point.DistanceTo(end_point)>self.tolerance:
                        result['added_connectors']+=1
                        return [(None,Rhino.Geometry.LineCurve(start_point,end_point))]
                    return []
                if self.closed:
                    chain += connector(moved_b,end_b['anchor']) if end_b['anchor'] is not None else []
                    chain += pieces
                    pieces = []
                    chain += connector(end_a['anchor'],moved_a) if end_a['anchor'] is not None else []
                else:
                    before = [(i,p) for i,p in pieces if i<selected]
                    after = [(i,p) for i,p in pieces if i>selected]
                    pieces = []
                    chain = before + (connector(end_a['anchor'],moved_a) if end_a and end_a['anchor'] is not None else []) + chain
                    chain += connector(moved_b,end_b['anchor']) if end_b and end_b['anchor'] is not None else []
                    chain += after
                joined = self._join([piece for index,piece in chain])
                owned.append(joined)
            finally:
                for index,piece in pieces:
                    piece.Dispose()
            if not joined.IsValid or joined.IsClosed != self.closed:
                raise ValueError('Blocked: result would not form a connected curve.')
            events = Rhino.Geometry.Intersect.Intersection.CurveSelf(joined,self.tolerance)
            has_intersections = events is not None and events.Count>0
            if events is not None:
                events.Dispose()
            if has_intersections:
                raise ValueError('Blocked: result would cross or overlap itself.')
            if self.closed:
                properties = Rhino.Geometry.AreaMassProperties.Compute(joined)
                try:
                    if properties is None or properties.Area<=self.tolerance*joined.GetLength():
                        raise ValueError('Blocked: the mixed curve would collapse.')
                finally:
                    if properties:
                        properties.Dispose()
            if check_motion:
                limit=abs(distance)
                sign=-1 if distance<0 else 1
                critical = sorted(sign*v for v in self._critical_distances(normal,midpoint)
                    if self.tolerance < sign*v < limit-self.tolerance)
                stops=[0.]+critical+[limit]
                probes=critical+[(lo+hi)*0.5 for lo,hi in zip(stops,stops[1:]) if hi-lo>self.tolerance*4]
                for value in probes:
                    probe=self.compute(pick,sign*value,extrude,allow_collapse,False)
                    try:
                        if probe['blocked']:
                            raise ValueError('Blocked: movement meets another part of the curve.')
                    finally:
                        dispose_result(probe)
            message='Move line segment'
            if result['added_connectors']:
                message='{} new connecting segment{}'.format(result['added_connectors'],'' if result['added_connectors']==1 else 's')
            elif result['trimmed_curves']:
                message='Trim curved neighbour'
            if removed:
                message='{} segment{} will be removed'.format(len(removed),'' if len(removed)==1 else 's')
            result.update(ok=True,blocked=False,new_curve=joined,message=message)
        except ValueError as error:
            dispose_result(result)
            result.update(new_curve=None,trimmed_curves=[],message=str(error))
        except Exception:
            dispose_result(result)
            raise
        return result

    def _join(self, pieces):
        """Append exact components, then release the temporary input copies."""
        result=Rhino.Geometry.PolyCurve()
        try:
            for piece in pieces:
                if not result.Append(piece):
                    raise ValueError('Blocked: curve components could not be joined.')
            return result
        except Exception:
            result.Dispose()
            raise
        finally:
            for piece in pieces:
                piece.Dispose()
