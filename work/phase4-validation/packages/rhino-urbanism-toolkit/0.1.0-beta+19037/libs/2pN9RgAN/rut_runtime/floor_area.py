# -*- coding: utf-8 -*-
"""Shared measurement and presentation primitives for the floor-area commands."""
import math
import Rhino
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing
from System.Drawing import Color
import urbanism_ui as ui
import viewport_ui

AREA_UNITS = (('m²', 'm²', 1.0), ('km²', 'km²', 1000000.0), ('Hectares (ha)', 'ha', 10000.0))
SELECTION_TYPES = (Rhino.DocObjects.ObjectType.Surface | Rhino.DocObjects.ObjectType.Brep |
                   Rhino.DocObjects.ObjectType.Extrusion | Rhino.DocObjects.ObjectType.InstanceReference)


def panel_font_size(size):
    """Match the bitmap HUD's screen-pixel type, including display scaling."""
    pixels = {ui.CAPTION_SIZE: viewport_ui.CAPTION_PIXELS,
              ui.BODY_SIZE: viewport_ui.BODY_PIXELS,
              ui.TITLE_SIZE: viewport_ui.HEADING_PIXELS,
              ui.VALUE_SIZE: viewport_ui.VALUE_PIXELS}[size]
    window = Rhino.UI.RhinoEtoApp.MainWindowForDocument(sc.doc)
    scale = window.Screen.Scale
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.GetDpiForWindow.argtypes = [wintypes.HWND]
        user32.GetDpiForWindow.restype = wintypes.UINT
        dpi = user32.GetDpiForWindow(window.NativeHandle.ToInt64())
        if dpi:
            # Eto's cached Screen.Scale can refer to the previous monitor.
            scale = dpi / 96.0
    return pixels * 72.0 / 96.0 / scale


def panel_label(text, size=ui.BODY_SIZE, muted=False):
    return ui.label(text, panel_font_size(size), muted)


def panel_button(text, primary=False):
    control = ui.button(text, primary)
    control.Font = drawing.Font('Segoe UI', panel_font_size(ui.BODY_SIZE))
    control.Height = 30
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        from System.Windows import Thickness
        control.ControlObject.Padding = Thickness(10, 5, 10, 5)
    return control


def panel_dialog(title, category, heading, description, floating=False):
    dialog = (ui.AquaForm if floating else ui.AquaDialog)(title, category, heading, description)
    dialog.MinimumSize = drawing.Size(380, 0)
    dialog.body.Padding = drawing.Padding(16)
    dialog.body.Spacing = drawing.Size(8, 10)
    dialog.close_button.Size = drawing.Size(24, 24)
    for control in dialog.header.Controls:
        if isinstance(control, forms.Label):
            control.Font = drawing.Font('Segoe UI', panel_font_size(ui.CAPTION_SIZE))
    for control in dialog.body.Controls:
        if isinstance(control, forms.Label):
            control.Font = drawing.Font('Segoe UI', panel_font_size(control.Font.Size))
    dialog.status.Font = drawing.Font('Segoe UI', panel_font_size(ui.CAPTION_SIZE))
    dialog.close_button.Font = drawing.Font('Segoe UI', panel_font_size(ui.BODY_SIZE))
    return dialog


def area_in_unit(value, unit_index, model_units=None):
    model_units = sc.doc.ModelUnitSystem if model_units is None else model_units
    to_metres = Rhino.RhinoMath.UnitScale(model_units, Rhino.UnitSystem.Meters)
    return value * to_metres * to_metres / AREA_UNITS[unit_index][2]


def try_face_plane(face, tol):
    is_planar, plane = face.TryGetPlane(tol)
    return is_planar, (plane if is_planar else None)


def is_near_horizontal(normal, ang_tol_rad):
    """
    Tests whether a face normal is nearly vertical, meaning the face itself is nearly horizontal.

    The face normal may point up or down depending on Brep orientation, so we compare to both +Z and -Z.
    """
    if not normal.IsValid or normal.IsZero:
        return False
    n = Rhino.Geometry.Vector3d(normal)
    n.Unitize()
    z = Rhino.Geometry.Vector3d(0, 0, 1)
    a = Rhino.Geometry.Vector3d.VectorAngle(n, z)
    a = min(a, abs(math.pi - a))
    return a <= ang_tol_rad


def lowest_horizontal_planar_faces(brep, tol, loose_ang_rad):
    """
    Finds the lowest horizontal planar face candidates on a Brep.

    This is intentionally close to the uploaded QuickArea_v3 logic:
      - first collect planar faces that are approximately horizontal
      - use their area centroid Z as the height reference
      - keep faces whose centroid Z equals the lowest candidate Z within tolerance
    """
    candidates = []

    for i, f in enumerate(brep.Faces):
        is_planar, plane = try_face_plane(f, tol)
        if not is_planar or plane is None:
            continue
        if not is_near_horizontal(plane.Normal, loose_ang_rad):
            continue

        amp = Rhino.Geometry.AreaMassProperties.Compute(f)
        z = amp.Centroid.Z if amp else f.GetBoundingBox(True).Center.Z
        candidates.append((f, i, z))

    if not candidates:
        return []

    min_z = min(z for _, _, z in candidates)
    return [(f, i, z) for (f, i, z) in candidates if abs(z - min_z) <= tol]


def base_area_and_z_from_lowest_faces(brep, tol, loose_ang_rad, strict_ang_rad):
    """
    Returns:
      (success, base_area, base_z, base_face_count, problem_text)

    This is the original QuickArea-style base calculation:
      - find the lowest approximately horizontal planar face candidates
      - require them to be strictly horizontal before counting them
      - sum their Rhino face areas

    The face area returned by AreaMassProperties.Compute(face) respects trimmed face
    boundaries, so holes in a base face should already be subtracted by Rhino.
    """
    lowest = lowest_horizontal_planar_faces(brep, tol, loose_ang_rad)
    if not lowest:
        return False, 0.0, None, 0, "No horizontal planar base face found"

    total_base_area = 0.0
    usable_z_values = []
    usable_face_count = 0

    for face, face_index, z in lowest:
        is_planar, plane = try_face_plane(face, tol)
        if not is_planar or plane is None:
            continue
        if not is_near_horizontal(plane.Normal, strict_ang_rad):
            continue

        amp = Rhino.Geometry.AreaMassProperties.Compute(face)
        if amp is None or amp.Area <= tol * tol:
            continue

        total_base_area += amp.Area
        usable_z_values.append(z)
        usable_face_count += 1

    if not usable_z_values or total_base_area <= tol * tol:
        return False, 0.0, None, 0, "Lowest base face is not strictly horizontal or has no measurable area"

    # Use the minimum centroid Z to avoid accidentally lifting the section plane.
    return True, total_base_area, min(usable_z_values), usable_face_count, None


def clean_joined_section_curves(raw_curves, tol):
    """
    Joins raw Brep/plane intersection segments into closed section loops.

    Brep-plane intersections commonly return several curve segments rather than complete loops.
    Area calculation requires closed curves, so we join first and then keep only closed curves.
    """
    if not raw_curves:
        return [], []

    joined = Rhino.Geometry.Curve.JoinCurves(raw_curves, tol)
    if not joined:
        joined = raw_curves

    closed = []
    open_or_invalid = []

    for crv in joined:
        if crv is None:
            continue
        if crv.IsClosed:
            closed.append(crv)
        else:
            open_or_invalid.append(crv)

    return closed, open_or_invalid


def curve_area_and_centroid(curve):
    """
    Returns (success, absolute_area, centroid).

    AreaMassProperties.Compute(curve) works for closed planar curves.
    We use absolute area because loop orientation can vary.
    """
    amp = Rhino.Geometry.AreaMassProperties.Compute(curve)
    if amp is None:
        return False, 0.0, Rhino.Geometry.Point3d.Unset

    return True, abs(amp.Area), amp.Centroid


def true_filled_area_from_section_loops(section_loops, section_plane, tol):
    """
    Calculates filled section area using nested closed curves.

    Why this is needed:
      A closed perimeter block can section as two loops:
        - outer facade loop
        - inner courtyard loop
      Summing both would over-count the courtyard. Instead, the inner loop must subtract.

    Method:
      1. Compute an area and centroid for each closed loop.
      2. For each loop, count how many larger loops contain its centroid.
      3. Even nesting depth means filled material -> add area.
      4. Odd nesting depth means void/courtyard -> subtract area.

    This is the standard even/odd region rule, and also handles islands inside holes.
    """
    loop_data = []

    for crv in section_loops:
        ok, area, centroid = curve_area_and_centroid(crv)
        if not ok or not math.isfinite(area) or area <= tol * tol or not centroid.IsValid:
            raise ValueError('A section loop has no valid measurable area.')
        loop_data.append({
            "curve": crv,
            "area": area,
            "centroid": centroid,
            "depth": 0
        })

    if not loop_data:
        return 0.0, 0, []

    # Larger loops must be tested first because only a larger loop can contain a smaller loop.
    loop_data.sort(key=lambda d: d["area"], reverse=True)

    for i, item in enumerate(loop_data):
        pt = item["centroid"]
        depth = 0

        for j, other in enumerate(loop_data):
            if i == j:
                continue
            if other["area"] <= item["area"]:
                continue

            containment = other["curve"].Contains(pt, section_plane, tol)
            if containment == Rhino.Geometry.PointContainment.Inside:
                depth += 1

        item["depth"] = depth

    total = 0.0
    for item in loop_data:
        if item["depth"] % 2 == 0:
            total += item["area"]
        else:
            total -= item["area"]

    return total, len(loop_data), loop_data


def section_area_of_solid(brep, tol, loose_ang_rad, strict_ang_rad,
                                 section_curve_output=None, height_metres=1.5, model_units=None):
    """
    Returns:
      (success, section_area, base_area, base_z, section_z, loop_count, base_face_count, problem_text)

    The section area is the filled horizontal section area of the actual closed Brep volume.
    The base area is the original QuickArea-style area of the lowest horizontal planar face(s).
    """
    ok, base_area, base_z, base_face_count, base_problem = base_area_and_z_from_lowest_faces(
        brep,
        tol,
        loose_ang_rad,
        strict_ang_rad
    )

    if not ok:
        return False, 0.0, 0.0, None, None, 0, 0, base_problem

    section_z = base_z + height_metres * Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Meters, sc.doc.ModelUnitSystem if model_units is None else model_units)
    section_plane = Rhino.Geometry.Plane(
        Rhino.Geometry.Point3d(0, 0, section_z),
        Rhino.Geometry.Vector3d.ZAxis
    )

    success, raw_curves, raw_points = Rhino.Geometry.Intersect.Intersection.BrepPlane(
        brep,
        section_plane,
        tol
    )

    if not success or not raw_curves:
        return False, 0.0, base_area, base_z, section_z, 0, base_face_count, 'No section curves at {:g} m above base'.format(height_metres)

    closed_loops, open_curves = clean_joined_section_curves(raw_curves, tol)

    if not closed_loops:
        return False, 0.0, base_area, base_z, section_z, 0, base_face_count, "Section did not produce closed loops"

    area, loop_count, loop_data = true_filled_area_from_section_loops(
        closed_loops,
        section_plane,
        tol
    )

    if area <= tol * tol:
        return False, 0.0, base_area, base_z, section_z, loop_count, base_face_count, "Section area is zero or below tolerance"

    if section_curve_output is not None:
        section_curve_output.extend(item['curve'].DuplicateCurve() for item in loop_data)

    # Any ignored geometry invalidates the whole selection in both commands.
    if open_curves:
        return False, area, base_area, base_z, section_z, loop_count, base_face_count, "Section contains open curves"

    return True, area, base_area, base_z, section_z, loop_count, base_face_count, None


def format_display_number(value, decimals):
    text = '{:.{}f}'.format(value, decimals)
    # Tolerance-scale calculation noise should display as 0.00, not -0.00.
    return text[1:] if text.startswith('-') and float(text) == 0 else text


class SectionPreview(Rhino.Display.DisplayConduit):
    """Temporary world-space section loops; never adds document objects."""
    def __init__(self, doc, curves):
        super().__init__()
        ui.refresh_theme()
        self.doc = doc
        self.curves = curves
        self.SpaceFilter = Rhino.DocObjects.ActiveSpace.ModelSpace
        self.color = Color.FromArgb(177, 228, 223) if ui.DARK else Color.FromArgb(36, 110, 123)
        self.bounds = Rhino.Geometry.BoundingBox.Empty
        for curve in curves:
            self.bounds.Union(curve.GetBoundingBox(True))
        self.draw_count = 0
        self.failed_breps = []
        self.failure_color = Color.FromArgb(240, 171, 153) if ui.DARK else Color.FromArgb(163, 69, 53)

    def set_failures(self, breps):
        self.failed_breps = breps
        for brep in breps:
            self.bounds.Union(brep.GetBoundingBox(True))

    def CalculateBoundingBox(self, event):
        if event.RhinoDoc == self.doc and self.bounds.IsValid:
            event.IncludeBoundingBox(self.bounds)

    def DrawForeground(self, event):
        if event.RhinoDoc != self.doc:
            return
        for curve in self.curves:
            event.Display.DrawCurve(curve, self.color, 3)
        for brep in self.failed_breps:
            # Selected objects are drawn after DrawForeground. A wide halo keeps
            # coral visible around Rhino's native yellow selection wires.
            for edge in brep.Edges:
                event.Display.DrawCurve(edge, self.failure_color, 6)
        self.draw_count += 1


class Measurement:
    """Own all temporary geometry; a result is usable only without issues."""
    def __init__(self):
        self.base = self.section = 0.0
        self.solids = self.faces = self.loops = 0
        self.issues = []
        self.curves = []
        self.failures = []

    @property
    def valid(self):
        return self.solids > 0 and not self.issues

    def dispose(self):
        for geometry in self.curves + self.failures:
            geometry.Dispose()
        self.curves.clear()
        self.failures.clear()


def selected_ids(doc):
    return [obj.Id for obj in doc.Objects.GetSelectedObjects(False, False)]


def object_label(doc, object_id):
    obj = doc.Objects.FindId(object_id)
    name = obj.Attributes.Name if obj else ''
    if not name and isinstance(obj, Rhino.DocObjects.InstanceObject):
        name = obj.InstanceDefinition.Name if obj.InstanceDefinition else ''
    return '{} [{}]'.format(name or 'Object', str(object_id)[:8])


def measure(doc, ids, sections=False, height=1.5):
    """Measure world-space Breps, recursively visiting nested block instances.

    Non-Brep block decoration is ignored. Open/invalid Breps, broken block
    references, empty blocks and unsupported top-level inputs invalidate totals.
    """
    result = Measurement()
    tol = doc.ModelAbsoluteTolerance

    def issue(origin, reason, geometry=None):
        result.issues.append((origin, reason))
        if geometry is not None:
            result.failures.append(geometry.DuplicateBrep())

    def visit(obj, transform, origin, ancestors, inside=False):
        if obj is None or obj.IsDeleted:
            issue(origin, 'Object is missing.')
            return 0
        if isinstance(obj, Rhino.DocObjects.InstanceObject):
            definition = obj.InstanceDefinition
            if definition is None or definition.Id in ancestors:
                issue(origin, 'Missing or recursive block definition.')
                return 0
            combined = Rhino.Geometry.Transform.Multiply(transform, obj.InstanceXform)
            count = 0
            for child in definition.GetObjects() or []:
                count += visit(child, combined, origin, ancestors | {definition.Id}, True)
            if not count:
                issue(origin, 'Block contains no measurable solids.')
                box = obj.Geometry.GetBoundingBox(True)
                if box.IsValid:
                    fallback = Rhino.Geometry.Brep.CreateFromBox(box)
                    if fallback:
                        fallback.Transform(transform)
                        result.failures.append(fallback)
            return count
        if not obj.ObjectType & SELECTION_TYPES:
            if not inside:
                issue(origin, 'Select solids or blocks containing solids.')
            return 0
        brep = Rhino.Geometry.Brep.TryConvertBrep(obj.Geometry)
        if brep is None:
            issue(origin, 'Geometry cannot be converted to a solid.')
            return 1
        world = brep.DuplicateBrep()
        try:
            if not world.Transform(transform):
                issue(origin, 'Block geometry could not be transformed.', world)
            elif not world.IsValid:
                issue(origin, 'Invalid solid geometry.', world)
            elif not world.IsSolid:
                issue(origin, 'Open geometry is not a closed solid.', world)
            else:
                start = len(result.curves)
                if sections:
                    ok, section, base, bz, sz, loops, faces, problem = section_area_of_solid(
                        world, tol, math.radians(30), math.radians(1), result.curves,
                        height, doc.ModelUnitSystem)
                else:
                    ok, base, bz, faces, problem = base_area_and_z_from_lowest_faces(
                        world, tol, math.radians(30), math.radians(1))
                    section, loops = 0.0, 0
                if not ok or problem or not math.isfinite(base) or not math.isfinite(section):
                    issue(origin, problem or 'Area calculation failed.', world)
                    for curve in result.curves[start:]:
                        curve.Dispose()
                    del result.curves[start:]
                else:
                    result.base += base
                    result.section += section
                    result.solids += 1
                    result.faces += faces
                    result.loops += loops
        except Exception as error:
            issue(origin, 'Cannot measure geometry: ' + str(error), world)
        finally:
            world.Dispose()
        return 1

    try:
        for object_id in ids:
            visit(doc.Objects.FindId(object_id), Rhino.Geometry.Transform.Identity, object_id, set())
        return result
    except Exception:
        result.dispose()
        raise


def area_value(doc, value, unit_index=0, decimals=2, include_unit=True):
    number = format_display_number(area_in_unit(value, unit_index, doc.ModelUnitSystem), decimals)
    return number + ' ' + AREA_UNITS[unit_index][1] if include_unit else number
