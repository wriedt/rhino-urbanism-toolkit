# QuickArea has been split

- [QuickFloorArea](QuickFloorArea.md), alias **RUTQuickFloorArea**, measures base
  area, prints it and copies it with m². Failures stay available for inspection
  until Enter/Escape acknowledges them.
- [FloorArea](FloorArea.md), alias **RUTFloorArea**, is the floating area inspector
  that follows selection and geometry edits. It stays open until its × is clicked.

Both support solids outside and inside nested blocks. Neither shows partial totals
when faulty geometry is selected. Settings are not shared between them.

`QuickArea.py` remains a compatibility entry point for existing toolbar buttons
and opens FloorArea. Use the new names for new shortcuts.
