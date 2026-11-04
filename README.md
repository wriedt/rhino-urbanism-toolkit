# Rhino Urbanism Toolkit (RUT)

Utility scripts for architecture and urbanism studios working in Rhino 8.

## Running the tools

Keep each command with its shared helper modules, including `urbanism_ui.py`.
The recommended installation folder is `C:\Projects\rhino-urbanism-toolkit`.
If you use another folder, adjust the full paths in the command documentation
and your Rhino toolbar buttons or aliases accordingly.

Open `rhino-urbanism-toolkit.rhproj` in Rhino's Script Editor for the project
settings. RUT is the short name used in tool dialogs; individual command and
helper filenames remain stable.

## Tools

- [PushPullCurve](PushPullCurve.md): move or extrude straight sections of planar
  polylines or mixed curves, with exact arc/spline trimming and live preview.
- [Block layer assignment](BlockLayerAssignment.md): assign a layer to a block
  definition, bulk-edit assignments, resolve missing target layers, and preview
  cleanup of top-level and nested instances with shared-copy safeguards (Phase 4).
