# Block naming conventions

The toolkit follows the naming system already used by the family. It does not
require conversion to `_vNN`.

| Current version | Next |
|---|---|
| `House_v02` | `House_v03` |
| `House_001` | `House_002` |
| `House 1` | `House 2` |
| `House_A` | `House_B` |
| `House_A01` | `House_A02` |
| `House_Z` | `House_AA` |

Case, separators and padding are retained. For `A01`, the letter prefix remains
fixed and the numeric portion increments. The dialog lets you choose `01` instead
if `A` belongs to the shared family name. Numeric padding expands only as needed.

Detection provides suggestions rather than guessing silently. Correct the version
part or choose an alternative split; the member review shows the exact scope.
Dimension patterns such as `3000x1500`, `Ø10m` and leading `2D` are excluded from
automatic suggestions. Other bare numbers can still be dimensions or product codes.

Copy words and numeric branches with an existing exact parent name can participate
in consolidation. Each definition receives its own sequential version; definitions
are not merged geometrically. Family renaming preserves their existing suffixes.

See [Block commands](BlockCommands.md) for the six commands and complete workflow.
