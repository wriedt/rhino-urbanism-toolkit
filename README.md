# Rhino Urbanism Toolkit (RUT)

Utility scripts for architecture and urbanism studios working in Rhino 8.

## Plugin beta preparation

The beta includes 18 RUT commands on one toolbar, with separators between
Layers, Blocks, Floor Area and Curve Tools. See [START_HERE.txt](START_HERE.txt)
for the short installation instructions.

The ZIP contains the plugin, toolbar, install/remove helpers, short start note,
license and buildable source. Command guides, feedback forms, release notes and
development records are excluded. [Build instructions](packaging/README.md)
are for development only.

## Running the tools

Keep each command with its shared helper modules, including `urbanism_ui.py`.
The recommended installation folder is `C:\Projects\rhino-urbanism-toolkit`.
If you use another folder, adjust the full paths in the command documentation
and your Rhino toolbar buttons or aliases accordingly.

Open `rhino-urbanism-toolkit.rhproj` in Rhino's Script Editor for the project
settings. RUT is the short name used in tool dialogs; individual command and
helper filenames remain stable.

## Tools

- [Layer utilities](LayerTools.md): isolate selected objects' layers and restore
  visibility or locks, show/unlock all layers, and expand/collapse the layer tree.

- [QuickFloorArea](QuickFloorArea.md): print and copy a solid/base area in m²,
  with command-line warnings and coral geometry inspection if measurement fails.
  Run `RUTQuickFloorArea`.
- [FloorArea](FloorArea.md): floating section/base-area inspector that updates
  with selection and geometry edits. Run `RUTFloorArea`.

- [Block commands](BlockCommands.md): six focused commands for creating and
  consolidating versions, renaming families, and assigning, applying, or reviewing
  block home layers. Choices and reviews use the shared aqua dialogs.
  Run `RUTCreateBlockVersion`, `RUTConsolidateBlockVersions`, `RUTRenameBlockFamily`,
  `RUTAssignBlockLayer`, `RUTApplyBlockLayers` and `RUTShowBlockLayers`.

- [Shape Builder](ShapeBuilder.md): merge or erase curve and hatch regions, preserve
  leftover open curves, and inherit the drag-start shape's properties. Run `RUTShapeBuilder`.

- [PushPullCurve](PushPullCurve.md): move or extrude straight sections of planar
  polylines or mixed curves, with exact arc/spline trimming and live preview.
- [Block home layers](BlockLayerAssignment.md): save definition-wide rules and
  review top-level or optional nested movements, skipping linked/reference blocks.
