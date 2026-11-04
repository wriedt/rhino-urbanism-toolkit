# Aqua drawing-office appearance

The user's approved tokens, subject to new explicit directions:

| Role | Light | Dark |
|---|---|---|
| Main text | `#263f4b` | `#e9f5f6` |
| Secondary text | `#526d76` | `#b9d0d5` |
| Accent / active choice | `#246e7b` | `#b1e4df` |
| Gradient start | `#f6f8f8` | `#223138` |
| Gradient end | `#e2f1ed` | `#294944` |
| Container / field | `#fcfefe` | `#263b43` |
| Border | `#c6d8da` | `#49616b` |
| Text on accent | `#f5ffff` | `#123d46` |
| Exclusion warning / failed wires | `#a34535` | `#f0ab99` |

Follow Rhino's current light/dark appearance when opening a dialog. Refresh tokens
in cached modules. Keep the gradient subtle, with continuous visible container
borders rather than glow or heavy shadows.

- Frameless outer surface, radius 12 logical pixels; compact toolkit/command
  header, custom X, draggable header, and thin divider.
- Separate context/settings, primary result, secondary metrics, and actions using
  spacing and containers (radius 8). Buttons use radius 6.
- Keep the main measurement prominent; align secondary labels and values in one
  comparison container.
- Segoe UI, regular weight by default. Established Eto sizes: caption 9 pt, body
  10.5 pt, heading 18 pt, main value 24 pt (12/14/24/32 logical pixels at 96 DPI).
- Sentence case; avoid competing mixtures of bold, caps, italic, and size changes.
  Let spacing, size roles, and secondary colour establish hierarchy.
- Hide empty feedback footers. Avoid persistent explanations of obvious actions.
- Theme scrollbars: rounded dark/pale track, aqua/teal thumb, stronger hover/drag
  opacity. The Windows implementation uses a 12-pixel track, 3-pixel padding,
  and native scrolling semantics.
- Preserve visible focus, selected states, native button accessibility, Enter's
  default action and Escape's cancel/close behavior.

Inspect the complete live window. Matching colours alone is insufficient if
containers, corners, typography, spacing, or borders do not match the reference.
