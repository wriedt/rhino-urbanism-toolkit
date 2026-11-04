# CreateBlockVersion prototype

Rhino 8, Python 3. Creates a new independent block definition from the selected
instance's current definition, then switches only selected instances to it.

## Run

Paste this in Rhino's command line or a toolbar button:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism\CreateBlockVersion.py"
```

You can preselect blocks or select them when prompted. Multiple selected
instances of one definition share one new definition. Different source
definitions are processed separately, with all prompts completed before changes
are made. One Undo reverses the whole operation.

## Naming

- The last group of digits is the default version number, even when followed by
  text: `Building_2026_Type_03_Left` uses `03`.
- At the preview, press Enter or choose Create to accept. Choose Number to
  change the number group. Rhino prints each choice with its digits in brackets.
- Existing definitions with the same prefix and suffix form the naming family.
  Matching ignores case and padding differences. Only the chosen digit group
  varies; all other characters and numbers must match.
- The highest existing version plus one is used, including unused definitions.
  Deleted definitions do not count. Padding follows the selected source name:
  `Block_001` becomes `Block_009` if `Block_008` exists. Width expands when needed.
- Geometry always comes from the selected source, even if a newer version exists.
- For an unnumbered source, choose RenameAndCreate to enter a starting name
  (default: the original name plus `_01`). The original definition is renamed
  for all existing instances; selected instances switch to the next version.
  The usual highest-version rule still applies if later versions already exist.
- Cancel/Escape before creation makes no definition changes. An invalid or
  occupied starting name ends the command with an explanation; rerun to correct it.

## Preserved and limitations

Instance IDs, attributes and transforms are retained. Definition geometry,
member attributes, description, URL and text user strings are copied. Nested
block references keep pointing to their original definitions. This is not a
recursive make-unique command.

This prototype handles editable, top-level embedded blocks. Linked/reference
definitions and locked/reference instances are rejected. Arbitrary third-party
plugin data on the definition is not explicitly copied. The number-group choice
is made per run; it is not stored as a lasting naming convention.

## Verified in Rhino on 2026-10-23

`work/test_create_block_version_rhino.py` passed 22 checks inside the user's
Rhino 8 session: the six naming examples, family matching, group override,
highest-number selection, shared selected instances, unchanged unselected
instances, retained instance IDs and attributes, rotated/mirrored/nonuniformly
scaled transforms, world-space geometry, shared nested definitions, member
attributes, definition metadata, source geometry from an older version,
unnumbered baseline conversion, collision rejection, and rollback after an
intentional late failure. Its temporary fixtures were removed.

The actual saved script was also run through Rhino's command-line script runner:

- `VersionDemo_01` became `VersionDemo_06` because version `05` already existed.
- Undo removed version `06` and restored the instance; Redo restored version `06`.
- The unnumbered prompt renamed `EntranceDemo` to `EntranceDemo_01` and created
  `EntranceDemo_02`. One Undo reversed both changes; Redo restored both.
- Number > Group1 changed `NumberDemo_03_Floor_02` to `NumberDemo_09_Floor_02`
  with version `08` already present.
- Declining the unnumbered prompt left its source name and instances unchanged.

Labelled demo blocks remain in the open, unsaved Rhino document for manual use.
Their text dots are demonstration labels, not automatically maintained names.

## API references

- [McNeel: ScriptEditor command macros](https://developer.rhino3d.com/guides/scripting/advanced-scripteditor-macros/)
- [McNeel: ReplaceInstanceObject](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_DocObjects_Tables_ObjectTable_ReplaceInstanceObject.htm)
