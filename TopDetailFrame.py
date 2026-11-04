#! python 3
# -*- coding: utf-8 -*-
"""Rhino Urbanism prototype: move a model frame to pan a Top layout detail.

Run in Rhino 8 ScriptEditor (Python 3). Link from a layout; then use normal
Move or Gumball in model space. Run again for Link / Refresh / Stop.
Session-only controller; see TopDetailFrame.md for limitations and checks.
"""
import math
import time

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from System.Drawing import Color
from System import Guid

KEY = "rhino-urbanism.TopDetailFrame.controller.v1"
TAG = "rhino-urbanism.TopDetailFrame.detail"
CONTROLLER_REVISION = 2


def xy_translation(before, after, tolerance):
    """Return XY displacement only if every ordered vertex moved equally."""
    if len(before) != 5 or len(after) != 5:
        raise ValueError("The linked frame must remain a closed four-sided polyline.")
    if not all(math.isfinite(v) for p in before + after for v in p):
        raise ValueError("Invalid frame coordinates.")
    delta = tuple(after[0][i] - before[0][i] for i in range(3))
    if abs(delta[2]) > tolerance:
        raise ValueError("Only movement in World XY is supported. Undo the Z move.")
    for old, new in zip(before, after):
        if any(abs(new[i] - old[i] - delta[i]) > tolerance for i in range(3)):
            raise ValueError("Only Move is supported. Undo the scale, rotation or edit.")
    return delta[0], delta[1], 0.0


def tuples(points):
    return [(p.X, p.Y, p.Z) for p in points]


def frame_points(obj):
    if not isinstance(obj.Geometry, Rhino.Geometry.PolylineCurve):
        raise ValueError("The linked frame must remain a polyline. Undo the edit.")
    ok, polyline = obj.Geometry.TryGetPolyline()
    if not ok:
        raise ValueError("Cannot read linked frame.")
    return tuples(list(polyline))


def detail_outline(detail):
    vp = detail.Viewport
    direction = Rhino.Geometry.Vector3d(vp.CameraDirection)
    direction.Unitize()
    if not vp.IsParallelProjection or (direction - Rhino.Geometry.Vector3d(0, 0, -1)).Length > 1e-8:
        raise ValueError("Choose a parallel World Top detail, looking down World Z.")
    if detail.DetailGeometry.IsProjectionLocked:
        raise ValueError("Unlock this detail before linking or moving its frame.")
    # Near-plane corners are already in model units, including layout scale.
    # For parallel Top projection their XY coordinates equal the footprint at Z=0.
    corners = vp.GetNearRect()
    if corners is None or len(corners) != 4:
        raise ValueError("Rhino could not determine the detail's visible rectangle.")
    return [(corners[i].X, corners[i].Y, 0.0) for i in (0, 1, 3, 2, 0)]


def curve(points):
    return Rhino.Geometry.PolylineCurve([Rhino.Geometry.Point3d(*p) for p in points])


def same(a, b, tol):
    return len(a) == len(b) and all(abs(x-y) <= tol for p, q in zip(a, b) for x, y in zip(p, q))


def layout_name(doc, detail_id):
    """Find the owning page without newer DetailViewObject.ParentPageView APIs."""
    for page in doc.Views.GetPageViews():
        if any(detail.Id == detail_id for detail in page.GetDetailViews()):
            return page.PageName
    raise ValueError("The source detail no longer belongs to a layout.")


class Controller:
    def __init__(self, doc):
        self.revision = CONTROLLER_REVISION
        self.doc = doc
        self.serial = doc.RuntimeSerialNumber
        self.links = {}
        self.busy = False
        self.last_poll = 0.0
        self.running = True
        self.idle_handler = self.on_idle
        self.close_handler = self.on_close
        Rhino.RhinoApp.Idle += self.idle_handler
        Rhino.RhinoDoc.CloseDocument += self.close_handler

    def stop(self):
        if self.running:
            Rhino.RhinoApp.Idle -= self.idle_handler
            Rhino.RhinoDoc.CloseDocument -= self.close_handler
            self.running = False

    def on_close(self, sender, event):
        if event.Document.RuntimeSerialNumber == self.serial:
            self.stop()

    def warn(self, link, message):
        if link.get("warning") != message:
            Rhino.RhinoApp.WriteLine("TopDetailFrame: " + message)
            link["warning"] = message

    def on_idle(self, sender, event):
        active = Rhino.RhinoDoc.ActiveDoc
        if (self.busy or not self.running or active is None
                or active.RuntimeSerialNumber != self.serial
                or Rhino.Commands.Command.InCommand()
                or self.doc.UndoActive or self.doc.RedoActive):
            return
        now = time.monotonic()
        if now - self.last_poll < 0.2:
            return
        self.last_poll = now
        self.busy = True
        redraw = False
        try:
            for frame_id, link in list(self.links.items()):
                try:
                    redraw = self.sync(frame_id, link) or redraw
                except Exception as error:
                    self.warn(link, str(error))
            if redraw:
                self.doc.Views.Redraw()
        finally:
            self.busy = False

    def sync(self, frame_id, link):
        obj = self.doc.Objects.FindId(frame_id)
        detail = self.doc.Objects.FindId(link["detail"])
        # Retain the mapping so Undo Delete can recover it; never follow copies.
        if obj is None or obj.IsDeleted or detail is None or detail.IsDeleted:
            return False
        tol = max(self.doc.ModelAbsoluteTolerance, 1e-8)
        desired = frame_points(obj)
        xy_translation(link["original"], desired, tol)
        live = detail_outline(detail)
        # Same shape is required; a changed layout scale/rotation needs Refresh.
        xy_translation(link["original"], live, tol)
        if same(desired, link["last"], tol):
            if not same(live, desired, tol):
                self.warn(link, "Layout view changed. Run Refresh before moving its frame.")
                link["stale"] = True
            return False
        if link.get("stale"):
            raise ValueError("Layout view changed. Run Refresh to relink to its current framing.")
        if not same(live, link["last"], tol) and not same(live, desired, tol):
            link["stale"] = True
            raise ValueError("Both layout and frame changed. Run Refresh; layout takes priority.")
        dx, dy, _ = xy_translation(live, desired, tol)
        if abs(dx) > tol or abs(dy) > tol:
            vp = detail.Viewport
            offset = Rhino.Geometry.Vector3d(dx, dy, 0)
            vp.SetCameraLocations(vp.CameraTarget + offset, vp.CameraLocation + offset)
            if not detail.CommitViewportChanges():
                raise RuntimeError("Rhino rejected the camera change. Stop and relink the detail.")
            # Camera is derived from the undoable frame. Do not create an idle
            # undo record, which would add a second undo step and clear Redo.
            fresh = self.doc.Objects.FindId(link["detail"])
            if fresh is None or not same(detail_outline(fresh), desired, tol * 5):
                link["stale"] = True
                raise RuntimeError("Camera verification failed. Run Refresh before continuing.")
        link["last"] = desired
        link["warning"] = None
        return True

    def link(self, detail):
        points = detail_outline(detail)
        # Reuse only the exact frame tracked in this session. After a restart,
        # existing guide curves remain inert; linking creates a fresh guide.
        existing = next((fid for fid, item in self.links.items()
                         if item["detail"] == detail.Id
                         and self.doc.Objects.FindId(fid) is not None), None)
        record = self.doc.BeginUndoRecord("Link Top detail frame")
        try:
            obj = self.doc.Objects.FindId(existing) if existing else None
            if obj is not None and not obj.IsDeleted:
                if not self.doc.Objects.Replace(existing, curve(points)):
                    raise RuntimeError("Cannot refresh frame. Check its layer/object lock.")
                frame_id = existing
            else:
                attrs = Rhino.DocObjects.ObjectAttributes()
                attrs.Name = "Detail frame - " + layout_name(self.doc, detail.Id)
                attrs.SetUserString(TAG, str(detail.Id))
                attrs.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
                attrs.ObjectColor = Color.FromArgb(30, 170, 220)
                # Display in model space only, excluding all layout details.
                attrs.Space = Rhino.DocObjects.ActiveSpace.ModelSpace
                for page in self.doc.Views.GetPageViews():
                    for other in page.GetDetailViews():
                        attrs.AddHideInDetailOverride(other.Viewport.Id)
                frame_id = self.doc.Objects.AddCurve(curve(points), attrs)
                if str(frame_id) == "00000000-0000-0000-0000-000000000000":
                    raise RuntimeError("Rhino could not create the frame.")
            # Rhino assigns new geometry to the active page even when AddCurve
            # receives ModelSpace attributes. Correct the stored attributes after
            # insertion (also repairs older frames when Refresh is used).
            stored = self.doc.Objects.FindId(frame_id)
            model_attrs = stored.Attributes.Duplicate()
            model_attrs.Space = Rhino.DocObjects.ActiveSpace.ModelSpace
            model_attrs.ViewportId = Guid.Empty
            if not self.doc.Objects.ModifyAttributes(frame_id, model_attrs, True):
                raise RuntimeError("Cannot assign the frame to model space.")
            stored = self.doc.Objects.FindId(frame_id)
            if (stored.Attributes.Space != Rhino.DocObjects.ActiveSpace.ModelSpace
                    or stored.Attributes.ViewportId != Guid.Empty):
                raise RuntimeError("Rhino did not retain the model-space frame assignment.")
            for old_id, old_link in list(self.links.items()):
                if old_link["detail"] == detail.Id and old_id != frame_id:
                    del self.links[old_id]
            self.links[frame_id] = {"detail": detail.Id, "original": points,
                                    "last": points, "stale": False}
        finally:
            if record:
                self.doc.EndUndoRecord(record)
        self.doc.Views.Redraw()
        print("Linked: {}. In model space, move the cyan frame in World XY.".format(
            layout_name(self.doc, detail.Id)))

    def refresh(self):
        for item in list(self.links.values()):
            detail = self.doc.Objects.FindId(item["detail"])
            if detail is not None and not detail.IsDeleted:
                self.link(detail)


def main():
    controller = sc.sticky.get(KEY)
    if controller and (not controller.running or controller.serial != sc.doc.RuntimeSerialNumber):
        controller.stop()
        controller = None
    if controller and getattr(controller, "revision", 0) != CONTROLLER_REVISION:
        # Replace old callbacks after updating the script, retaining frame IDs
        # so Refresh can repair the existing guides rather than duplicating them.
        previous = controller
        previous.stop()
        controller = Controller(sc.doc)
        controller.links = previous.links.copy()
        sc.sticky[KEY] = controller
    action = rs.GetString("Top detail frame prototype", "Link", ["Link", "Refresh", "Stop"])
    if not action:
        return
    if action == "Stop":
        if controller:
            controller.stop()
        sc.sticky.pop(KEY, None)
        print("Top detail frame listener stopped. Guide curves remain as ordinary geometry.")
        return
    if controller is None:
        controller = Controller(sc.doc)
        sc.sticky[KEY] = controller
    try:
        if action == "Refresh":
            controller.refresh()
            return
        getter = Rhino.Input.Custom.GetObject()
        getter.SetCommandPrompt("On a layout, select an unlocked Top detail border")
        getter.GeometryFilter = Rhino.DocObjects.ObjectType.Detail
        getter.Get()
        if getter.CommandResult() != Rhino.Commands.Result.Success:
            return
        detail = getter.Object(0).Object()
        controller.link(detail)
    except Exception as error:
        print("TopDetailFrame: " + str(error))


if __name__ == "__main__":
    main()
