"""Run inside the user's Rhino 8 instance through MCP. Removes its fixtures."""
import os
import runpy
import math
import scriptcontext as sc
import Rhino
import Eto.Forms as forms
import clr

sc.doc = __rhino_doc__
doc = __rhino_doc__
q = runpy.run_path(r'C:\Projects\rhino-urbanism\QuickArea.py', run_name='quickarea_test')
ui = q['ui']
# Rhino's ScriptEditor can cache module bytecode during active development.
exec(compile(open(ui.__file__, encoding='utf-8').read(), ui.__file__, 'exec'), ui.__dict__)
g = q['main'].__globals__
output = r'C:\Projects\rhino-urbanism\work\quickarea-ui'
os.makedirs(output, exist_ok=True)
checks, errors, objects, definitions, timers = [], [], [], [], []
selected_before = [o.Id for o in doc.Objects.GetSelectedObjects(False, False)]
object_count_before = sum(1 for obj in doc.Objects if not obj.IsDeleted)
height_key = q['HEIGHT_STICKY_KEY']
had_height = height_key in sc.sticky
previous_height = sc.sticky.get(height_key)
sc.sticky[height_key] = 1.5
original_show = ui.AquaDialog.show_for_doc
original_result = g['show_result_dialog']
original_preview = g['SectionPreview']
previews = []


def make_preview(doc, curves):
    preview = original_preview(doc, curves)
    previews.append(preview)
    return preview


g['SectionPreview'] = make_preview


def check(condition, text):
    if not condition:
        raise AssertionError(text)
    checks.append(text)


def capture(dialog, name):
    # Render the actual live WPF content at its displayed DPI, not a mockup.
    clr.AddReference('PresentationCore')
    clr.AddReference('WindowsBase')
    from System.Windows.Media import VisualTreeHelper, PixelFormats
    from System.Windows.Media.Imaging import RenderTargetBitmap, PngBitmapEncoder, BitmapFrame
    from System.IO import FileStream, FileMode
    native = dialog.ControlObject.Content
    dpi = VisualTreeHelper.GetDpi(native)
    bitmap = RenderTargetBitmap(int(math.ceil(native.ActualWidth * dpi.DpiScaleX)),
        int(math.ceil(native.ActualHeight * dpi.DpiScaleY)),
        dpi.PixelsPerInchX, dpi.PixelsPerInchY, PixelFormats.Pbgra32)
    bitmap.Render(native)
    encoder = PngBitmapEncoder()
    encoder.Frames.Add(BitmapFrame.Create(bitmap))
    stream = FileStream(os.path.join(output, name + '.png'), FileMode.Create)
    try:
        encoder.Save(stream)
    finally:
        stream.Dispose()


def show_auto(dialog, action, name, picking=False):
    timer = forms.UITimer()
    timer.Interval = 0.7
    def tick(sender, event):
        timer.Stop()
        try:
            capture(dialog, name)
            action(dialog)
        except Exception as exc:
            errors.append(str(exc))
            dialog.Close(False)
    timer.Elapsed += tick
    dialog.Shown += lambda s, e: timer.Start()
    timers.append(timer)
    return original_show(dialog, doc, picking)


def select(ids):
    doc.Objects.UnselectAll()
    for object_id in ids:
        doc.Objects.Select(object_id)


def run_main(ids, name, cancel=False, expect_result=True, close_result=False, change_height=None, copy_result=False):
    select(ids)
    result_calls = []
    def result(*args):
        result_calls.append(args)
        return original_result(*args)
    def auto(self, target_doc, picking=False):
        if hasattr(self, 'issue_buttons'):
            def select_issue(d):
                target = d.issue_object_ids[0]
                d.issue_buttons[0].PerformClick()
                check({o.Id for o in doc.Objects.GetSelectedObjects(False, False)} == {target},
                      'Clicking a real issue entry selects its object: ' + name)
                capture(d, name + '-issues-selected')
                d.AbortButton.PerformClick()
            return show_auto(self, select_issue, name + '-issues', picking)
        if hasattr(self, 'continue_button'):
            action = (lambda d: d.cancel_button.PerformClick()) if cancel else (
                lambda d: d.continue_button.PerformClick())
            return show_auto(self, action, name + '-warning')
        if hasattr(self, 'done_button'):
            check(self.decimal_slider.Value == 2, 'Default precision is two decimals: ' + name)
            check(not self.status.Visible, 'Crossed-out footer is absent: ' + name)
            coverage = result_calls[-1][11]
            check(bool(self.coverage_warning) == bool(coverage['warning']),
                  'Result warning visibility matches exclusions: ' + name)
            if name == 'short-volume-issue':
                check('1 of 2 selected objects excluded' in self.coverage_warning.Text and
                      'No section at 1.5 m for 1 solid' in self.coverage_warning.Text,
                      'Result retains exclusion count and section height after issues close')
                check(len(previews[-1].failed_breps) == 1,
                      'Failed solid included in temporary coral preview')
            if name == 'partial-block':
                check('1 selected block is only partly counted' in self.coverage_warning.Text,
                      'Partly counted block is reported separately from excluded objects')
            def close(d):
                if change_height is not None and len(result_calls) == 1:
                    feed = forms.UITimer()
                    feed.Interval = 0.6
                    def send(s, e):
                        feed.Stop()
                        Rhino.RhinoApp.SendKeystrokes(str(change_height), True)
                    feed.Elapsed += send
                    timers.append(feed)
                    feed.Start()
                    d.height_button.PerformClick()
                    feed.Stop()
                    return
                if name == 'roof':
                    from System.Drawing import Size
                    viewport = doc.Views.ActiveView.ActiveViewport
                    saved_projection = Rhino.DocObjects.ViewportInfo(viewport)
                    saved_location = Rhino.Geometry.Point3d(viewport.CameraLocation)
                    saved_target = Rhino.Geometry.Point3d(viewport.CameraTarget)
                    try:
                        viewport.ZoomBoundingBox(previews[-1].bounds)
                        doc.Views.Redraw()
                        bitmap = doc.Views.ActiveView.CaptureToBitmap(Size(900, 650))
                        try:
                            bitmap.Save(os.path.join(output, 'section-preview-viewport.png'))
                        finally:
                            bitmap.Dispose()
                    finally:
                        restored = viewport.SetViewProjection(saved_projection, False)
                        viewport.SetCameraTarget(saved_target, False)
                        check(restored and viewport.CameraLocation.DistanceTo(saved_location) < 1e-8
                              and viewport.CameraTarget.DistanceTo(saved_target) < 1e-8,
                              'Viewport camera restored after preview capture')
                        saved_projection.Dispose()
                        doc.Views.Redraw()
                if copy_result:
                    d.copy_button.PerformClick()
                    check(not d.Visible, 'Copy closes result during full command')
                else:
                    (d.close_button if close_result else d.done_button).PerformClick()
            return show_auto(self, close, name + '-result', picking)
        return show_auto(self, lambda d: d.AbortButton.PerformClick(), name + '-message')
    ui.AquaDialog.show_for_doc = auto
    g['show_result_dialog'] = result
    q['main']()
    check(all(not p.Enabled for p in previews), 'Section highlights disabled after close: ' + name)
    check(not errors, 'No timer, rendering, or button errors: ' + name)
    expected = (2 if change_height is not None else 1) if expect_result and not cancel else 0
    check(len(result_calls) == expected, 'Result routing: ' + name)
    return result_calls


try:
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    tol = doc.ModelAbsoluteTolerance
    angles = (math.radians(30), math.radians(1))
    box = Rhino.Geometry.Box(Rhino.Geometry.Plane.WorldXY,
        Rhino.Geometry.Interval(0, 10 * scale), Rhino.Geometry.Interval(0, 8 * scale),
        Rhino.Geometry.Interval(0, 4 * scale)).ToBrep()
    fixture_transform = Rhino.Geometry.Transform.Translation(1000 * scale, 1000 * scale, 0)
    box.Transform(fixture_transform)
    box_id = doc.Objects.AddBrep(box)
    objects.append(box_id)
    result = q['section_area_of_solid_at_1p5m'](box, tol, *angles)
    check(result[0] and abs(result[1] - 80 * scale**2) < max(tol, 1e-6),
          'Box section area: 80 square metres converted to document units')
    roof = Rhino.Geometry.Brep.CreateFromBox([
        Rhino.Geometry.Point3d(x*scale, y*scale, z*scale)
        for x, y, z in [(0,0,0),(10,0,0),(10,8,0),(0,8,0),
                         (2,0,4),(8,0,4),(8,8,4),(2,8,4)]])
    roof.Transform(fixture_transform)
    result = q['section_area_of_solid_at_1p5m'](roof, tol, *angles)
    check(result[0] and abs(result[1] - 68 * scale**2) < max(tol, 1e-6),
          'Tapered volume section: 68 square metres, 15 percent reduction')
    roof_id = doc.Objects.AddBrep(roof)
    objects.append(roof_id)
    open_brep = Rhino.Geometry.PlaneSurface(Rhino.Geometry.Plane.WorldXY,
        Rhino.Geometry.Interval(0, scale), Rhino.Geometry.Interval(0, scale)).ToBrep()
    open_id = doc.Objects.AddBrep(open_brep)
    objects.append(open_id)
    calls = run_main([box_id], 'box')
    check(calls[0][2] == q['round_half_up'](80 * scale**2), 'Real main flow returned correct rounded box area')
    calls = run_main([roof_id], 'roof')
    check(abs(calls[0][4] - 15) < 1e-6, 'Real main flow returned 15 percent reduction')
    short = Rhino.Geometry.Box(Rhino.Geometry.Plane.WorldXY,
        Rhino.Geometry.Interval(0, scale), Rhino.Geometry.Interval(0, scale),
        Rhino.Geometry.Interval(0, 0.5 * scale)).ToBrep()
    short.Transform(fixture_transform)
    short_id = doc.Objects.AddBrep(short)
    objects.append(short_id)
    calls = run_main([box_id, short_id], 'short-volume-issue')
    check(calls[0][5] == 1, 'Summary counts successful solids only')
    calls = run_main([short_id], 'all-failed')
    check(calls[0][5] == 0 and calls[0][11]['excluded_count'] == 1,
          'All-failed selection reports zero counted solids and one exclusion')
    import System
    definition = doc.InstanceDefinitions.Add('QuickAreaTest-' + str(System.Guid.NewGuid()),
        '', Rhino.Geometry.Point3d.Origin, [box, short],
        [Rhino.DocObjects.ObjectAttributes(), Rhino.DocObjects.ObjectAttributes()])
    definitions.append(definition)
    instance_id = doc.Objects.AddInstanceObject(definition, Rhino.Geometry.Transform.Identity)
    objects.append(instance_id)
    calls = run_main([instance_id], 'partial-block')
    check(calls[0][5] == 1 and calls[0][11]['excluded_count'] == 0
          and calls[0][11]['partial_count'] == 1,
          'Mixed-success block counts its successful solid and retains failed-solid warning')
    calls = run_main([box_id, open_id], 'mixed')
    check(calls[0][2] == q['round_half_up'](80 * scale**2), 'Skipped open surface without changing total')
    run_main([box_id], 'close-x', close_result=True)
    run_main([box_id, open_id], 'cancel', cancel=True)
    run_main([open_id], 'open-only', expect_result=False)
    ui.message_dialog(doc, 'QuickArea | Section issues',
                      'Review the section issues.',
                      'Some solids could not be counted:\n' + '\n'.join(
                          '- Object fixture: example diagnostic {}'.format(i) for i in range(20)))
    check(not errors, 'No-solids and scrollable diagnostics dialogs rendered successfully')
    # Real native clipboard interaction; restore all original clipboard formats.
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import Clipboard, DataObject
    previous = Clipboard.GetDataObject()
    snapshot = DataObject()
    if previous is not None:
        for data_format in previous.GetFormats(False):
            snapshot.SetData(data_format, False, previous.GetData(data_format, False))
    dlg = q['create_result_dialog']('68.8391 meters²', '82.3892 meters²', 69, 82, 16.45,
                                  1, 1, 1, 68.83912345, 82.38923456)
    def test_copy(d):
        check(d.section_label.Text == '68.84 m²' and d.base_label.Text == '82.39 m²',
              'Default two-decimal formatting uses full-precision areas')
        check(d.ControlObject.AllowsTransparency and d.ControlObject.Content.Clip.RadiusX == 12,
              'Outer window has transparent rounded corners')
        d.decimal_slider.Value = 0
        check(d.copy_value == '69', 'Zero decimals supported')
        d.decimal_slider.Value = 4
        check(d.copy_value == '68.8391' and d.base_label.Text == '82.3892 m²',
              'Slider updates section and base area together')
        d.unit_buttons[1].PerformClick()
        d.decimal_slider.Value = 6
        check(d.copy_value == '0.000069' and d.base_copy_value == '0.000082', 'Square kilometre display conversion')
        d.unit_buttons[2].PerformClick()
        check(d.copy_value == '0.006884' and d.base_copy_value == '0.008239', 'Hectare display conversion')
        d.copy_button.PerformClick()
        check(forms.Clipboard.Instance.Text == '0.006884', 'Copy uses selected area unit')
        check(not d.Visible, 'Section copy closes result after copying')
    try:
        show_auto(dlg, test_copy, 'copy-before')
        base_dialog = q['create_result_dialog']('', '', 69, 82, 16.45,
                                              1, 1, 1, 68.83912345, 82.38923456)
        def test_base_copy(d):
            d.decimal_slider.Value = 4
            d.copy_base_button.PerformClick()
            check(forms.Clipboard.Instance.Text == '82.3892', 'Separate base-plane copy button')
            check(not d.Visible, 'Base-plane copy closes result after copying')
        show_auto(base_dialog, test_base_copy, 'copy-base-before')
        failed_dialog = q['create_result_dialog']('', '', 69, 82, 16.45,
                                                1, 1, 1, 68.83912345, 82.38923456)
        original_copy = ui.copy_text_to_clipboard
        def fail_copy(value):
            raise RuntimeError('Simulated clipboard failure')
        def test_failed_copy(d):
            ui.copy_text_to_clipboard = fail_copy
            try:
                d.copy_button.PerformClick()
                check(d.Visible and 'Clipboard unavailable' in d.status.Text,
                      'Clipboard failure keeps result open with feedback')
            finally:
                ui.copy_text_to_clipboard = original_copy
            d.done_button.PerformClick()
        show_auto(failed_dialog, test_failed_copy, 'copy-error-before')
        run_main([box_id], 'copy-closes-preview', copy_result=True)
    finally:
        if previous is None:
            Clipboard.Clear()
        else:
            Clipboard.SetDataObject(snapshot, True)
    for tagged in (False, True):
        dlg = q['create_invalid_dialog']()
        dlg.tag_checkbox.Checked = tagged
        show_auto(dlg, lambda d: d.continue_button.PerformClick(), 'tag-' + str(tagged))
        check(dlg.choice == ('continue_tag' if tagged else 'continue_no_tag'), 'Tag choice: ' + str(tagged))
    from System import Guid
    missing_id = Guid.NewGuid()
    dlg = q['create_issues_dialog'](doc,
        [(box_id, 'First issue'), (box_id, 'Second issue'),
         (roof_id, 'Another object issue'), (missing_id, 'Object removed')],
        [(open_id, 'Example non-fatal warning')])
    check(len(dlg.issue_buttons) == 4, 'Multiple reasons for one object share one clickable entry')
    def test_issue_selection(d):
        d.issue_buttons[1].PerformClick()
        check({o.Id for o in doc.Objects.GetSelectedObjects(False, False)} == {roof_id},
              'Issue entry selects the exact second object')
        d.issue_buttons[2].PerformClick()
        check('no longer exists' in d.status.Text and
              {o.Id for o in doc.Objects.GetSelectedObjects(False, False)} == {roof_id},
              'Missing object reports feedback and preserves selection')
        capture(d, 'interactive-issues-selected')
        d.AbortButton.PerformClick()
    show_auto(dlg, test_issue_selection, 'interactive-issues', True)
    dlg = q['create_invalid_dialog']()
    show_auto(dlg, lambda d: d.cancel_button.PerformClick(), 'warning-cancel')
    check(dlg.choice == 'cancel', 'Warning cancellation returns cancel')
    check('create_selection_dialog' not in q, 'No initial confirmation dialog exists')
    check(abs(q['area_in_unit'](1000000, 0, Rhino.UnitSystem.Millimeters) - 1) < 1e-12,
          'Square-millimetre document areas converted correctly to square metres')
    check(q['area_in_unit'](1000000, 1, Rhino.UnitSystem.Meters) == 1,
          'One million square metres equals one square kilometre')
    check(q['area_in_unit'](10000, 2, Rhino.UnitSystem.Meters) == 1,
          'Ten thousand square metres equals one hectare')
    calls = run_main([roof_id], 'change-height', change_height=2.5)
    check(abs(calls[1][8] - 60 * scale**2) < max(tol, 1e-6),
          'Command-line height entry recalculates same selection at 2.5 metres')
    check(q['section_height_metres']() == 2.5, 'Changed height remembered for this Rhino session')
    calls = run_main([roof_id], 'remember-height')
    check(abs(calls[0][8] - 60 * scale**2) < max(tol, 1e-6), 'Next invocation uses remembered height')
    check(any(p.draw_count > 0 and len(p.curves) > 0 for p in previews),
          'Section loops actually drawn by the viewport pipeline')
    if selected_before:
        calls = run_main(selected_before, 'current-selection')
        print('CURRENT_SELECTION_RESULT', calls)
    check(not errors, 'All live dialog renderings succeeded')
finally:
    if had_height:
        sc.sticky[height_key] = previous_height
    else:
        sc.sticky.pop(height_key, None)
    ui.AquaDialog.show_for_doc = original_show
    g['show_result_dialog'] = original_result
    g['SectionPreview'] = original_preview
    for timer in timers:
        timer.Stop()
        timer.Dispose()
    for object_id in objects:
        doc.Objects.Delete(object_id, True)
    for definition in definitions:
        doc.InstanceDefinitions.Delete(definition, True, True)
    select(selected_before)
    doc.Views.Redraw()
    print('QUICKAREA_UI_CHECKS', checks)
    print('QUICKAREA_UI_ERRORS', errors)
    import json
    with open(os.path.join(output, 'test-report.json'), 'w', encoding='utf-8') as report:
        json.dump({'checks': checks, 'errors': errors}, report, indent=2)
    print('FIXTURE_CLEANUP', sum(1 for obj in doc.Objects if not obj.IsDeleted) == object_count_before)
    print('SELECTION_RESTORED', set(selected_before) == {o.Id for o in doc.Objects.GetSelectedObjects(False, False)})
