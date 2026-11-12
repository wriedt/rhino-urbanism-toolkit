# -*- coding: utf-8 -*-
"""Exact unused spans of open source curves after editing enclosed regions."""
import Rhino
G = Rhino.Geometry


def remaining_parts(curve, boundaries, tolerance, erased_intervals=()):
    """Return owned pieces and whether any source span was consumed.

    Boundaries belong to the initial cells actually affected by gestures, including
    erased cells. Comparing only final outlines would resurrect merged dividers.
    Matching geometry instead of Boolean curve indices also handles duplicate inputs.
    """
    intervals = [(max(curve.Domain.T0,a),min(curve.Domain.T1,b)) for a,b in erased_intervals
                 if b>a and curve.GetLength(G.Interval(a,b))>tolerance]
    for boundary in boundaries:
        events = G.Intersect.Intersection.CurveCurve(curve,boundary,tolerance,tolerance)
        if events is None:
            continue
        try:
            for event in events:
                if not event.IsOverlap:
                    continue
                start = max(curve.Domain.T0,min(event.OverlapA.T0,event.OverlapA.T1))
                end = min(curve.Domain.T1,max(event.OverlapA.T0,event.OverlapA.T1))
                if end>start and curve.GetLength(G.Interval(start,end))>tolerance:
                    intervals.append((start,end))
        finally:
            events.Dispose()
    if not intervals:
        return [curve.DuplicateCurve()],False
    used = []
    for start,end in sorted(intervals):
        if used and (start<=used[-1][1] or curve.GetLength(G.Interval(used[-1][1],start))<=tolerance):
            used[-1] = (used[-1][0],max(end,used[-1][1]))
        else:
            used.append((start,end))
    pieces = []
    cursor = curve.Domain.T0
    try:
        for start,end in used+[(curve.Domain.T1,curve.Domain.T1)]:
            if start>cursor:
                piece = curve.Trim(cursor,start)
                if piece is None:
                    raise ValueError('Could not preserve an unused part of an open curve.')
                if piece.GetLength()>tolerance:
                    pieces.append(piece)
                else:
                    piece.Dispose()
            cursor = max(cursor,end)
        return pieces,True
    except Exception:
        for piece in pieces:
            piece.Dispose()
        raise


def dispose_records(records):
    for record in records or []:
        for piece in record['pieces']:
            piece.Dispose()


def edge_intervals(curve, other_curves, tolerance):
    """Original source domains split at intersections, not polyline corners."""
    parameters = [curve.Domain.T0,curve.Domain.T1]
    for other in other_curves:
        own = other is curve
        events = (G.Intersect.Intersection.CurveSelf(curve,tolerance) if own else
                  G.Intersect.Intersection.CurveCurve(curve,other,tolerance,tolerance))
        if events is None:
            continue
        try:
            for event in events:
                if event.IsOverlap:
                    parameters.extend([event.OverlapA.T0,event.OverlapA.T1])
                    if own:parameters.extend([event.OverlapB.T0,event.OverlapB.T1])
                else:
                    parameters.append(event.ParameterA)
                    if own:parameters.append(event.ParameterB)
        finally:
            events.Dispose()
    kept = []
    for value in sorted(set(max(curve.Domain.T0,min(curve.Domain.T1,t)) for t in parameters)):
        if not kept or curve.GetLength(G.Interval(kept[-1],value))>tolerance:
            kept.append(value)
    if kept[-1] != curve.Domain.T1:
        kept[-1] = curve.Domain.T1
    return [(a,b) for a,b in zip(kept,kept[1:]) if curve.GetLength(G.Interval(a,b))>tolerance]
