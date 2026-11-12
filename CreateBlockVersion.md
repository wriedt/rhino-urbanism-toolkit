# RUTCreateBlockVersion

Select copies of one local definition, review the proposed version, and choose
**Create version**. Only selected copies switch to the new independent definition.

The highest matching family version determines the next number or letter, including
unused definitions. Examples: `v02 → v03`, `_001 → _002`, `A → B`; if Z already exists,
selecting A or Z creates AA. Combined tokens such as A01 keep their letter prefix.
Formatting and metadata, including home-layer rules, are preserved.

**Adjust naming** contains one Version part selector with the chosen text marked
in brackets. **Starting name** appears only for an unversioned source. Any source
rename shown in the review affects all its copies.

Enter/Space invokes the primary action outside text entry/open dropdowns.
Escape/X cancels. One Undo reverses the operation.

Run `RUTCreateBlockVersion`, or use this toolbar macro:

```text
! _-ScriptEditor _Run "C:\Projects\rhino-urbanism-toolkit\CreateBlockVersion.py"
```

See [Block commands](BlockCommands.md) for the complete six-command guide.
