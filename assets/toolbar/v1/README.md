# RUT toolbar icons - draft v1

Original vector artwork for the 18 proposed beta commands, using the existing
RUT aqua drawing-office palette. Each command has transparent light- and dark-mode
SVG artwork plus transparent PNG exports at 24, 32 and 48 pixels. The SVG is the
editable source format to use in Rhino 8's Script Editor command properties.

`preview.png` shows all commands on light and dark backgrounds at actual export
sizes. `manifest.json` maps commands to their theme-specific SVG files and marks
the two conditional beta tools. The contact sheet is a review aid, not a sprite
atlas consumed by Rhino.

These approved draft assets are now embedded in the plugin project's command
entries and generated toolbar. They have not yet been tested in Rhino's actual
toolbar. Final review should check recognition at small sizes, contrast
against Rhino's actual toolbar backgrounds and display scaling. Native command
tooltips should supply the command names; the icons contain no tiny text.

The icon generator is `generate.cjs`. Run with Node.js and a Sharp module:

```text
node generate.cjs <path-to-sharp-module>
```

No generator dependency is needed by Rhino or included in the plugin. Artwork
uses only SVG paths and circles, with explicit colors and no external resources.

Rhino reference: https://developer.rhino3d.com/guides/scripting/projects-create/
