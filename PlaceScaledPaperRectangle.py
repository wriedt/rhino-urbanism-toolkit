#! python 3
# -*- coding: utf-8 -*-
# Author: Rune Wriedt (runewriedt@gmail.com)
# Version: 1.0
# Date: 2026-09-25
# Description:
# Places an A0-A4 paper boundary at a chosen drawing scale.
# The rectangle is previewed dynamically on the active construction plane.
# Orientation and insertion point can be changed from the command line while
# the preview is active.

import re

import Rhino
import scriptcontext as sc
from System.Drawing import Color


PAPER_SIZES_MM = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
}

PAPER_SIZE_ORDER = ("A0", "A1", "A2", "A3", "A4")
SCALE_PRESETS = (100, 200, 500, 1000, 2000, 5000, 10000)

STICKY_PREFIX = "PlaceScaledPaperRectangle."
PREVIEW_COLOR = Color.FromArgb(40, 210, 230)
PREVIEW_THICKNESS = 2
EMPTY_GUID = "00000000-0000-0000-0000-000000000000"


def get_sticky(key, default):
    """Return a saved session value, or a safe default."""
    return sc.sticky.get(STICKY_PREFIX + key, default)


def set_sticky(key, value):
    """Remember a setting for the rest of the current Rhino session."""
    sc.sticky[STICKY_PREFIX + key] = value


def get_paper_size():
    """Ask for A0-A4 on Rhino's command line."""
    default_size = get_sticky("PaperSize", "A3")
    if default_size not in PAPER_SIZE_ORDER:
        default_size = "A3"

    getter = Rhino.Input.Custom.GetOption()
    getter.SetCommandPrompt("Paper size")
    getter.SetCommandPromptDefault(default_size)
    getter.AcceptNothing(True)

    option_to_size = {}
    for size_name in PAPER_SIZE_ORDER:
        option_index = getter.AddOption(size_name)
        option_to_size[option_index] = size_name

    result = getter.Get()

    if result == Rhino.Input.GetResult.Nothing:
        selected_size = default_size
    elif result == Rhino.Input.GetResult.Option:
        selected_size = option_to_size.get(getter.OptionIndex())
    else:
        return None

    if selected_size:
        set_sticky("PaperSize", selected_size)
    return selected_size


def parse_scale_denominator(text):
    """
    Parse either a denominator ("75") or ratio ("1:75" / "1/75").

    Returns a positive float, or None when the value is not a valid 1:N scale.
    """
    value = text.strip().replace(" ", "")
    match = re.match(r"^(?:(1)\s*[:/]\s*)?(\d+(?:\.\d+)?)$", value)
    if not match:
        return None

    try:
        denominator = float(match.group(2))
    except ValueError:
        return None

    if denominator <= 0.0:
        return None
    return denominator


def format_scale(scale):
    """Format a scale denominator without unnecessary decimal places."""
    if float(scale).is_integer():
        return str(int(scale))
    return "{0:g}".format(scale)


def get_scale():
    """Ask for a custom scale or one of the requested presets."""
    default_scale = float(get_sticky("Scale", 1000.0))

    while True:
        getter = Rhino.Input.Custom.GetString()
        getter.SetCommandPrompt(
            "Scale denominator (type 75 or 1:75, or choose a preset)"
        )
        getter.SetDefaultString("1:{0}".format(format_scale(default_scale)))

        option_to_scale = {}
        for preset in SCALE_PRESETS:
            option_index = getter.AddOption("Scale{0}".format(preset))
            option_to_scale[option_index] = float(preset)

        result = getter.Get()

        if result == Rhino.Input.GetResult.Cancel:
            return None

        if result == Rhino.Input.GetResult.Option:
            scale = option_to_scale.get(getter.OptionIndex())
        elif result == Rhino.Input.GetResult.String:
            scale = parse_scale_denominator(getter.StringResult())
        elif result == Rhino.Input.GetResult.Nothing:
            scale = default_scale
        else:
            return None

        if scale is not None:
            set_sticky("Scale", scale)
            return scale

        Rhino.RhinoApp.WriteLine(
            "Invalid scale. Enter a positive denominator such as 75 or 1:75."
        )


def millimetres_to_model_units(value_mm):
    """Convert a paper measurement in millimetres to document model units."""
    factor = Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Millimeters,
        sc.doc.ModelUnitSystem,
    )
    return value_mm * factor


def scaled_dimensions(paper_size, scale, landscape):
    """Return the model-space width and height for the selected paper setup."""
    long_side_mm, short_side_mm = PAPER_SIZES_MM[paper_size]

    if landscape:
        width_mm = long_side_mm
        height_mm = short_side_mm
    else:
        width_mm = short_side_mm
        height_mm = long_side_mm

    width = millimetres_to_model_units(width_mm * scale)
    height = millimetres_to_model_units(height_mm * scale)
    return width, height


def rectangle_points(insertion_point, cplane, width, height, centered):
    """Build five points for a closed rectangle parallel to the active CPlane."""
    x_axis = Rhino.Geometry.Vector3d(cplane.XAxis)
    y_axis = Rhino.Geometry.Vector3d(cplane.YAxis)
    x_axis.Unitize()
    y_axis.Unitize()

    corner = Rhino.Geometry.Point3d(insertion_point)
    if centered:
        corner -= x_axis * (width * 0.5)
        corner -= y_axis * (height * 0.5)

    point_0 = corner
    point_1 = corner + x_axis * width
    point_2 = point_1 + y_axis * height
    point_3 = corner + y_axis * height

    return [point_0, point_1, point_2, point_3, point_0]


def place_rectangle(paper_size, scale):
    """Preview the paper boundary and add it to the document when clicked."""
    active_view = sc.doc.Views.ActiveView
    if active_view is None:
        Rhino.RhinoApp.WriteLine("No active viewport is available.")
        return None

    cplane = active_view.ActiveViewport.ConstructionPlane()
    landscape = bool(get_sticky("Landscape", True))
    centered = bool(get_sticky("Centered", False))

    while True:
        width, height = scaled_dimensions(paper_size, scale, landscape)
        orientation_name = "Landscape" if landscape else "Portrait"
        anchor_name = "Center" if centered else "LowerLeft"

        getter = Rhino.Input.Custom.GetPoint()
        getter.SetCommandPrompt(
            "Click to place {0} at 1:{1} ({2}, {3})".format(
                paper_size,
                format_scale(scale),
                orientation_name,
                anchor_name,
            )
        )

        orientation_toggle = Rhino.Input.Custom.OptionToggle(
            landscape,
            "Portrait",
            "Landscape",
        )
        anchor_toggle = Rhino.Input.Custom.OptionToggle(
            centered,
            "LowerLeft",
            "Center",
        )
        getter.AddOptionToggle("Orientation", orientation_toggle)
        getter.AddOptionToggle("Anchor", anchor_toggle)

        def draw_preview(sender, event):
            points = rectangle_points(
                event.CurrentPoint,
                cplane,
                width,
                height,
                centered,
            )
            preview_curve = Rhino.Geometry.PolylineCurve(points)
            event.Display.DrawCurve(
                preview_curve,
                PREVIEW_COLOR,
                PREVIEW_THICKNESS,
            )

        getter.DynamicDraw += draw_preview
        result = getter.Get()

        if result == Rhino.Input.GetResult.Option:
            landscape = orientation_toggle.CurrentValue
            centered = anchor_toggle.CurrentValue
            set_sticky("Landscape", landscape)
            set_sticky("Centered", centered)
            continue

        if result != Rhino.Input.GetResult.Point:
            return None

        insertion_point = getter.Point()
        points = rectangle_points(
            insertion_point,
            cplane,
            width,
            height,
            centered,
        )
        rectangle = Rhino.Geometry.PolylineCurve(points)

        attributes = Rhino.DocObjects.ObjectAttributes()
        attributes.Name = "{0}_1-{1}_{2}".format(
            paper_size,
            format_scale(scale),
            orientation_name,
        )

        undo_record = sc.doc.BeginUndoRecord("Place scaled paper rectangle")
        try:
            object_id = sc.doc.Objects.AddCurve(rectangle, attributes)
        finally:
            sc.doc.EndUndoRecord(undo_record)

        if str(object_id) == EMPTY_GUID:
            Rhino.RhinoApp.WriteLine("The paper rectangle could not be added.")
            return None

        set_sticky("Landscape", landscape)
        set_sticky("Centered", centered)
        sc.doc.Views.Redraw()
        return object_id


def main():
    if sc.doc is None:
        return

    paper_size = get_paper_size()
    if paper_size is None:
        return

    scale = get_scale()
    if scale is None:
        return

    object_id = place_rectangle(paper_size, scale)
    if object_id is None:
        return

    width, height = scaled_dimensions(
        paper_size,
        scale,
        bool(get_sticky("Landscape", True)),
    )
    unit_name = sc.doc.GetUnitSystemName(
        True,
        False,
        False,
        True,
    )
    Rhino.RhinoApp.WriteLine(
        "Placed {0} at 1:{1}: {2:g} x {3:g} {4}.".format(
            paper_size,
            format_scale(scale),
            width,
            height,
            unit_name,
        )
    )


if __name__ == "__main__":
    main()
