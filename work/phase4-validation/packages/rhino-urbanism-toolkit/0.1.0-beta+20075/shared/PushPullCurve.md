# Push/pull straight curve section

The viewport panel uses the heading `RUT | Push/pull` and sits 32 screen pixels
from the left edge and 48 from the top, leaving space below the viewport title
dropdown. Keep `viewport_ui.py` alongside the script; it shares panel spacing
and font sizes with QuickArea.

Run `PushPullCurve.py`, click a straight section, then click its new position
or type a distance. Typed distances show a preview; press Enter to apply.
Escape cancels. Planar curves stay in their original plane. For a non-planar
curve, choose **Project** to work on a projection onto the active viewport's
CPlane, or **Cancel** to leave it unchanged. Projection is perpendicular to
that CPlane and is only committed when you apply a valid push/pull movement.

While choosing or reviewing the distance, choose **SplitSegment**:

1. Pick a split point inside the selected segment, away from its ends.
2. Hover over either half to highlight it, then click once to select it.
3. Push/pull that half as usual. The other half stays fixed at the split, with
   a perpendicular connecting segment joining it to the moved half.

You can split the selected half again before applying the movement. Splitting
resets any typed distance. Escape at either split prompt cancels the entire
command. Projection, splits, and movement form one edit for Undo; no intermediate
curves are added.

- **Extrude=No** (default): extend or trim angled neighbours. A collinear
  neighbour stays fixed, with a new perpendicular connecting segment at the
  shared vertex. This lets you move one section of a subdivided straight edge.
- **Extrude=Yes**: move the selected segment with perpendicular connections
  at both ends, keeping the neighbouring outline fixed. Toggle Extrude before
  selection or while picking/reviewing the distance. An existing perpendicular
  neighbour already serves as a connection, so redundant vertices are omitted.
- **Replace=Yes/No**: replace the original curve, or keep it and create a copy.
  With projection, **Replace=No** keeps the original non-planar curve and adds
  the edited planar result.
- **AllowCollapse=Yes/No**: allow segments to disappear when trimming past
  vertices. Removed original edges appear in coral with a removal count.
  Adding connecting edges does not require AllowCollapse.
- **ShowPreview=Yes/No**: control the geometry overlay; status stays visible.

Works with planar polylines and mixed polycurves containing lines, arcs, and
splines, including open curves. Only straight sections can be selected. Existing collinear vertices
are meaningful selection boundaries. Positive typed distances use the cursor's
side; negative values flip it. Ortho does not redirect this tool's distance
picker; Rhino's global settings are preserved.

Collisions with another part of the outline are blocked. Closed-curve trimming
can continue through several consecutive vertices. When the selected edge
itself disappears, movement stops there. Deleting an entire collapsed curve
requires confirmation. Open curves retain their existing trim-past-vertex limits.

For mixed curves, normal mode trims curved neighbours at their intersections
with the moved line, including originally tangent joins. If a curved neighbour
has no intersection, it stays unchanged and gets a perpendicular connector.
Extrude keeps curved neighbours intact and adds connectors. A single curved
component can be clipped at both ends. Curves retain their exact geometry;
there is no conversion to polyline approximations.

Ambiguous, self-intersecting, disconnected, and fully collapsed mixed-curve
results are blocked. Straight sections must exist as distinct components;
a smooth spline is not automatically split into selectable straight-looking spans.
Keep `pushpull_mixed.py` alongside the main script (and `urbanism_ui.py` for
whole-polyline deletion confirmation).
