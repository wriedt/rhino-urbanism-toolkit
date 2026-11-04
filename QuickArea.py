#! python 3
# -*- coding: utf-8 -*-
# Author: Rune Wriedt (runewriedt@gmail.com)
# Version: 1.1
# Date: 2026-10-23
# Description:
# Computes total horizontal section area of closed Breps / closed Breps inside blocks.
# For each solid, the script:
#   1. Finds the lowest horizontal planar face(s)
#   2. Sums the area of those base face(s)
#   3. Uses the base face centroid Z as the local base height
#   4. Creates a World XY section plane above base Z (session default 1.5 metres)
#   5. Intersects the closed Brep with that plane
#   6. Calculates the true filled plan area from the resulting closed section curves
#      Nested curves are treated with an even/odd rule:
#        - outer loops add area
#        - loops inside outer loops subtract area
#        - loops inside holes add area again
#
# This is intended for Danish GFA-style checks where a sloping roof/floor volume
# is counted by its horizontal area at 1.5 m above the local base height.

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from System.Drawing import Color
import math
import os
import sys

import Eto.Forms as forms
import Eto.Drawing as drawing

# ScriptEditor and published commands may not add the script folder to sys.path.
SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
import urbanism_ui as ui

WARN_LAYER_NAME = "QuickArea_Warnings"
WARN_LAYER_COLOR = Color.FromArgb(230, 50, 50)

# The default offset is 1.5 metres; the session value can be changed in the result.
# It is converted to the current Rhino model unit system in offset_1p5m_in_model_units().
SECTION_HEIGHT_METRES = 1.5
HEIGHT_STICKY_KEY = 'RhinoUrbanism.QuickArea.SectionHeightMetres'
AREA_UNITS = (('m²', 'm²', 1.0), ('km²', 'km²', 1000000.0),
              ('Hectares (ha)', 'ha', 10000.0))


def section_height_metres():
    value = sc.sticky.get(HEIGHT_STICKY_KEY, SECTION_HEIGHT_METRES)
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else SECTION_HEIGHT_METRES


def area_in_unit(value, unit_index, model_units=None):
    model_units = sc.doc.ModelUnitSystem if model_units is None else model_units
    to_metres = Rhino.RhinoMath.UnitScale(model_units, Rhino.UnitSystem.Meters)
    return value * to_metres * to_metres / AREA_UNITS[unit_index][2]


def prompt_section_height(current):
    getter = Rhino.Input.Custom.GetNumber()
    try:
        getter.SetCommandPrompt('Section height above each local base (metres)')
        getter.SetDefaultNumber(current)
        getter.SetLowerLimit(0.0, False)
        getter.AcceptNothing(True)
        result = getter.Get()
        if result == Rhino.Input.GetResult.Nothing:
            return current
        if result == Rhino.Input.GetResult.Number:
            value = getter.Number()
            if math.isfinite(value) and value > 0:
                return value
        return None
    finally:
        getter.Dispose()


def ensure_layer(name, color):
    layers = sc.doc.Layers
    idx = layers.Find(name, True)
    if idx < 0:
        la = Rhino.DocObjects.Layer()
        la.Name = name
        la.Color = color
        idx = layers.Add(la)
    return idx


class WarningTagger(object):
    """Creates warning layer lazily; can be disabled to avoid creating dots/layers."""
    def __init__(self, enabled=True, layer_name=WARN_LAYER_NAME, layer_color=WARN_LAYER_COLOR):
        self.enabled = enabled
        self.layer_name = layer_name
        self.layer_color = layer_color
        self._layer_ready = False

    def _ensure(self):
        if not self.enabled:
            return
        if not self._layer_ready:
            ensure_layer(self.layer_name, self.layer_color)
            self._layer_ready = True

    def add_dot(self, text, point):
        if not self.enabled:
            return None
        self._ensure()
        dot_id = rs.AddTextDot(text, point)
        if dot_id:
            rs.ObjectLayer(dot_id, self.layer_name)
        return dot_id

    @property
    def layer_created(self):
        return self._layer_ready and self.enabled


def offset_1p5m_in_model_units():
    """
    Returns the current session height, default 1.5 m, in document units.

    Examples:
      - model in metres      -> 1.5
      - model in centimetres -> 150.0
      - model in millimetres -> 1500.0

    This keeps the script useful even if the file is not using metres as its unit system.
    """
    try:
        scale = Rhino.RhinoMath.UnitScale(
            Rhino.UnitSystem.Meters,
            sc.doc.ModelUnitSystem
        )
        return section_height_metres() * scale
    except:
        # Conservative fallback: if the conversion fails, use the raw value.
        # In a metres model this is correct.
        return section_height_metres()


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
        if not ok or area <= tol * tol or not centroid.IsValid:
            continue
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


def section_area_of_solid_at_1p5m(brep, tol, loose_ang_rad, strict_ang_rad,
                                 section_curve_output=None):
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

    section_z = base_z + offset_1p5m_in_model_units()
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
        return False, 0.0, base_area, base_z, section_z, 0, base_face_count, 'No section curves at {:g} m above base'.format(section_height_metres())

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

    # Open curves indicate possible tolerance or modelling issues.
    # We still return the area from the closed loops, but report the warning upstream.
    if open_curves:
        return True, area, base_area, base_z, section_z, loop_count, base_face_count, "Warning: some section curves were open and ignored"

    return True, area, base_area, base_z, section_z, loop_count, base_face_count, None


def format_area_with_units(area_value):
    try:
        unit_name = rs.UnitSystemName(model_units=True, singular=False)
        return "{:.6g} {}²".format(area_value, unit_name) if unit_name else "{:.6g}".format(area_value)
    except:
        return "{:.6g}".format(area_value)


def format_percent(value):
    """Formats a percentage with enough precision to be useful in a dialog."""
    return "{:.2f}%".format(value)


def lowest_bbox_point(obj_id):
    bb = rs.BoundingBox(obj_id)
    if not bb:
        return None
    return sorted(bb, key=lambda p: p.Z)[0]


# Ensures 1893.5 -> 1894 instead of Python's banker's rounding.
def round_half_up(x):
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(abs(x) + 0.5))


def _xform_multiply(a, b):
    # Returns transform equivalent to applying b, then a (a*b).
    return Rhino.Geometry.Transform.Multiply(a, b)


def extract_solids_from_instance(instance_obj, parent_xform, out_list, origin_id, visited_idef_ids):
    """
    Recursively extracts Breps from a block instance into out_list.

    Each entry appended:
      (origin_id, kind, brep_world)

    kind == "Solid" for closed Breps
    kind == "Open"  for non-solid Breps
    """
    if instance_obj is None:
        return

    idef = instance_obj.InstanceDefinition
    if idef is None:
        return

    # Avoid infinite recursion if a block somehow references itself.
    if idef.Id in visited_idef_ids:
        return
    visited_idef_ids.add(idef.Id)

    def_objects = idef.GetObjects()
    if not def_objects:
        visited_idef_ids.remove(idef.Id)
        return

    for dobj in def_objects:
        if dobj is None:
            continue
        geo = dobj.Geometry
        if geo is None:
            continue

        if dobj.ObjectType == Rhino.DocObjects.ObjectType.InstanceReference:
            child_inst = dobj
            child_xf = child_inst.InstanceXform
            total = _xform_multiply(parent_xform, child_xf)
            extract_solids_from_instance(child_inst, total, out_list, origin_id, visited_idef_ids)
            continue

        brep = Rhino.Geometry.Brep.TryConvertBrep(geo)
        if brep is None:
            continue

        brep_dup = brep.DuplicateBrep()
        if brep_dup is None:
            continue

        if not brep_dup.Transform(parent_xform):
            continue

        if brep_dup.IsSolid:
            out_list.append((origin_id, "Solid", brep_dup))
        else:
            out_list.append((origin_id, "Open", brep_dup))

    visited_idef_ids.remove(idef.Id)


SELECTION_TYPES = (Rhino.DocObjects.ObjectType.Surface |
                   Rhino.DocObjects.ObjectType.Brep |
                   Rhino.DocObjects.ObjectType.Extrusion |
                   Rhino.DocObjects.ObjectType.InstanceReference)


def select_objects(doc):
    """No settings means no opening dialog: preselection or the native picker."""
    preselected = [obj.Id for obj in doc.Objects.GetSelectedObjects(False, False)
                   if obj.ObjectType & SELECTION_TYPES]
    if preselected:
        return preselected
    getter = Rhino.Input.Custom.GetObject()
    try:
        getter.SetCommandPrompt('Select volumes or blocks for QuickArea')
        getter.GeometryFilter = SELECTION_TYPES
        getter.SubObjectSelect = False
        getter.EnablePreSelect(True, True)
        getter.GetMultiple(1, 0)
        if getter.CommandResult() != Rhino.Commands.Result.Success:
            return []
        return [getter.Object(i).ObjectId for i in range(getter.ObjectCount)]
    finally:
        getter.Dispose()


def create_invalid_dialog():
    dlg = ui.AquaDialog('QuickArea | Selection', 'Measurement / QuickArea',
                        'Some items will be skipped', '')
    dlg.choice = 'cancel'
    dlg.tag_checkbox = ui.checkbox('Tag skipped items in the model')
    dlg.tag_checkbox.Checked = False
    notice = ui.content_layout(14)
    notice.AddRow(ui.label('Open surfaces and blocks without closed volumes\n'
                          'cannot contribute to the section area.', muted=True))
    notice.AddRow(dlg.tag_checkbox)
    dlg.body.AddRow(ui.InfoPanel(notice))
    dlg.cancel_button = ui.button('Cancel')
    dlg.continue_button = ui.button('Continue', True)

    def proceed(sender, event):
        dlg.choice = 'continue_tag' if dlg.tag_checkbox.Checked else 'continue_no_tag'
        dlg.Close(True)

    dlg.continue_button.Click += proceed
    dlg.cancel_button.Click += lambda s, e: dlg.Close(False)
    dlg.DefaultButton = dlg.continue_button
    dlg.AbortButton = dlg.cancel_button
    dlg.finish(ui.action_row(dlg.cancel_button, dlg.continue_button),
               'Only closed volumes will be measured.')
    return dlg


def ask_invalid_dialog():
    dlg = create_invalid_dialog()
    dlg.show_for_doc(sc.doc)
    return dlg.choice


def format_display_number(value, decimals):
    text = '{:.{}f}'.format(value, decimals)
    # Tolerance-scale calculation noise should display as 0.00, not -0.00.
    return text[1:] if text.startswith('-') and float(text) == 0 else text


def create_result_dialog(pretty_section_area, pretty_base_area, rounded_section_value,
                         rounded_base_value, reduction_percent, solid_count,
                         loop_count, base_face_count, section_area=None, base_area=None,
                         section_curves=None, coverage=None):
    # Main passes full-precision numbers; formatted arguments remain compatible
    # with callers that build a result dialog directly.
    section_area = float(pretty_section_area.split()[0]) if section_area is None else section_area
    base_area = float(pretty_base_area.split()[0]) if base_area is None else base_area
    dlg = ui.AquaDialog('QuickArea | Result', 'Measurement / QuickArea',
                        'Area summary', '')
    dlg.recalculate = False
    dlg.height_button = ui.button('Change height')
    height_row = ui.content_layout(0)
    height_row.AddRow(ui.label('Measured at {:g} m above each local base.'.format(section_height_metres()),
                               ui.CAPTION_SIZE, True), None, dlg.height_button)
    dlg.body.AddRow(height_row)
    coverage = coverage or {}
    dlg.coverage_warning = None
    if coverage.get('warning'):
        warning = ui.content_layout(6)
        dlg.coverage_warning = ui.label(coverage['warning'])
        dlg.coverage_warning.TextColor = ui.colour('#a34535', '#f0ab99')
        warning.AddRow(dlg.coverage_warning)
        if coverage.get('failed_breps'):
            warning.AddRow(ui.label('Coral outlines mark uncounted solids.', ui.CAPTION_SIZE, True))
        dlg.body.AddRow(ui.InfoPanel(warning))
    section = ui.content_layout(8)
    section.AddRow(ui.label('Section area', muted=True))
    dlg.section_label = ui.label('', ui.VALUE_SIZE)
    section.AddRow(dlg.section_label)
    dlg.body.AddRow(ui.InfoPanel(section))
    precision = ui.content_layout(6)
    dlg.unit_index = 0
    dlg.unit_buttons = [ui.button(unit[1], index == 0) for index, unit in enumerate(AREA_UNITS)]
    for control, unit in zip(dlg.unit_buttons, AREA_UNITS):
        control.Width = 66
        control.ToolTip = unit[0]
    unit_row = ui.content_layout(0)
    unit_row.AddRow(ui.label('Area unit', muted=True), None, *dlg.unit_buttons)
    precision.AddRow(unit_row)
    precision_header = ui.content_layout(0)
    dlg.decimal_label = ui.label('2', muted=True)
    precision_header.AddRow(ui.label('Decimal places', muted=True), None, dlg.decimal_label)
    precision.AddRow(precision_header)
    dlg.decimal_slider = forms.Slider()
    dlg.decimal_slider.MinValue = 0
    dlg.decimal_slider.MaxValue = 6
    dlg.decimal_slider.TickFrequency = 1
    dlg.decimal_slider.SnapToTick = True
    dlg.decimal_slider.Value = 2
    precision.AddRow(dlg.decimal_slider)
    dlg.body.AddRow(precision)
    metrics = ui.content_layout()
    metrics.Spacing = drawing.Size(24, 10)
    dlg.base_label = ui.label('')
    metrics.AddRow(ui.label('Base plane area', muted=True), None, dlg.base_label)
    dlg.reduction_label = ui.label('')
    metrics.AddRow(ui.label('Reduction from base', muted=True), None, dlg.reduction_label)
    dlg.body.AddRow(ui.InfoPanel(metrics))
    dlg.body.AddRow(ui.label('{} {} counted · {} {} · {} {}'.format(
        solid_count, 'solid' if solid_count == 1 else 'solids',
        base_face_count, 'base face' if base_face_count == 1 else 'base faces',
        loop_count, 'section loop' if loop_count == 1 else 'section loops'), ui.CAPTION_SIZE, True))
    dlg.copy_button = ui.button('Copy section area', True)
    dlg.copy_base_button = ui.button('Copy base plane area')
    dlg.done_button = ui.button('Close')

    def update_precision(sender=None, event=None):
        decimals = dlg.decimal_slider.Value
        unit_index = dlg.unit_index
        unit = AREA_UNITS[unit_index][1]
        dlg.decimal_label.Text = str(decimals)
        dlg.copy_value = format_display_number(area_in_unit(section_area, unit_index), decimals)
        dlg.base_copy_value = format_display_number(area_in_unit(base_area, unit_index), decimals)
        dlg.section_label.Text = dlg.copy_value + ' ' + unit
        dlg.base_label.Text = dlg.base_copy_value + ' ' + unit
        dlg.reduction_label.Text = format_display_number(reduction_percent, decimals) + '%'
        dlg.set_status('')

    def copy(value):
        try:
            ui.copy_text_to_clipboard(value)
            dlg.Close(True)
        except Exception:
            dlg.set_status('Clipboard unavailable. Try copying again.')

    def change_height(sender, event):
        changed = {'value': None}
        def ask(s, e):
            changed['value'] = prompt_section_height(section_height_metres())
        Rhino.UI.EtoExtensions.PushPickButton(dlg, ask)
        if changed['value'] is not None:
            sc.sticky[HEIGHT_STICKY_KEY] = changed['value']
            dlg.recalculate = True
            dlg.Close(True)

    def choose_unit(index):
        dlg.unit_index = index
        for button_index, control in enumerate(dlg.unit_buttons):
            ui.set_button_selected(control, button_index == index)
        update_precision()

    dlg.height_button.Click += change_height
    dlg.copy_button.Click += lambda s, e: copy(dlg.copy_value)
    dlg.copy_base_button.Click += lambda s, e: copy(dlg.base_copy_value)
    for index, control in enumerate(dlg.unit_buttons):
        control.Click += lambda s, e, index=index: choose_unit(index)
    dlg.decimal_slider.ValueChanged += update_precision
    dlg.done_button.Click += lambda s, e: dlg.Close(True)
    dlg.DefaultButton = dlg.done_button
    dlg.AbortButton = dlg.done_button
    dlg.finish(ui.action_row(dlg.done_button, dlg.copy_base_button, dlg.copy_button))
    update_precision()
    return dlg


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
            event.Display.DrawBrepWires(brep, self.failure_color, 3)
        self.draw_count += 1


def show_result_dialog(*args):
    curves = args[10] if len(args) > 10 else []
    coverage = args[11] if len(args) > 11 else {}
    failed_breps = coverage.get('failed_breps', [])
    preview = SectionPreview(sc.doc, curves)
    try:
        preview.set_failures(failed_breps)
        preview.Enabled = True
        sc.doc.Views.Redraw()
        dialog = create_result_dialog(*args)
        dialog.show_for_doc(sc.doc, picking=True)
        return dialog.recalculate
    finally:
        preview.Enabled = False
        sc.doc.Views.Redraw()
        for curve in curves:
            curve.Dispose()
        for brep in failed_breps:
            brep.Dispose()


def create_issues_dialog(doc, problems, warnings, tagged=False):
    """Keep object identities attached to actionable issue entries."""
    import textwrap
    dlg = ui.AquaDialog('QuickArea | Section issues', 'Measurement / QuickArea',
                        'Review section issues', 'Click an object to select it in Rhino.')
    entries = ui.content_layout(14)
    dlg.issue_buttons = []
    dlg.issue_object_ids = []

    def select_issue(object_id, name):
        obj = doc.Objects.FindId(object_id)
        if obj is None or obj.IsDeleted:
            dlg.set_status('This object no longer exists in the document.')
            return
        if obj.IsHidden or obj.IsLocked:
            dlg.set_status('This object is hidden or locked and cannot be selected.')
            return
        previous = [o.Id for o in doc.Objects.GetSelectedObjects(False, False)]
        doc.Objects.UnselectAll()
        if doc.Objects.Select(object_id):
            dlg.set_status('Selected ' + name)
        else:
            for previous_id in previous:
                doc.Objects.Select(previous_id)
            dlg.set_status('This object cannot currently be selected.')
        doc.Views.Redraw()

    for heading, items in [('Not counted', problems), ('Counted with warnings', warnings)]:
        if not items:
            continue
        entries.AddRow(ui.label(heading, muted=True))
        grouped = {}
        for object_id, reason in items:
            grouped.setdefault(object_id, []).append(reason)
        for object_id, reasons in grouped.items():
            obj = doc.Objects.FindId(object_id)
            name = obj.Attributes.Name if obj else ''
            if not name and isinstance(obj, Rhino.DocObjects.InstanceObject):
                name = obj.InstanceDefinition.Name
            name = ('{} · {}'.format(name, str(object_id)[:8]) if name else
                    'Object ' + str(object_id)[:8])
            control = ui.button(name)
            control.ToolTip = 'Select this object in Rhino'
            control.Click += lambda s, e, object_id=object_id, name=name: select_issue(object_id, name)
            dlg.issue_buttons.append(control)
            dlg.issue_object_ids.append(object_id)
            entry = ui.content_layout(6)
            entry.AddRow(control, None)
            reason_text = '\n'.join(textwrap.fill('• ' + reason, 58,
                                     subsequent_indent='  ') for reason in reasons)
            entry.AddRow(ui.label(reason_text))
            entries.AddRow(entry)
    scroll = forms.Scrollable()
    scroll.Size = drawing.Size(430, min(280, 40 + 90 * len(dlg.issue_buttons)))
    scroll.ExpandContentWidth = True
    scroll.ExpandContentHeight = False
    scroll.Border = forms.BorderType.NONE
    scroll.BackgroundColor = ui.FIELD
    ui.theme_scrollbars(scroll)
    scroll.Content = entries
    dlg.body.AddRow(ui.InfoPanel(scroll))
    if tagged:
        dlg.body.AddRow(ui.label('Problem items were tagged on ' + WARN_LAYER_NAME + '.',
                                 ui.CAPTION_SIZE, True))
    done = ui.button('Close', True)
    done.Click += lambda s, e: dlg.Close(True)
    dlg.DefaultButton = done
    dlg.AbortButton = done
    dlg.finish(ui.action_row(done))
    return dlg


def measure_selection(ids):
    doc_tol = sc.doc.ModelAbsoluteTolerance

    # A loose filter is used to find candidate base faces.
    # A strict filter is then used to reject faces that are not truly World XY horizontal.
    loose_filter_deg = 30.0
    loose_filter_rad = math.radians(loose_filter_deg)
    strict_deg = 1.0
    strict_rad = math.radians(strict_deg)

    invalid_ids = []
    open_item_ids = []
    solids = []  # (origin_id, brep_world)

    # First pass: gather closed Breps and detect invalid/open geometry.
    for oid in ids:
        rh_obj = sc.doc.Objects.FindId(oid)
        if rh_obj is None:
            invalid_ids.append(oid)
            continue

        if rh_obj.ObjectType == Rhino.DocObjects.ObjectType.InstanceReference:
            inst = rh_obj
            xform = inst.InstanceXform  # block instance transform to world coordinates
            extracted = []
            extract_solids_from_instance(inst, xform, extracted, origin_id=oid, visited_idef_ids=set())

            if not extracted:
                invalid_ids.append(oid)
                continue

            for origin_id, kind, brep_world in extracted:
                if kind == "Solid":
                    solids.append((origin_id, brep_world))
                else:
                    open_item_ids.append(origin_id)
            continue

        brep = rs.coercebrep(oid)
        if brep is None:
            invalid_ids.append(oid)
            continue
        if brep.IsSolid:
            solids.append((oid, brep))
        else:
            open_item_ids.append(oid)

    any_invalid_selection = bool(invalid_ids or open_item_ids)

    tag_invalid = False
    if any_invalid_selection:
        choice = ask_invalid_dialog()
        if choice == "cancel":
            return
        elif choice == "continue_tag":
            tag_invalid = True
        elif choice == "continue_no_tag":
            tag_invalid = False

    tagger = WarningTagger(enabled=tag_invalid)

    if not solids:
        if tag_invalid:
            rs.UnselectAllObjects()
            rs.SelectObjects(list(set(invalid_ids + open_item_ids)))
            for oid in invalid_ids:
                pt = lowest_bbox_point(oid)
                if pt:
                    tagger.add_dot("INVALID / NO SOLIDS", pt)
            for oid in open_item_ids:
                pt = lowest_bbox_point(oid)
                if pt:
                    tagger.add_dot("OPEN BREP", pt)

        ui.message_dialog(sc.doc, 'QuickArea', 'No closed volumes found.',
                          'No closed Breps to process (including inside selected blocks).')
        return

    if any_invalid_selection and tag_invalid:
        rs.UnselectAllObjects()
        rs.SelectObjects(list(set(invalid_ids + open_item_ids)))

        for oid in invalid_ids:
            pt = lowest_bbox_point(oid)
            if pt:
                tagger.add_dot("INVALID / NO SOLIDS", pt)

        for oid in open_item_ids:
            pt = lowest_bbox_point(oid)
            if pt:
                tagger.add_dot("OPEN BREP", pt)

    total_section_area = 0.0
    total_base_area = 0.0
    total_loops = 0
    total_base_faces = 0
    preview_curves = []
    problems = []  # (origin_id, reason)
    warnings = []  # (origin_id, warning_text)
    counted_origins = set()
    counted_solids = 0
    failed_breps = []

    for origin_id, brep in solids:
        ok, section_area, base_area, base_z, section_z, loop_count, base_face_count, problem = section_area_of_solid_at_1p5m(
            brep,
            doc_tol,
            loose_filter_rad,
            strict_rad,
            section_curve_output=preview_curves
        )

        # Good result, but with a non-fatal warning such as ignored open curves.
        if ok:
            counted_solids += 1
            counted_origins.add(origin_id)
            total_section_area += section_area
            total_base_area += base_area
            total_loops += loop_count
            total_base_faces += base_face_count
            if problem:
                warnings.append((origin_id, problem))
            continue

        # Failed result.
        problems.append((origin_id, problem))
        failed_breps.append(brep.DuplicateBrep())

        amp_brep = Rhino.Geometry.AreaMassProperties.Compute(brep)
        cen = amp_brep.Centroid if amp_brep else brep.GetBoundingBox(True).Center
        tagger.add_dot(problem, cen)

    if problems or warnings:
        if tag_invalid and problems:
            rs.UnselectAllObjects()
            rs.SelectObjects(list({p[0] for p in problems}))

        create_issues_dialog(sc.doc, problems, warnings,
                             tag_invalid and tagger.layer_created).show_for_doc(sc.doc, picking=True)

    pretty_section = format_area_with_units(total_section_area)
    pretty_base = format_area_with_units(total_base_area)

    rounded_section_value = round_half_up(total_section_area)
    rounded_base_value = round_half_up(total_base_area)

    if total_base_area > doc_tol * doc_tol:
        reduction_percent = ((total_base_area - total_section_area) / total_base_area) * 100.0
    else:
        reduction_percent = 0.0

    print("QuickArea — Total base plane area: {}".format(pretty_base))
    print('QuickArea — Total {:g} m section area: {}'.format(section_height_metres(), pretty_section))
    print('QuickArea — Reduction from base: {}'.format(format_percent(reduction_percent)))
    print("QuickArea — Display and clipboard precision can be adjusted in the result.")

    excluded = len(set(ids) - counted_origins)
    partial = len((set(origin for origin, reason in problems) | set(open_item_ids)) & counted_origins)
    notes = []
    if excluded:
        notes.append('{} of {} selected {} excluded from totals.'.format(
            excluded, len(set(ids)), 'object' if len(set(ids)) == 1 else 'objects'))
    if partial:
        notes.append('{} selected {} only partly counted.'.format(
            partial, 'block is' if partial == 1 else 'blocks are'))
    if problems and all(reason.startswith('No section curves at ') for origin, reason in problems):
        notes.append('No section at {:g} m for {} {}.'.format(
            section_height_metres(), len(problems), 'solid' if len(problems) == 1 else 'solids'))
    coverage = {'warning': '\n'.join(notes), 'failed_breps': failed_breps,
                'excluded_count': excluded, 'partial_count': partial}

    return show_result_dialog(
        pretty_section,
        pretty_base,
        rounded_section_value,
        rounded_base_value,
        reduction_percent,
        counted_solids,
        total_loops,
        total_base_faces,
        total_section_area,
        total_base_area,
        preview_curves,
        coverage
    )


def main():
    ids = select_objects(sc.doc)
    while ids and measure_selection(ids):
        pass


if __name__ == "__main__":
    main()
