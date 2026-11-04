# Push/pull straight curve section

Run `PushPullCurve.py`, click a straight section, then click its new position
or type a distance. Typed distances show a preview; press Enter to apply.
Escape cancels. The curve stays in its original plane.

- **Extrude=No** (default): extend or trim angled neighbours. A collinear
  neighbour stays fixed, with a new perpendicular connecting segment at the
  shared vertex. This lets you move one section of a subdivided straight edge.
- **Extrude=Yes**: move the selected segment with perpendicular connections
  at both ends, keeping the neighbouring outline fixed. Toggle Extrude before
  selection or while picking/reviewing the distance. An existing perpendicular
  neighbour already serves as a connection, so redundant vertices are omitted.
- **Replace=Yes/No**: replace the original curve, or keep it and create a copy.
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
