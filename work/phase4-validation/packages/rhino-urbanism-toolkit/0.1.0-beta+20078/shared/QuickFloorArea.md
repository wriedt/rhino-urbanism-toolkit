# QuickFloorArea

Run **RUTQuickFloorArea** in Rhino 8, or run `QuickFloorArea.py` in the Python 3
Script Editor. Compatible preselection is used immediately; otherwise Rhino asks
you to select solids or blocks. The selection is preserved.

The command adds the areas of each solid's lowest horizontal planar base faces,
including trimmed holes, and prints and copies the complete total as, for example,
`123.45 m²`. Successful output is a single command-line message:
`Base plane area: 123.45 m² | Value copied to clipboard`.
Precision is fixed at two decimal places. Document units are converted
to square metres. This is a sum of individual bases, without merging overlaps.
It does not calculate sections, so short solids can still have a valid base area.

Open or invalid Breps, missing horizontal bases, and blocks without solids prevent
any total from being shown or copied. The clipboard stays unchanged. Rhino prints
the reasons with originating object/block names and short IDs. Temporary coral
wires mark faulty geometry, including world-transformed contents of nested blocks.
The command stays active so you can navigate and inspect the geometry. Press
Enter to acknowledge or Escape to cancel; either removes the coral overlay.
No tags, layers, colours or permanent geometry are added.

Solids represented by Breps and extrusions are supported. Non-solid Brep contents
inside blocks are errors; curves and other block decoration are ignored.
Meshes and standalone curves/surfaces are outside the supported measurement scope.

For an alias or toolbar button, use:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\QuickFloorArea.py"
```

Keep `floor_area.py`, `urbanism_ui.py` and `viewport_ui.py` alongside the script.
No settings are saved or shared with [FloorArea](FloorArea.md).
