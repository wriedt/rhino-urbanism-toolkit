import math

import Rhino
import scriptcontext as sc


# ----------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------

# Degree of all rebuilt curves.
DEGREE = 3

# Do not preserve end tangencies during Rebuild.
PRESERVE_TANGENTS = False

# Maximum number of control points we will allow.
MAX_POINT_COUNT = 1000


# ----------------------------------------------------------------------
# STORED SETTINGS
# ----------------------------------------------------------------------

# scriptcontext.sticky is a Python dictionary which survives between
# executions of Python scripts for as long as this Rhino session remains
# open.
#
# The key should be reasonably unique. Otherwise another script could
# accidentally use the same key and overwrite our value.
SPACING_STICKY_KEY = "RebuildBySpacing.LastSpacing"


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------

def ceil_with_tolerance(value):
    """
    Round a number upwards while protecting against tiny floating-point
    inaccuracies.

    For example, something that mathematically ought to be:

        20 / 4 = 5

    could theoretically end up represented internally as:

        5.000000000000001

    math.ceil() would incorrectly turn that into 6.

    Therefore, if the value is extremely close to an integer, we treat
    it as that integer first.
    """

    nearest_integer = round(value)

    tolerance = 1e-10 * max(1.0, abs(value))

    if abs(value - nearest_integer) <= tolerance:
        return int(nearest_integer)

    return int(math.ceil(value))


def calculate_point_count(curve_length, spacing, is_closed):
    """
    Calculate the requested number of control points.

    OPEN CURVE
    ----------

    Example:

        curve length = 20
        spacing      = 4

        20 / 4 = 5 intervals

    Since an open curve has separate points at both ends:

        5 intervals + 1 = 6 control points


    CLOSED CURVE
    ------------

    The start and end coincide, so there is no additional endpoint:

        20 / 4 = 5 control points
    """

    ratio = curve_length / spacing

    # Always round upwards so that the entered spacing behaves as the
    # maximum desired nominal spacing.
    interval_count = ceil_with_tolerance(ratio)

    if is_closed:
        point_count = interval_count

        # Minimum for our degree-3 closed rebuild.
        minimum_point_count = DEGREE

    else:
        point_count = interval_count + 1

        # An open degree-3 curve needs at least 4 points.
        minimum_point_count = DEGREE + 1

    return max(point_count, minimum_point_count)


def get_input_curves():
    """
    Get the curves that should be rebuilt.

    There are two possible routes:

    1. If one or more CURVES are already selected in Rhino:
       use those immediately.

    2. Otherwise:
       start Rhino's normal interactive GetObject selection.

    The function always returns a list of ObjRefs.

    It returns None if the interactive selection is cancelled.
    """

    # ------------------------------------------------------------------
    # First check Rhino's CURRENT selection
    # ------------------------------------------------------------------

    selected_objects = sc.doc.Objects.GetSelectedObjects(
        False,  # includeLights
        False   # includeGrips
    )

    selected_curve_objrefs = []

    for rhino_object in selected_objects:

        # We only care about standalone curve objects.
        #
        # If, for example, a mesh and three curves are selected, the
        # mesh is simply ignored and the three curves are used.
        if isinstance(rhino_object, Rhino.DocObjects.CurveObject):

            # Convert the RhinoObject into an ObjRef because the rest of
            # our script already works with ObjRefs.
            #
            # Using the constructor that includes sc.doc explicitly is
            # the current RhinoCommon form.
            objref = Rhino.DocObjects.ObjRef(
                sc.doc,
                rhino_object.Id
            )

            selected_curve_objrefs.append(objref)


    # If we found at least one preselected curve, we are done.
    #
    # Most importantly, GetObject is NEVER created or called here.
    # Consequently Rhino does not ask the user to select curves again.
    if selected_curve_objrefs:
        return selected_curve_objrefs


    # ------------------------------------------------------------------
    # No curves were preselected:
    # use normal interactive Rhino selection
    # ------------------------------------------------------------------

    go = Rhino.Input.Custom.GetObject()

    go.SetCommandPrompt("Select curves to rebuild")

    # Only allow curve objects.
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve

    # Do not allow Brep edges etc. as sub-object selections.
    go.SubObjectSelect = False

    # Do not allow reference/worksession objects.
    go.ReferenceObjectSelect = False

    # Minimum 1 curve.
    # Maximum 0 means unlimited.
    get_result = go.GetMultiple(1, 0)

    if get_result != Rhino.Input.GetResult.Object:
        return None

    return list(go.Objects())


def get_spacing():
    """
    Ask for the maximum desired control-point spacing.

    If this script has previously been run during the current Rhino
    session, the last-used spacing becomes the command-line default.

    For example:

        Maximum control point spacing <4.000>:

    Pressing Enter accepts 4.000.

    Typing another number replaces it, and that new number becomes the
    default next time.
    """

    gn = Rhino.Input.Custom.GetNumber()

    gn.SetCommandPrompt("Maximum control point spacing")

    # Spacing must be greater than zero.
    gn.SetLowerLimit(0.0, True)


    # ------------------------------------------------------------------
    # Restore the previous spacing, if we have one
    # ------------------------------------------------------------------

    if SPACING_STICKY_KEY in sc.sticky:

        previous_spacing = sc.sticky[SPACING_STICKY_KEY]

        # SetDefaultNumber does two useful things:
        #
        # 1. It displays the previous value in the Rhino command line.
        #
        # 2. It allows the user to press Enter to accept that value.
        gn.SetDefaultNumber(previous_spacing)


    # ------------------------------------------------------------------
    # Ask for the number
    # ------------------------------------------------------------------

    get_result = gn.Get()

    if get_result != Rhino.Input.GetResult.Number:
        return None

    spacing = gn.Number()


    # ------------------------------------------------------------------
    # Remember it for next time
    # ------------------------------------------------------------------

    sc.sticky[SPACING_STICKY_KEY] = spacing

    return spacing


# ----------------------------------------------------------------------
# MAIN COMMAND
# ----------------------------------------------------------------------

def main():

    # ------------------------------------------------------------------
    # 1. GET CURVES
    # ------------------------------------------------------------------

    # This function first checks for preselected curves.
    #
    # Therefore:
    #
    #     Curves already selected
    #             |
    #             v
    #     Skip selection prompt
    #
    # Whereas:
    #
    #     Nothing selected
    #             |
    #             v
    #     "Select curves to rebuild"
    #
    objrefs = get_input_curves()

    if not objrefs:
        return


    # ------------------------------------------------------------------
    # 2. GET MAXIMUM SPACING
    # ------------------------------------------------------------------

    spacing = get_spacing()

    if spacing is None:
        return


    # ------------------------------------------------------------------
    # 3. REBUILD EACH CURVE
    # ------------------------------------------------------------------

    rebuilt_count = 0
    failed_count = 0

    for index, objref in enumerate(objrefs, start=1):

        # Get the actual curve geometry.
        curve = objref.Curve()

        if curve is None:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: could not access curve geometry.".format(index)
            )

            continue


        # --------------------------------------------------------------
        # Measure curve
        # --------------------------------------------------------------

        curve_length = curve.GetLength()

        if curve_length <= 0.0:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: invalid or zero curve length.".format(index)
            )

            continue

        is_closed = curve.IsClosed


        # --------------------------------------------------------------
        # Determine number of control points
        # --------------------------------------------------------------

        point_count = calculate_point_count(
            curve_length,
            spacing,
            is_closed
        )


        # --------------------------------------------------------------
        # Check point-count limit
        # --------------------------------------------------------------

        if point_count > MAX_POINT_COUNT:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: would require {1} control points; "
                "maximum allowed is {2}. Curve was not changed.".format(
                    index,
                    point_count,
                    MAX_POINT_COUNT
                )
            )

            continue


        # --------------------------------------------------------------
        # Rebuild curve
        # --------------------------------------------------------------

        rebuilt_curve = curve.Rebuild(
            point_count,
            DEGREE,
            PRESERVE_TANGENTS
        )

        if rebuilt_curve is None:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: rebuild failed.".format(index)
            )

            continue


        # --------------------------------------------------------------
        # Defensive check for closed curves
        # --------------------------------------------------------------

        if is_closed and not rebuilt_curve.IsClosed:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: rebuilt result was unexpectedly open. "
                "Original curve was not changed.".format(index)
            )

            continue


        # --------------------------------------------------------------
        # Replace original curve
        # --------------------------------------------------------------

        replace_succeeded = sc.doc.Objects.Replace(
            objref,
            rebuilt_curve
        )

        if not replace_succeeded:

            failed_count += 1

            Rhino.RhinoApp.WriteLine(
                "Curve {0}: could not replace original curve.".format(index)
            )

            continue

        rebuilt_count += 1


        # --------------------------------------------------------------
        # Calculate nominal resulting spacing for reporting
        # --------------------------------------------------------------

        if is_closed:

            nominal_spacing = curve_length / point_count
            curve_type = "closed"

        else:

            nominal_spacing = curve_length / (point_count - 1)
            curve_type = "open"


        Rhino.RhinoApp.WriteLine(
            "Curve {0}: {1}, length {2:.6g} -> "
            "{3} control points, nominal spacing {4:.6g}".format(
                index,
                curve_type,
                curve_length,
                point_count,
                nominal_spacing
            )
        )


    # ------------------------------------------------------------------
    # 4. FINISH
    # ------------------------------------------------------------------

    sc.doc.Views.Redraw()

    Rhino.RhinoApp.WriteLine(
        "RebuildBySpacing complete: {0} rebuilt, {1} failed.".format(
            rebuilt_count,
            failed_count
        )
    )


# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------

if __name__ == "__main__":
    main()