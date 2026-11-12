# -*- coding: utf-8 -*-
"""Geometry study only: preserve unused spans of open curves; main tool unchanged."""
import Rhino
import math
import json
import os
from System.Collections.Generic import List
G=Rhino.Geometry


def region_loops(curves,tolerance):
    result=G.Curve.CreateBooleanRegions(List[G.Curve](curves),G.Plane.WorldXY,False,tolerance)
    if result is None:return []
    try:return [[c.DuplicateCurve() for c in result.RegionCurves(i)] for i in range(result.RegionCount)]
    finally:result.Dispose()


def unused_spans(curve,regions,tolerance):
    """Match region edges back onto original 3D geometry, including duplicate inputs."""
    used=[]
    for loops in regions:
        for boundary in loops:
            events=G.Intersect.Intersection.CurveCurve(curve,boundary,tolerance,tolerance)
            if events is None:continue
            try:
                for event in events:
                    if event.IsOverlap:
                        start=max(curve.Domain.T0,min(event.OverlapA.T0,event.OverlapA.T1))
                        end=min(curve.Domain.T1,max(event.OverlapA.T0,event.OverlapA.T1))
                        if end>start:used.append((start,end))
            finally:events.Dispose()
    merged=[]
    for start,end in sorted(used):
        if merged and (start<=merged[-1][1] or curve.GetLength(G.Interval(merged[-1][1],start))<=tolerance):
            merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    cursor=curve.Domain.T0
    result=[]
    for start,end in merged+[(curve.Domain.T1,curve.Domain.T1)]:
        if start>cursor:
            piece=curve.Trim(cursor,start)
            if piece is not None:
                if piece.GetLength()>tolerance:result.append(piece)
                else:piece.Dispose()
        cursor=max(cursor,end)
    return result


def rect():return G.Rectangle3d(G.Plane.WorldXY,10,10).ToNurbsCurve()


def line(a,b):return G.LineCurve(G.Point3d(*a),G.Point3d(*b))


def run_experiments():
    cases=[]
    def case(name,curves,index,count,length,kind=None,hatch_domain=False):
        loops=[];pieces=[]
        try:
            loops=region_loops(curves,0.001)
            if hatch_domain:
                for region in loops:
                    for c in region:c.Dispose()
                # Use the tool's actual eligible cells: a U-shaped external excursion
                # can enclose a kernel region outside the hatch, which the tool excludes.
                path=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','ShapeBuilder.py'))
                ns={'__name__':'study_builder','__file__':path}
                exec(compile(open(path,encoding='utf-8').read(),path,'exec'),ns)
                doc=Rhino.RhinoDoc.CreateHeadless(None);doc.ModelAbsoluteTolerance=0.001
                h=G.Hatch.Create(G.Plane.WorldXY,curves[0],List[G.Curve](),0,0,1)
                builder=None
                try:
                    builder=ns['Builder'](doc,[h]+curves[1:])
                    loops=[[c.DuplicateCurve() for c in cell.loops] for cell in builder.cells]
                finally:
                    if builder:builder.dispose_geometry()
                    h.Dispose();doc.Dispose()
            pieces=unused_spans(curves[index],loops,0.001)
            actual=sum(c.GetLength() for c in pieces)
            assert len(pieces)==count,(name,len(pieces),count)
            assert abs(actual-length)<0.002,(name,actual,length)
            if kind is not None:assert all(isinstance(p,kind) for p in pieces)
            cases.append({'case':name,'regions':len(loops),'leftover_pieces':len(pieces),'leftover_length':round(actual,6)})
        finally:
            for p in pieces:p.Dispose()
            for region in loops:
                for c in region:c.Dispose()
            for c in curves:c.Dispose()
    case('crossing line: keep two external tails',[rect(),line((-5,5,0),(15,5,0))],1,2,10)
    case('unrelated selected line: keep whole',[rect(),line((-5,15,0),(15,15,0))],1,1,20)
    case('dangling line: no enclosed region edge, keep whole',[rect(),line((-5,5,0),(5,5,0))],1,1,10)
    case('line on outer boundary: no duplicate middle span',[rect(),line((-5,10,0),(15,10,0))],1,2,10)
    case('point tangency: preserve whole curve',[rect(),line((-5,5,0),(5,15,0))],1,1,math.sqrt(200))
    c=G.PolylineCurve(List[G.Point3d]([G.Point3d(-5,2,0),G.Point3d(15,2,0),G.Point3d(15,8,0),G.Point3d(-5,8,0)]))
    case('re-entering polyline through hatch: preserve outside bridge and both tails',[rect(),c],1,3,26,hatch_domain=True)
    arc=G.ArcCurve(G.Arc(G.Point3d(-10,0,0),G.Point3d(0,10,0),G.Point3d(10,0,0)))
    r=G.Rectangle3d(G.Plane.WorldXY,G.Interval(-5,5),G.Interval(-2,12)).ToNurbsCurve()
    case('curved leftovers stay exact arcs',[r,arc],1,2,20*math.pi/3,G.ArcCurve)
    case('duplicate divider: both sources classified geometrically',[rect(),line((-5,5,0),(15,5,0)),line((-5,5,0),(15,5,0))],2,2,10)
    return cases


if __name__=='__main__':
    print(json.dumps(run_experiments(),indent=2))
