"""Rhino 8 integration checks. Run run(__rhino_doc__) through Rhino MCP.

The timer exercises real selection/document events between command turns.
Only test fixtures are removed; selection and camera are preserved. Copy is
captured at the clipboard boundary so the system clipboard is never changed.
"""
import importlib
import json
import math
from pathlib import Path
import Rhino
import scriptcontext as sc
import Eto.Forms as forms
from System import Guid, Array


def run(doc):
    import urbanism_ui as ui
    import floor_area as area
    import FloorArea as floating
    import QuickFloorArea as quick
    for module in (area, floating, quick):
        importlib.reload(module)
    root = Path(__file__).parent / 'work' / 'floor-area-validation'
    root.mkdir(exist_ok=True)
    checks, ids, definitions = [], [], []
    previous_selection = area.selected_ids(doc)
    previous_modified = doc.Modified
    previous_context = sc.doc
    sc.doc = doc
    prefix = 'RUT_AreaTest_' + str(Guid.NewGuid())[:8]
    scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    key = 'RUT.FloorArea.' + str(doc.RuntimeSerialNumber)
    if sc.sticky.get(key):
        sc.sticky[key].form.Close()

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        checks.append(message)

    def box(width=10, depth=8, height=3):
        return Rhino.Geometry.Brep.CreateFromBox(Rhino.Geometry.BoundingBox(
            Rhino.Geometry.Point3d(0, 0, 0),
            Rhino.Geometry.Point3d(width * scale, depth * scale, height * scale)))

    def add(geometry, suffix):
        attrs = Rhino.DocObjects.ObjectAttributes()
        attrs.Name = prefix + suffix
        oid = doc.Objects.AddBrep(geometry, attrs)
        ids.append(oid)
        return oid

    def select(items):
        doc.Objects.UnselectAll()
        for oid in items:
            doc.Objects.Select(oid)
        doc.Views.Redraw()

    def result(items, sections=False):
        return area.measure(doc, items, sections, 1.5)

    def capture(controller, name):
        from System.Windows.Media import VisualTreeHelper, PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap, PngBitmapEncoder, BitmapFrame
        from System.IO import FileStream, FileMode
        native = controller.form.ControlObject.Content
        native.UpdateLayout()
        dpi = VisualTreeHelper.GetDpi(native)
        bitmap = RenderTargetBitmap(int(math.ceil(native.ActualWidth * dpi.DpiScaleX)),
            int(math.ceil(native.ActualHeight * dpi.DpiScaleY)),
            dpi.PixelsPerInchX, dpi.PixelsPerInchY, PixelFormats.Pbgra32)
        bitmap.Render(native)
        encoder = PngBitmapEncoder()
        encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream = FileStream(str(root / (name + '.png')), FileMode.Create)
        try:
            encoder.Save(stream)
        finally:
            stream.Dispose()

    controller = None
    timer = forms.UITimer()
    state = {'step': 0, 'error': None, 'closed': False}

    def cleanup():
        if state['closed']:
            return
        state['closed'] = True
        timer.Stop()
        if state.get('handler'):
            timer.Elapsed -= state['handler']
        timer.Dispose()
        if controller and not controller.closed:
            controller.form.Close()
        for oid in reversed(ids):
            doc.Objects.Delete(oid, True)
        for index in reversed(definitions):
            doc.InstanceDefinitions.Delete(index, True, True)
        select(previous_selection)
        doc.Modified = previous_modified
        sc.doc = previous_context
        (root / 'results.json').write_text(json.dumps(
            {'checks': checks, 'error': state['error'],
             'clipboard': 'Copy boundary captured; system clipboard untouched'}, indent=2), encoding='utf-8')
        sc.sticky.pop('RUT.FloorArea.Validation', None)

    try:
        good = add(box(), '_good')
        short = add(box(height=0.5), '_short')
        open_geometry = box().Faces[0].DuplicateFace(False)
        opened = add(open_geometry, '_open')
        ball = Rhino.Geometry.Sphere(Rhino.Geometry.Point3d.Origin, 4 * scale).ToBrep()
        sphere = add(ball, '_no_base')
        for oid, expected in ((good, 80), (short, 80)):
            r = result([oid])
            check(r.valid and abs(area.area_in_unit(r.base, 0) - expected) < 1e-6,
                  'Base-only measurement independent of section height: ' + str(oid))
            r.dispose()
        r = result([good, opened])
        check(not r.valid and len(r.failures) == 1 and r.issues[0][0] == opened,
              'Open input invalidates selection and preserves exact failure identity')
        r.dispose()
        r = result([sphere])
        check(not r.valid and r.failures, 'Solid without horizontal base fails with preview geometry')
        r.dispose()
        # Nested nonuniformly scaled block: 80 m² base becomes 480 m².
        attrs = Rhino.DocObjects.ObjectAttributes()
        inner = doc.InstanceDefinitions.Add(prefix + '_inner', '', Rhino.Geometry.Point3d.Origin,
                                            [box()], [attrs])
        definitions.append(inner)
        transform = Rhino.Geometry.Transform.Scale(Rhino.Geometry.Plane.WorldXY, 2, 3, 1)
        child = Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[inner].Id, transform)
        outer = doc.InstanceDefinitions.Add(prefix + '_outer', '', Rhino.Geometry.Point3d.Origin,
                                            [child], [attrs])
        definitions.append(outer)
        placed = Rhino.Geometry.Transform.Translation(30 * scale, 0, 0)
        block = doc.Objects.AddInstanceObject(outer, placed)
        ids.append(block)
        r = result([block], True)
        check(r.valid and abs(area.area_in_unit(r.base, 0) - 480) < 1e-6,
              'Nested nonuniform block transforms measure world-space area')
        check(all(curve.GetBoundingBox(True).Min.X >= 30 * scale - 1e-5 for curve in r.curves),
              'Nested block preview curves use world coordinates')
        r.dispose()
        # A headless millimetre document checks conversion without changing user units.
        mm = Rhino.RhinoDoc.CreateHeadless(None)
        try:
            mm.ModelUnitSystem = Rhino.UnitSystem.Millimeters
            b = Rhino.Geometry.Brep.CreateFromBox(Rhino.Geometry.BoundingBox(
                Rhino.Geometry.Point3d.Origin, Rhino.Geometry.Point3d(10000, 8000, 3000)))
            oid = mm.Objects.AddBrep(b)
            r = area.measure(mm, [oid], True, 1.5)
            check(r.valid and area.area_value(mm, r.base) == '80.00 m²' and
                  area.area_value(mm, r.section) == '80.00 m²', 'Millimetre base/section unit conversion')
            r.dispose()
        finally:
            mm.Dispose()
        copied = []
        select([good, opened])
        previews = []
        original_preview = area.SectionPreview
        def preview(*args):
            item = original_preview(*args)
            previews.append(item)
            return item
        area.SectionPreview = preview
        def inspect():
            check(previews[-1].Enabled and set(area.selected_ids(doc)) == {good, opened},
                  'Quick warning keeps overlay active and input selection unchanged')
        try:
            check(not quick.run(doc, [good, opened], wait=inspect, copy=copied.append),
                  'Quick failure returns without a total')
            check(not previews[-1].Enabled and not copied, 'Acknowledgement clears coral and never copies partial area')
            try:
                quick.run(doc, [opened], wait=lambda: (_ for _ in ()).throw(RuntimeError('test cancellation')),
                          copy=copied.append)
            except RuntimeError:
                pass
            check(not previews[-1].Enabled, 'Exceptional warning exit also clears coral')
        finally:
            area.SectionPreview = original_preview
        quick.run(doc, [short], copy=copied.append)
        check(copied == ['80.00 m²'], 'Quick success copies base with unit and two decimals')
        select([good])
        controller = floating.FloorAreaController(doc)
        controller.show()
    except Exception:
        import traceback
        state['error'] = traceback.format_exc()
        cleanup()
        raise

    def step(sender, event):
        if state['closed']:
            return
        try:
            n = state['step']
            if n == 0:
                check(controller.form.Visible and controller.result.valid and controller.base_label.Text == '80.00 m²',
                      'Floating tool initially measures selection')
                capture(controller, 'valid')
                from System.Windows import RoutedEventArgs
                from System.Windows.Controls import Button
                controller.height_down.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))
                check(abs(float(controller.height.Value) - 1.4) < 1e-9,
                      'Native minus button decreases section height by 0.1 m')
                controller.height_up.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))
                check(abs(float(controller.height.Value) - 1.5) < 1e-9,
                      'Native plus button increases section height by 0.1 m')
                from System.Globalization import CultureInfo
                separator = CultureInfo.CurrentCulture.NumberFormat.NumberDecimalSeparator
                controller.height.ControlObject.Text = '1' + separator + '7'
                controller.height.ControlObject.CommitInput()
                check(abs(float(controller.height.Value) - 1.7) < 1e-9,
                      'Height value remains directly editable with native numeric parsing')
                controller.height.Value = 1.5
                controller.refresh()
                check(controller.context_label.Text == '1 valid, closed solid selected.' and
                      controller.height_label.Font.Size == controller.context_label.Font.Size,
                      'Selection summary describes valid solids and height label uses normal body size')
                original_copy = area.ui.copy_text_to_clipboard
                copy_values = []
                try:
                    area.ui.copy_text_to_clipboard = copy_values.append
                    controller.copy_base.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))
                    check(copy_values == ['80.00'] and controller.form.Visible,
                          'Native copy button supplies numeric value and keeps window open')
                    def unavailable(value):
                        raise RuntimeError('Simulated unavailable clipboard')
                    area.ui.copy_text_to_clipboard = unavailable
                    controller.copy_base.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))
                    check(controller.form.Visible and 'unavailable' in controller.form.status.Text.lower(),
                          'Copy failure keeps window open and shows feedback')
                finally:
                    area.ui.copy_text_to_clipboard = original_copy
                from System.Windows import PresentationSource
                from System.Windows.Input import KeyEventArgs, Keyboard, Key
                from System import Environment
                native = controller.form.ControlObject
                args = KeyEventArgs(Keyboard.PrimaryDevice, PresentationSource.FromVisual(native),
                                    Environment.TickCount, Key.Escape)
                args.RoutedEvent = Keyboard.PreviewKeyDownEvent
                native.RaiseEvent(args)
                check(args.Handled and controller.form.Visible, 'Native Escape routing keeps floating tool open')
                controller.choose_unit(2)
                controller.decimals.Value = 4
                check(controller.base_label.Text == '0.0080 ha', 'Floating precision and units format full result')
                controller.choose_unit(0)
                controller.decimals.Value = 2
                select([good, opened])
            elif n == 1:
                check(not controller.result.valid and not controller.copy_base.Enabled and
                      controller.base_label.Text == '—' and controller.section_label.Text == '—',
                      'Selection event automatically withholds all totals for mixed faulty inputs')
                check(controller.preview.Enabled and controller.preview.failed_breps,
                      'Floating failure coral stays active')
                from System.Windows import Point
                native = controller.form.ControlObject
                button = controller.copy_base.ControlObject
                bottom = button.TranslatePoint(Point(0, button.ActualHeight), native.Content).Y
                check(bottom <= native.Content.ActualHeight,
                      'Issues expand window enough to keep Copy buttons inside its bounds')
                capture(controller, 'issues')
                select([good])
                doc.Objects.Replace(good, box(width=20))
            elif n == 2:
                check(controller.result.valid and controller.base_label.Text == '160.00 m²',
                      'Geometry replacement automatically recalculates selected solid')
                controller.height.Value = 10
            elif n == 3:
                check(not controller.result.valid and controller.base_label.Text == '—',
                      'Height edits automatically invalidate impossible sections and hide base total too')
                controller.height.Value = 1.5
                select([])
            elif n == 4:
                check(controller.result is None and controller.base_label.Text == '—' and not controller.copy_base.Enabled,
                      'Deselect-all clears results and copy actions')
                select([block])
            elif n == 5:
                check(controller.result.valid and controller.base_label.Text == '480.00 m²',
                      'Floating selection update measures nested block')
                check(doc.InstanceDefinitions.ModifyGeometry(inner, [box(width=20)],
                                                             [Rhino.DocObjects.ObjectAttributes()]),
                      'Test block definition edit succeeded')
            elif n == 6:
                check(controller.result.valid and controller.base_label.Text == '960.00 m²',
                      'Block-definition event automatically recalculates selected nested instance')
                preview = controller.preview
                from System.Windows import RoutedEventArgs
                from System.Windows.Controls import Button
                controller.form.close_button.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))
                check(controller.closed and not preview.Enabled and not controller.subscriptions and key not in sc.sticky,
                      'Native X closes window, clears overlay and removes event subscriptions')
                fresh = floating.FloorAreaController(doc)
                check(float(fresh.height.Value) == 1.5 and fresh.unit_index == 0 and fresh.decimals.Value == 2,
                      'Reopening starts with independent default settings')
                fresh.form.Close()
                fresh.on_closed()
                cleanup()
                cleanup()  # A late/error-path cleanup must be harmless.
                return
            state['step'] += 1
        except Exception:
            import traceback
            state['error'] = traceback.format_exc()
            cleanup()

    timer.Interval = 0.6
    state['handler'] = step
    timer.Elapsed += step
    sc.sticky['RUT.FloorArea.Validation'] = (timer, controller, state)
    timer.Start()
    return 'Live checks running; results in ' + str(root / 'results.json')
