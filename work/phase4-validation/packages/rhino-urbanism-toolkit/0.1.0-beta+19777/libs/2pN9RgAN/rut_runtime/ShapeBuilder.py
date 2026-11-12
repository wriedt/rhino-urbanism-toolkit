#! python 3
# -*- coding: utf-8 -*-
"""Shape Builder: merge and erase coplanar curve and hatch regions in Rhino 8."""
import os
import sys
import Rhino
import scriptcontext as sc
import System.Drawing as sd
import System.Windows.Forms as win
from System.Collections.Generic import List

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import viewport_ui
import shape_builder_leftovers as leftover_geometry

KEY = 'RUT.ShapeBuilder'
G = Rhino.Geometry
AQUA = sd.Color.FromArgb(64, 177, 170)
CORAL = sd.Color.FromArgb(213, 116, 95)
INK = sd.Color.FromArgb(36, 110, 123)
SEPARATE = sd.Color.FromArgb(225, 235, 241)
EDGE = sd.Color.FromArgb(68, 82, 95)
HOVER = sd.Color.FromArgb(247, 199, 79)


def net_curves(items):
    return List[G.Curve](list(items))


def inside_loops(loops, point, plane, tolerance):
    relations = [c.Contains(point, plane, tolerance) for c in loops]
    return (G.PointContainment.Coincident not in relations and
            sum(r == G.PointContainment.Inside for r in relations) % 2 == 1)


def boundaries(curves, plane, tolerance, points=None):
    if points is None:
        result = G.Curve.CreateBooleanRegions(net_curves(curves), plane, False, tolerance)
    else:
        result = G.Curve.CreateBooleanRegions(
            net_curves(curves), plane, List[G.Point3d](list(points)), True, tolerance)
    if result is None:
        raise ValueError('Rhino could not calculate regions from these curves.')
    try:
        return [[c.DuplicateCurve() for c in result.RegionCurves(i)]
                for i in range(result.RegionCount)]
    finally:
        result.Dispose()


class Cell:
    def __init__(self, loops, plane, tolerance):
        self.loops = loops
        self.plane = plane
        self.tolerance = tolerance
        self.box = G.BoundingBox.Empty
        self.mesh = G.Mesh()
        for c in loops:
            self.box.Union(c.GetBoundingBox(True))
        breps = G.Brep.CreatePlanarBreps(net_curves(loops), tolerance)
        if not breps:
            raise ValueError('A region could not be filled.')
        for b in breps:
            try:
                meshes = G.Mesh.CreateFromBrep(b, G.MeshingParameters.FastRenderMesh)
                if meshes:
                    for m in meshes:
                        self.mesh.Append(m)
                        m.Dispose()
            finally:
                b.Dispose()
        self.seed = None
        self.mesh.Faces.ConvertQuadsToTriangles()
        for f in self.mesh.Faces:
            a, b, c = [G.Point3d(self.mesh.Vertices[i]) for i in (f.A, f.B, f.C)]
            p = G.Point3d((a.X+b.X+c.X)/3, (a.Y+b.Y+c.Y)/3, (a.Z+b.Z+c.Z)/3)
            if self.contains(p):
                self.seed = p
                break
        if self.seed is None:
            raise ValueError('Could not find a safe interior point for a region.')

    def contains(self, point):
        return inside_loops(self.loops, point, self.plane, self.tolerance)

    def dispose(self):
        self.mesh.Dispose()
        for c in self.loops:
            c.Dispose()


class Preview(Rhino.Display.DisplayConduit):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.good = Rhino.Display.DisplayMaterial(AQUA)
        self.good.Transparency = 0.22
        self.separate = Rhino.Display.DisplayMaterial(SEPARATE)
        self.separate.Transparency = 0.28
        self.hover = Rhino.Display.DisplayMaterial(HOVER)
        self.hover.Transparency = 0.35
        self.bad = Rhino.Display.DisplayMaterial(CORAL)
        self.bad.Transparency = 0.45

    def ObjectCulling(self, e):
        o = self.owner
        if (e.RhinoDoc.RuntimeSerialNumber == o.doc.RuntimeSerialNumber and
                e.RhinoObject is not None and e.RhinoObject.Id in o.source_ids):
            e.CullObject = True

    def CalculateBoundingBox(self, e):
        if e.RhinoDoc.RuntimeSerialNumber != self.owner.doc.RuntimeSerialNumber:
            return
        for c in self.owner.cells:
            e.IncludeBoundingBox(c.box)
        for record in self.owner.preview_leftovers():
            for piece in record['pieces']:
                e.IncludeBoundingBox(piece.GetBoundingBox(True))

    def PostDrawObjects(self, e):
        o = self.owner
        if e.RhinoDoc.RuntimeSerialNumber != o.doc.RuntimeSerialNumber:
            return
        active = o.active_members()
        for group, regions in o.group_outlines:
            selected = bool(group & active)
            if not selected and not o.is_output_group(group):
                continue
            merged = len(group) > 1
            material = (self.bad if o.erase else self.hover) if selected else (self.good if merged else self.separate)
            for index in group:
                e.Display.DrawMeshShaded(o.cells[index].mesh, material)
        # Draw boundaries after every fill. Coplanar mesh depth must not break outlines.
        e.Display.PushDepthTesting(False)
        try:
            for group, regions in o.group_outlines:
                selected = bool(group & active)
                if not selected and not o.is_output_group(group):
                    continue
                merged = len(group)>1
                if not (o.dragging and o.pending_loops and selected):
                    for loops in regions:
                        for c in loops:
                            color = (CORAL if o.erase else HOVER) if selected else (INK if merged else EDGE)
                            e.Display.DrawCurve(c, color, 5 if selected else (4 if merged else 1))
            for loops in o.pending_loops:
                for c in loops:
                    e.Display.DrawCurve(c, HOVER, 5)
            for record in o.preview_leftovers():
                color = o.leftover_colour(record['entry'])
                for piece in record['pieces']:
                    e.Display.DrawCurve(piece,color,2)
            edges = o.stroke_edges if o.dragging and o.erase else ({o.edge_hover} if o.edge_hover is not None else set())
            for key in edges:
                e.Display.DrawCurve(o.edge_atoms[key]['curve'],CORAL,4)
        finally:
            e.Display.PopDepthTesting()

    def DrawForeground(self, e):
        o = self.owner
        if (e.RhinoDoc.RuntimeSerialNumber == o.doc.RuntimeSerialNumber and
                o.doc.Views.ActiveView is not None and
                e.Viewport.Id == o.doc.Views.ActiveView.ActiveViewport.Id):
            o.panel.draw(e.Display,'RUT | Shape Builder',o.status_text(),[
                'Output: {}  |  Originals: {}'.format(o.output_summary(),
                                                      'Keep' if o.keep_originals else 'Replace'),
                'Drag to merge  /  Alt: erase regions or edges',
                'Aqua: merged  /  Grey: separate  /  Gold: hover'],
                'Enter / Space to finish  /  Undo: last stroke  /  Esc to cancel')


class Mouse(Rhino.UI.MouseCallback):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def valid(self, e):
        return (not self.owner.closed and
                e.View.Document.RuntimeSerialNumber == self.owner.doc.RuntimeSerialNumber)

    def point(self, e):
        ok, line = e.View.ActiveViewport.GetFrustumLine(e.ViewportPoint.X, e.ViewportPoint.Y)
        if not ok:
            return None
        ok, t = G.Intersect.Intersection.LinePlane(line, self.owner.plane)
        return line.PointAt(t) if ok else None

    def update(self, e):
        o = self.owner
        if o.panel is not None and o.panel.contains(e.ViewportPoint):
            if o.dragging:
                o.apply_stroke()
            o.hover = None
            o.edge_hover = None
            o.last_point = None
            o.doc.Views.Redraw()
            return
        p = self.point(e)
        if p is None:
            return
        if o.dragging and o.last_point is not None:
            o.stroke_segment(o.last_point, p)
        if not o.dragging:
            o.erase = bool(win.Control.ModifierKeys & win.Keys.Alt)
        o.edge_hover = o.hit_edge(p,e.View.ActiveViewport) if o.erase else None
        o.hover = None if o.edge_hover is not None else o.hit(p)
        if o.dragging and o.hover is not None:
            o.touch(o.hover)
        if o.dragging and o.edge_hover is not None:
            o.stroke_edges.add(o.edge_hover)
        o.last_point = p
        o.update_pending()
        o.doc.Views.Redraw()

    def OnMouseMove(self, e):
        if self.valid(e):
            try:
                self.update(e)
                if self.owner.dragging:
                    e.Cancel = True
            except Exception as error:
                self.owner.fail(error)

    def OnMouseDown(self, e):
        if not self.valid(e) or str(e.Button) != 'Left':
            return
        try:
            o = self.owner
            if o.panel is not None and o.panel.contains(e.ViewportPoint):
                e.Cancel = True
                return
            o.begin_stroke(bool(win.Control.ModifierKeys & win.Keys.Alt))
            self.update(e)
            e.Cancel = True
        except Exception as error:
            self.owner.fail(error)

    def OnMouseUp(self, e):
        if not self.valid(e) or str(e.Button) != 'Left' or not self.owner.dragging:
            return
        try:
            self.update(e)
            self.owner.apply_stroke()
            e.Cancel = True
        except Exception as error:
            self.owner.fail(error)

    def OnMouseLeave(self, e):
        if self.valid(e):
            try:
                # Mouse-up can be delivered to another window after leaving a view.
                # Finish at the last sampled point instead of leaving a stuck stroke.
                if self.owner.dragging:
                    self.owner.apply_stroke()
                self.owner.hover = None
                self.owner.edge_hover = None
                self.owner.last_point = None
                self.owner.doc.Views.Redraw()
            except Exception as error:
                self.owner.fail(error)


class Builder:
    def __init__(self, doc, curves):
        self.doc = doc
        self.tol = doc.ModelAbsoluteTolerance
        self.curves = []
        self.sources = []
        self.source_ids = set()
        self.input_geometry = []
        self.hatch_entries = []
        self.curve_entries = []
        self.curve_inputs = []
        self.curve_domains = []
        self.keep_originals = False
        self.pending_loops = []
        self.pending_key = None
        self.leftovers = []
        self.pending_leftovers = None
        self.affected = set()
        self.edge_atoms = {}
        self.erased_edges = set()
        self.stroke_edges = set()
        self.edge_hover = None
        self.cells = []
        self.neighbours = []
        self.groups = []
        self.masters = {}
        self.history = []
        self.outlines = []
        self.group_outlines = []
        self.hover = None
        self.stroke = set()
        self.stroke_start = None
        self.stroke_master = None
        self.dragging = False
        self.erase = False
        self.closed = False
        self.last_point = None
        self.panel = None
        self.getter = None
        try:
            self.prepare_inputs(curves)
        except Exception:
            self.dispose_geometry()
            raise
        # Derive one plane from all control points; never silently project 3D inputs.
        points = []
        for c in self.curves:
            n = c.ToNurbsCurve()
            try:
                points.extend(p.Location for p in n.Points)
            finally:
                n.Dispose()
        result, self.plane = G.Plane.FitPlaneToPoints(List[G.Point3d](points))
        if result != G.PlaneFitResult.Success or any(abs(self.plane.DistanceTo(p)) > self.tol for p in points):
            self.dispose_geometry()
            raise ValueError('Select curves lying on one shared plane.')
        try:
            if self.hatch_entries and self.curve_inputs:
                try:
                    self.curve_domains = boundaries(self.curve_inputs,self.plane,self.tol)
                except ValueError:
                    self.curve_domains = []
            for loops in boundaries(self.curves, self.plane, self.tol):
                cell = Cell(loops, self.plane, self.tol)
                covered = (any(inside_loops(entry['loops'],cell.seed,self.plane,self.tol) for entry in self.hatch_entries) or
                           any(inside_loops(region,cell.seed,self.plane,self.tol) for region in self.curve_domains))
                if self.hatch_entries and not covered:
                    cell.dispose()
                else:
                    self.cells.append(cell)
            if not self.cells:
                raise ValueError('The selected curves do not enclose any regions.')
            self.neighbours = [set() for _ in self.cells]
            for i, cell in enumerate(self.cells):
                for j in range(i):
                    if self.share_edge(cell, self.cells[j]):
                        self.neighbours[i].add(j)
                        self.neighbours[j].add(i)
            self.groups = [{i} for i in range(len(self.cells))]
            self.masters = {frozenset(g):self.default_style(g) for g in self.groups}
            self.build_edge_atoms()
            self.rebuild()
        except Exception:
            self.dispose_geometry()
            raise

    def prepare_inputs(self, inputs):
        for item in inputs:
            obj = item if isinstance(item, Rhino.DocObjects.RhinoObject) else None
            geometry = obj.Geometry if obj is not None else item
            if not isinstance(geometry, (G.Curve, G.Hatch)):
                raise ValueError('Select curves or hatches.')
            if obj is not None:
                if obj.IsLocked or obj.IsReference or obj.IsInstanceDefinitionGeometry:
                    raise ValueError('Select editable curves or hatches outside block definitions.')
                if obj.Id in self.source_ids:
                    continue
                self.sources.append({'id':obj.Id, 'serial':obj.RuntimeSerialNumber,
                                     'crc':geometry.DataCRC(0)})
                self.source_ids.add(obj.Id)
            attributes = obj.Attributes.Duplicate() if obj is not None else None
            owned = geometry.Duplicate()
            self.input_geometry.append(owned)
            if isinstance(owned, G.Hatch):
                loops = list(owned.Get3dCurves(True) or []) + list(owned.Get3dCurves(False) or [])
                self.hatch_entries.append({'hatch':owned,'loops':loops,'attributes':attributes})
                self.curves.extend(loops)
            else:
                curve = owned.DuplicateCurve()
                self.curves.append(curve)
                self.curve_inputs.append(curve)
                self.curve_entries.append({'hatch':None,'loops':[curve],'attributes':attributes,
                                           'source_id':obj.Id if obj is not None else None})

    def clear_pending(self):
        for loops in self.pending_loops:
            for c in loops:
                c.Dispose()
        self.pending_loops = []
        self.pending_key = None
        leftover_geometry.dispose_records(self.pending_leftovers)
        self.pending_leftovers = None

    def build_edge_atoms(self):
        for entry_index,entry in enumerate(self.curve_entries):
            curve = entry['loops'][0]
            if curve.IsClosed:
                continue
            for segment_index,domain in enumerate(leftover_geometry.edge_intervals(curve,self.curves,self.tol)):
                piece = curve.Trim(*domain)
                if piece is None:
                    raise ValueError('Could not prepare an open curve edge.')
                self.edge_atoms[(entry_index,segment_index)] = {'entry':entry,'domain':domain,'curve':piece}

    def visible_edges(self):
        domains = {id(record['entry']):[p.Domain for p in record['pieces']] for record in self.leftovers}
        for key,atom in self.edge_atoms.items():
            middle = (atom['domain'][0]+atom['domain'][1])/2
            if key not in self.erased_edges and any(d.T0<=middle<=d.T1 for d in domains.get(id(atom['entry']),[])):
                yield key,atom

    def hit_edge(self, point, viewport=None):
        best = 7.0 if viewport is not None else self.tol
        target = viewport.WorldToClient(point) if viewport is not None else point
        found = None
        for key,atom in self.visible_edges():
            ok,t = atom['curve'].ClosestPoint(point)
            if not ok:
                continue
            closest = atom['curve'].PointAt(t)
            if viewport is not None:
                q = viewport.WorldToClient(closest)
                distance = ((target.X-q.X)**2+(target.Y-q.Y)**2)**0.5
            else:
                distance = point.DistanceTo(closest)
            if distance<=best:
                found,best = key,distance
        return found

    def calculate_leftovers(self, affected, erased_edges=None):
        erased_edges = self.erased_edges if erased_edges is None else erased_edges
        edges = [curve for index in sorted(affected) for curve in self.cells[index].loops]
        records = []
        try:
            for entry in self.curve_entries:
                curve = entry['loops'][0]
                if curve.IsClosed:
                    continue
                erased = [self.edge_atoms[key]['domain'] for key in erased_edges if self.edge_atoms[key]['entry'] is entry]
                pieces,consumed = leftover_geometry.remaining_parts(curve,edges,self.tol,erased)
                records.append({'entry':entry,'pieces':pieces,'consumed':consumed})
            return records
        except Exception:
            leftover_geometry.dispose_records(records)
            raise

    def preview_leftovers(self):
        return self.pending_leftovers if self.pending_leftovers is not None else self.leftovers

    def leftover_colour(self, entry):
        attr = entry['attributes']
        if attr is None:
            return EDGE
        if attr.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject:
            return attr.ObjectColor
        if 0<=attr.LayerIndex<self.doc.Layers.Count:
            return self.doc.Layers[attr.LayerIndex].Color
        return EDGE

    def is_output_group(self, group):
        # An untouched region formed solely by open curves is a potential region,
        # not permission to convert those curves into a closed object.
        return self.filled_style(group) is not None or bool(group & self.affected)

    def stroke_changes(self, members):
        return bool(members) and (self.erase or sum(1 for g in self.groups if g & members)>1 or
                                 any(g & members and not self.is_output_group(g) for g in self.groups))

    def update_pending(self):
        members = self.active_members() if self.dragging else set()
        if not self.stroke_changes(members):
            members = set()
        edge_hits = self.stroke_edges if self.dragging and self.erase else set()
        key = (frozenset(members),self.erase,frozenset(edge_hits))
        if key == self.pending_key:
            return
        self.clear_pending()
        self.pending_key = key
        if members or edge_hits:
            self.pending_leftovers = self.calculate_leftovers(self.affected | members,self.erased_edges | edge_hits)
        if len(members)>1 and not self.erase:
            for group in self.components(members):
                self.pending_loops.extend(boundaries(self.curves,self.plane,self.tol,
                                                    [self.cells[i].seed for i in sorted(group)]))

    def filled_style(self, group):
        """An existing filled shape, independent of an open boundary's style."""
        for entry in self.hatch_entries:
            if any(inside_loops(entry['loops'],self.cells[i].seed,self.plane,self.tol) for i in group):
                return entry
        for entry in self.curve_entries:
            if entry['loops'][0].IsClosed and any(inside_loops(entry['loops'],self.cells[i].seed,self.plane,self.tol)
                                                 for i in group):
                return entry
        return None

    def default_style(self, group):
        entry = self.filled_style(group)
        if entry is not None:
            return entry
        # Open curves can supply attributes without promoting an untouched region.
        # Prefer the curve contributing the longest boundary, ignoring unrelated
        # curves and point intersections. Selection order breaks equal-length ties.
        best, length = None, self.tol
        for candidate in self.curve_entries:
            curve = candidate['loops'][0]
            if curve.IsClosed:
                continue
            overlap = 0.0
            for i in sorted(group):
                for edge in self.cells[i].loops:
                    events = G.Intersect.Intersection.CurveCurve(curve,edge,self.tol,self.tol)
                    if events:
                        try:
                            overlap += sum(curve.GetLength(e.OverlapA) for e in events if e.IsOverlap)
                        finally:
                            events.Dispose()
            if overlap > self.tol and (best is None or overlap > length + self.tol):
                best, length = candidate, overlap
        return best

    def output_style(self, group):
        key = frozenset(group)
        return self.masters[key] if key in self.masters else self.default_style(group)

    def group_is_hatch(self, group):
        entry = self.output_style(group)
        return entry is not None and entry['hatch'] is not None

    def output_summary(self):
        if self.dragging and self.stroke_start is not None:
            return 'Hatch (drag)' if self.stroke_master and self.stroke_master['hatch'] is not None else 'Curve (drag)'
        outputs = [g for g in self.groups if self.is_output_group(g)]
        hatches = sum(self.group_is_hatch(g) for g in outputs)
        curves = len(outputs)-hatches
        return '{} curve{} / {} hatch{}'.format(curves,'' if curves==1 else 's',hatches,'es' if hatches!=1 else '')

    def begin_stroke(self, erase=False):
        self.dragging = True
        self.erase = erase
        self.stroke = set()
        self.stroke_edges = set()
        self.stroke_start = None
        self.stroke_master = None
        self.last_point = None

    def touch(self, index):
        if self.stroke_start is None:
            self.stroke_start = index
            group = next(g for g in self.groups if index in g)
            self.stroke_master = self.output_style(group)
        self.stroke.add(index)

    def share_edge(self, a, b):
        for ca in a.loops:
            for cb in b.loops:
                events = G.Intersect.Intersection.CurveCurve(ca, cb, self.tol, self.tol)
                if events:
                    try:
                        if any(e.IsOverlap and ca.GetLength(e.OverlapA) > self.tol for e in events):
                            return True
                    finally:
                        events.Dispose()
        return False

    def components(self, members):
        remaining = set(members)
        result = []
        while remaining:
            group = {remaining.pop()}
            queue = list(group)
            while queue:
                for index in self.neighbours[queue.pop()] & remaining:
                    remaining.remove(index)
                    group.add(index)
                    queue.append(index)
            result.append(group)
        return result

    def hit(self, p):
        for i, c in enumerate(self.cells):
            if any(i in group for group in self.groups) and c.contains(p):
                return i
        return None

    def active_members(self):
        picked = self.stroke if self.dragging else ({self.hover} if self.hover is not None else set())
        return set().union(*(g for g in self.groups if g & picked)) if picked else set()

    def stroke_segment(self, a, b):
        if a.DistanceTo(b) <= self.tol:
            return
        line = G.LineCurve(a, b)
        parameters = [line.Domain.T0, line.Domain.T1]
        try:
            if self.erase:
                for key,atom in self.visible_edges():
                    events = G.Intersect.Intersection.CurveCurve(line,atom['curve'],self.tol,self.tol)
                    if events is not None:
                        try:
                            if events.Count:self.stroke_edges.add(key)
                        finally:events.Dispose()
            for cell in self.cells:
                for loop in cell.loops:
                    events = G.Intersect.Intersection.CurveCurve(line, loop, self.tol, self.tol)
                    if events:
                        try:
                            for event in events:
                                parameters.append(event.ParameterA)
                                if event.IsOverlap:
                                    parameters.append(event.OverlapA.T1)
                        finally:
                            events.Dispose()
            parameters = sorted(set(parameters))
            for start, end in zip(parameters, parameters[1:]):
                index = self.hit(line.PointAt((start + end) / 2))
                if index is not None:
                    self.touch(index)
        finally:
            line.Dispose()

    def rebuild(self):
        fresh = []
        grouped = []
        try:
            for group in self.groups:
                if len(group) == 1:
                    regions = [[c.DuplicateCurve() for c in self.cells[next(iter(group))].loops]]
                else:
                    regions = boundaries(self.curves, self.plane, self.tol,
                                         [self.cells[i].seed for i in sorted(group)])
                fresh.extend(regions)
                grouped.append((set(group), regions))
            fresh_leftovers = self.calculate_leftovers(self.affected)
        except Exception:
            for loops in fresh:
                for c in loops:
                    c.Dispose()
            raise
        for loops in self.outlines:
            for c in loops:
                c.Dispose()
        self.outlines = fresh
        self.group_outlines = grouped
        leftover_geometry.dispose_records(self.leftovers)
        self.leftovers = fresh_leftovers

    def apply_stroke(self):
        members = self.active_members()
        self.clear_pending()
        self.dragging = False
        self.stroke = set()
        self.last_point = None
        if self.stroke_changes(members) or (self.erase and self.stroke_edges):
            old = ([set(g) for g in self.groups],dict(self.masters),set(self.affected),set(self.erased_edges))
            self.affected.update(members)
            self.erased_edges.update(self.stroke_edges if self.erase else set())
            self.groups = [g for g in self.groups if not g & members]
            self.masters = {frozenset(g):self.masters[frozenset(g)] for g in self.groups}
            if not self.erase:
                for group in self.components(members):
                    self.groups.append(group)
                    self.masters[frozenset(group)] = (self.stroke_master if self.stroke_start in group
                                                       else self.default_style(group))
            try:
                self.rebuild()
            except Exception:
                self.groups,self.masters,self.affected,self.erased_edges = old
                raise
            self.history.append(old)
        self.stroke_start = None
        self.stroke_master = None
        self.stroke_edges = set()
        self.edge_hover = None
        self.doc.Views.Redraw()

    def undo(self, sender=None, event=None):
        self.clear_pending()
        self.stroke_edges = set()
        self.edge_hover = None
        if self.dragging:
            self.dragging = False
            self.stroke = set()
            self.last_point = None
        if self.history:
            self.groups,self.masters,self.affected,self.erased_edges = self.history.pop()
            self.rebuild()
            self.hover = None
            self.doc.Views.Redraw()

    def status_text(self):
        merged = sum(len(g)>1 for g in self.groups)
        return '{} merged | {} separate'.format(merged,len(self.groups)-merged)

    def make_outputs(self):
        """Prepare and validate all geometry before changing document objects."""
        prepared = []
        try:
            for group, regions in self.group_outlines:
                if not self.is_output_group(group):
                    continue
                entry = self.output_style(group)
                for loops in regions:
                    attr = (entry['attributes'].Duplicate() if entry and entry['attributes'] is not None
                            else Rhino.DocObjects.ObjectAttributes())
                    if not entry or entry['attributes'] is None:
                        attr.LayerIndex = self.doc.Layers.CurrentLayerIndex
                    attr.RemoveFromAllGroups()
                    if not entry or entry['attributes'] is None:
                        attr.Name = 'Shape Builder result'
                    if self.group_is_hatch(group):
                        style = entry['hatch'] if entry else None
                        areas = []
                        for c in loops:
                            props = G.AreaMassProperties.Compute(c)
                            if props is None:
                                raise ValueError('Could not classify a hatch boundary.')
                            areas.append(abs(props.Area))
                            props.Dispose()
                        outer = max(range(len(loops)),key=lambda i:areas[i])
                        hatch_plane = style.Plane if style else self.plane
                        pattern_index = style.PatternIndex if style else -1
                        # This overload expects curves in the hatch's local XY coordinates.
                        # It also rejects negative built-in indices; assign those afterwards.
                        local = [c.DuplicateCurve() for c in loops]
                        try:
                            transform = G.Transform.PlaneToPlane(hatch_plane,G.Plane.WorldXY)
                            for c in local:
                                c.Transform(transform)
                            hatch = G.Hatch.Create(hatch_plane,local[outer],
                                                   net_curves(c for i,c in enumerate(local) if i != outer),
                                                   max(0,pattern_index),
                                                   style.PatternRotation if style else 0.0,
                                                   style.PatternScale if style else 1.0)
                            if hatch is not None:
                                hatch.PatternIndex = pattern_index
                        finally:
                            for c in local:
                                c.Dispose()
                        if hatch is None or not hatch.IsValid:
                            if hatch is not None:
                                hatch.Dispose()
                            raise ValueError('Rhino could not create a valid result hatch.')
                        if style:
                            hatch.BasePoint = style.BasePoint
                            gradient = style.GetGradientFill()
                            if gradient is not None:
                                hatch.SetGradientFill(gradient)
                        prepared.append(([hatch],attr))
                    else:
                        prepared.append(([c.DuplicateCurve() for c in loops],attr))
            for record in self.leftovers:
                entry = record['entry']
                if entry['source_id'] is not None and (self.keep_originals or not record['consumed']):
                    continue
                for piece in record['pieces']:
                    attr = (entry['attributes'].Duplicate() if entry['attributes'] is not None
                            else Rhino.DocObjects.ObjectAttributes())
                    if entry['attributes'] is None:
                        attr.LayerIndex = self.doc.Layers.CurrentLayerIndex
                    attr.RemoveFromAllGroups()
                    prepared.append(([piece.DuplicateCurve()],attr))
            return prepared
        except Exception:
            for geometries,attr in prepared:
                for geometry in geometries:
                    geometry.Dispose()
                attr.Dispose()
            raise

    def delete_source(self, source):
        if not self.doc.Objects.Delete(source['id'],True):
            raise RuntimeError('Could not replace an original object.')

    def commit_output(self):
        for source in self.sources:
            obj = self.doc.Objects.FindId(source['id'])
            if (obj is None or obj.IsDeleted or obj.RuntimeSerialNumber != source['serial'] or
                    obj.Geometry.DataCRC(0) != source['crc'] or obj.IsLocked or obj.IsReference):
                raise RuntimeError('Shape Builder could not access an input object.')
        prepared = self.make_outputs()
        ids, deleted, added_groups, added_patterns = [], [], [], []
        record = self.doc.BeginUndoRecord('RUT Shape Builder')
        try:
            for geometries,attr in prepared:
                group_ids = []
                for geometry in geometries:
                    if isinstance(geometry,G.Hatch) and geometry.PatternIndex < 0:
                        solid = next((p for p in self.doc.HatchPatterns
                                      if not p.IsDeleted and p.FillType == Rhino.DocObjects.HatchPatternFillType.Solid),None)
                        index = solid.Index if solid else self.doc.HatchPatterns.Add(Rhino.DocObjects.HatchPattern.Defaults.Solid)
                        if index < 0:
                            raise RuntimeError('Could not create the solid hatch pattern.')
                        if solid is None:
                            added_patterns.append(index)
                        geometry.PatternIndex = index
                    ident = (self.doc.Objects.AddHatch(geometry,attr) if isinstance(geometry,G.Hatch)
                             else self.doc.Objects.AddCurve(geometry,attr))
                    if str(ident) == '00000000-0000-0000-0000-000000000000':
                        raise RuntimeError('Could not add a result object.')
                    ids.append(ident)
                    group_ids.append(ident)
                if len(group_ids)>1:
                    group_index = self.doc.Groups.Add(group_ids)
                    if group_index < 0:
                        raise RuntimeError('Could not group the result boundaries.')
                    added_groups.append(group_index)
            if not self.keep_originals:
                retained_ids = {record['entry']['source_id'] for record in self.leftovers
                                if not record['consumed']}
                for source in self.sources:
                    if source['id'] in retained_ids:
                        continue
                    self.delete_source(source)
                    deleted.append(source)
            return ids
        except Exception:
            for source in reversed(deleted):
                if not self.doc.Objects.Undelete(source['serial']):
                    Rhino.RhinoApp.WriteLine('Shape Builder: could not restore an original; use Rhino Undo.')
            for index in added_groups:
                self.doc.Groups.Delete(index)
            for ident in ids:
                self.doc.Objects.Delete(ident,True)
            for index in added_patterns:
                self.doc.HatchPatterns.Delete(index,True)
            raise
        finally:
            self.doc.EndUndoRecord(record)
            for geometries,attr in prepared:
                for geometry in geometries:
                    geometry.Dispose()
                attr.Dispose()

    def finish(self, sender=None, event=None):
        if self.dragging:
            self.apply_stroke()
        try:
            ids = self.commit_output()
        except Exception as error:
            Rhino.RhinoApp.WriteLine('Shape Builder: ' + str(error))
            return False
        self.doc.Objects.UnselectAll()
        for ident in ids:
            self.doc.Objects.Select(ident)
        Rhino.RhinoApp.WriteLine('Shape Builder: created {} {}; originals {}.'.format(
            len(ids),'result objects',
            'kept' if self.keep_originals else 'replaced'))
        self.close()
        return True

    def fail(self, error):
        Rhino.RhinoApp.WriteLine('Shape Builder stopped: ' + str(error))
        self.close()

    def document_closed(self, sender, event):
        if event.Document.RuntimeSerialNumber == self.doc.RuntimeSerialNumber:
            self.close()

    def dispose_geometry(self):
        self.clear_pending()
        leftover_geometry.dispose_records(self.leftovers)
        for atom in self.edge_atoms.values():
            atom['curve'].Dispose()
        for c in self.cells:
            c.dispose()
        for loops in self.outlines:
            for c in loops:
                c.Dispose()
        for c in self.curves:
            c.Dispose()
        for loops in self.curve_domains:
            for c in loops:
                c.Dispose()
        for geometry in self.input_geometry:
            geometry.Dispose()
        for entry in self.hatch_entries+self.curve_entries:
            if entry['attributes'] is not None:
                entry['attributes'].Dispose()

    def close(self, sender=None, event=None):
        if self.closed:
            return
        self.closed = True
        if self.getter is not None:
            self.getter.PostCustomMessage('ShapeBuilderCancel')
        if getattr(self,'mouse',None) is not None:
            self.mouse.Enabled = False
        if getattr(self,'preview',None) is not None:
            self.preview.Enabled = False
            self.preview.good.Dispose()
            self.preview.bad.Dispose()
            self.preview.separate.Dispose()
            self.preview.hover.Dispose()
        if getattr(self,'document_hook',False):
            Rhino.RhinoDoc.CloseDocument -= self.document_closed
        if self.panel is not None:
            self.panel.dispose()
        self.dispose_geometry()
        if sc.sticky.get(KEY) is self:
            del sc.sticky[KEY]
        self.doc.Views.Redraw()

    def show(self):
        self.panel = viewport_ui.AquaPanel()
        self.mouse = Mouse(self)
        self.preview = Preview(self)
        Rhino.RhinoDoc.CloseDocument += self.document_closed
        self.document_hook = True
        self.doc.Objects.UnselectAll()
        sc.sticky[KEY] = self
        self.preview.Enabled = True
        self.mouse.Enabled = True
        self.doc.Views.Redraw()

    def run(self):
        """Own native Rhino input until Finish or Cancel; never run modeless."""
        go = Rhino.Input.Custom.GetOption()
        self.getter = go
        try:
            go.SetCommandPrompt('Shape Builder: drag to merge, Alt-drag to erase. Enter or Space to finish')
            go.AcceptNothing(True)
            go.AcceptUndo(True)
            go.AcceptCustomMessage(True)
            go.EnableTransparentCommands(False)
            self.show()
            while not self.closed:
                go.ClearCommandOptions()
                keep = Rhino.Input.Custom.OptionToggle(self.keep_originals,'No','Yes')
                go.AddOptionToggle('KeepOriginals',keep)
                finish = go.AddOption('Finish')
                cancel = go.AddOption('Cancel')
                result = go.Get()
                if self.closed:
                    break
                if result == Rhino.Input.GetResult.Nothing:
                    if self.finish():
                        break
                elif result == Rhino.Input.GetResult.Undo:
                    self.undo()
                elif result == Rhino.Input.GetResult.Option:
                    index = go.OptionIndex()
                    if index == finish:
                        if self.finish():
                            break
                    elif index == cancel:
                        break
                    else:
                        self.keep_originals = bool(keep.CurrentValue)
                        self.doc.Views.Redraw()
                else:
                    break
        finally:
            self.getter = None
            go.Dispose()
            self.close()


def start(doc, curves=None):
    for key in (KEY, 'RUT.ShapeBuilderPrototype'):
        old = sc.sticky.get(key)
        if old:
            old.close()
    if curves is None:
        picker = Rhino.Input.Custom.GetObject()
        picker.SetCommandPrompt('Select coplanar curves or hatches for Shape Builder')
        picker.GeometryFilter = Rhino.DocObjects.ObjectType.Curve | Rhino.DocObjects.ObjectType.Hatch
        picker.SubObjectSelect = False
        try:
            picker.GetMultiple(1, 0)
            if picker.CommandResult() != Rhino.Commands.Result.Success:
                return
            curves = [picker.Object(i).Object() for i in range(picker.ObjectCount)]
        finally:
            picker.Dispose()
    try:
        tool = Builder(doc, curves)
        tool.run()
        return tool
    except Exception as error:
        Rhino.RhinoApp.WriteLine('Shape Builder: ' + str(error))


if __name__ == '__main__':
    start(globals().get('__rhino_doc__') or sc.doc)
