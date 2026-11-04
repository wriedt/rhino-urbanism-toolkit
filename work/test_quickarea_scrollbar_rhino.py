"""Live native scrollbar style and scrolling checks; no document fixtures."""
import ast
import os
import math
import clr
import runpy
import scriptcontext as sc
import Eto.Forms as forms
from System import Guid
from System.Windows.Controls import ScrollViewer
from System.Windows.Controls.Primitives import ScrollBar
from System.Windows.Media import VisualTreeHelper

sc.doc = __rhino_doc__
q = runpy.run_path(r'C:\Projects\rhino-urbanism\QuickArea.py', run_name='qa_scroll_test')
ui = q['ui']
exec(compile(open(ui.__file__, encoding='utf-8').read(), ui.__file__, 'exec'), ui.__dict__)
output = r'C:\Projects\rhino-urbanism\work\quickarea-ui'
source = ast.parse(open(r'C:\Projects\rhino-urbanism\work\test_quickarea_ui_rhino.py', encoding='utf-8').read())
capture_node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
exec(compile(ast.Module(body=[capture_node], type_ignores=[]), 'capture', 'exec'))


def descendants(root):
    yield root
    for i in range(VisualTreeHelper.GetChildrenCount(root)):
        yield from descendants(VisualTreeHelper.GetChild(root, i))


dialog = q['create_issues_dialog'](__rhino_doc__,
    [(Guid.NewGuid(), 'No section curves at 3 m above base') for _ in range(12)], [])
errors = []
timer = forms.UITimer()
timer.Interval = 0.8


def inspect(sender, event):
    timer.Stop()
    try:
        all_visuals = list(descendants(dialog.ControlObject.Content))
        viewer = next(v for v in all_visuals if isinstance(v, ScrollViewer))
        bar = next(v for v in all_visuals if isinstance(v, ScrollBar) and v.IsVisible)
        assert bar.Width == 12, bar.Width
        bar.ApplyTemplate()
        track = bar.Template.FindName('PART_Track', bar)
        assert track is not None
        track.Thumb.ApplyTemplate()
        grip = track.Thumb.Template.FindName('Grip', track.Thumb)
        expected = '#FFB1E4DF' if ui.DARK else '#FF246E7B'
        assert str(grip.Background.Color).upper() == expected
        assert viewer.ScrollableHeight > 0
        capture(dialog, 'themed-scrollbar')
        before = viewer.VerticalOffset
        ScrollBar.PageDownCommand.Execute(None, bar)
        viewer.UpdateLayout()
        assert viewer.VerticalOffset > before
        print('THEMED_SCROLLBAR_PASS: aqua thumb, rounded track, native page scrolling')
    except Exception as error:
        errors.append(str(error))
    finally:
        dialog.AbortButton.PerformClick()


timer.Elapsed += inspect
dialog.Shown += lambda s, e: timer.Start()
try:
    dialog.show_for_doc(__rhino_doc__, picking=True)
finally:
    timer.Dispose()
assert not errors, errors
