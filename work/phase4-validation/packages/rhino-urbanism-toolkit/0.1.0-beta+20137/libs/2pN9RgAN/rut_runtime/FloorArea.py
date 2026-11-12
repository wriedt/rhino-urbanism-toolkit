#! python 3
# -*- coding: utf-8 -*-
"""RUTFloorArea: document-owned, live selection measurement window."""
import os
import sys
import Rhino
import scriptcontext as sc
import Eto.Forms as forms
import Eto.Drawing as drawing

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
import floor_area as area


class FloorAreaController:
    EVENTS = ('SelectObjects', 'DeselectObjects', 'DeselectAllObjects',
              'AddRhinoObject', 'DeleteRhinoObject', 'UndeleteRhinoObject',
              'ReplaceRhinoObject', 'ModifyObjectAttributes', 'AfterTransformObjects',
              'InstanceDefinitionTableEvent', 'DocumentPropertiesChanged')

    def __init__(self, doc):
        self.doc = doc
        self.key = 'RUT.FloorArea.' + str(doc.RuntimeSerialNumber)
        self.result = None
        self.preview = None
        self.closed = False
        self.dirty = True
        self.subscriptions = []
        self.unit_index = 0
        self.input_ids = []
        self.form = area.panel_dialog('FloorArea', 'Measurement / FloorArea',
                                      '', '', floating=True)
        f = self.form
        height_row = area.ui.content_layout(0)
        self.height = forms.NumericStepper()
        self.height.MinValue = 0.001
        self.height.MaxValue = 1000000
        self.height.DecimalPlaces = 3
        self.height.Increment = 0.1
        self.height.Value = 1.5
        self.height.FormatString = '0.###'
        self.height.Width = 50
        self.height.Height = 28
        self.height.TextColor = area.ui.INK
        self.height.BackgroundColor = area.ui.FIELD
        self.height.Font = drawing.Font('Segoe UI', area.panel_font_size(area.ui.BODY_SIZE))
        self.height_down = area.panel_button('−')
        self.height_up = area.panel_button('+')
        for control in (self.height_down, self.height_up):
            control.Width = 30
        self.height_down.ToolTip = 'Decrease section height by 0.1 m'
        self.height_up.ToolTip = 'Increase section height by 0.1 m'
        self.height.ToolTip = 'Type section height in metres'
        self.height_down.Click += lambda s, e: self.step_height(-0.1)
        self.height_up.Click += lambda s, e: self.step_height(0.1)
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import Thickness, TextAlignment
            from System.Globalization import CultureInfo
            self.height.ControlObject.CultureInfo = CultureInfo.CurrentCulture
            self.height.ControlObject.ShowButtonSpinner = False
            self.height.ControlObject.BorderThickness = Thickness(0)
            self.height.ControlObject.TextAlignment = TextAlignment.Center
        height_value = area.ui.content_layout(0)
        height_value.Spacing = drawing.Size(0, 0)
        height_value.AddRow(self.height, area.panel_label('m', muted=True))
        height_controls = area.ui.content_layout(0)
        height_controls.Spacing = drawing.Size(6, 0)
        height_controls.AddRow(self.height_down, area.ui.InfoPanel(height_value, 2), self.height_up)
        self.height_label = area.panel_label('Section height above local base', muted=True)
        height_row.AddRow(self.height_label, None, height_controls)
        f.body.AddRow(height_row)
        section = area.ui.content_layout(4)
        section.AddRow(area.panel_label('Section area', muted=True))
        self.section_label = area.panel_label('—', area.ui.VALUE_SIZE)
        section.AddRow(self.section_label)
        f.body.AddRow(area.ui.InfoPanel(section, 12))
        precision = area.ui.content_layout(6)
        unit_row = area.ui.content_layout(0)
        self.units = [area.panel_button(unit[1], i == 0) for i, unit in enumerate(area.AREA_UNITS)]
        for i, control in enumerate(self.units):
            control.Width = 48
            control.Click += lambda s, e, index=i: self.choose_unit(index)
        unit_row.AddRow(area.panel_label('Area unit', muted=True), None, *self.units)
        precision.AddRow(unit_row)
        precision_header = area.ui.content_layout(0)
        self.decimal_label = area.panel_label('2', muted=True)
        precision_header.AddRow(area.panel_label('Decimal places', muted=True), None, self.decimal_label)
        precision.AddRow(precision_header)
        self.decimals = forms.Slider()
        self.decimals.MinValue, self.decimals.MaxValue = 0, 6
        self.decimals.TickFrequency = 1
        self.decimals.SnapToTick = True
        self.decimals.Value = 2
        self.decimals.Height = 24
        area.ui.theme_slider(self.decimals)
        precision.AddRow(self.decimals)
        f.body.AddRow(precision)
        metrics = area.ui.content_layout()
        metrics.Spacing = drawing.Size(16, 6)
        self.base_label = area.panel_label('—')
        self.reduction_label = area.panel_label('—')
        metrics.AddRow(area.panel_label('Base plane area', muted=True), None, self.base_label)
        metrics.AddRow(area.panel_label('Reduction from base', muted=True), None, self.reduction_label)
        f.body.AddRow(area.ui.InfoPanel(metrics, 12))
        self.context_label = area.panel_label('Select solids or blocks to measure.', muted=True)
        f.body.AddRow(self.context_label)
        self.issues = forms.TextArea()
        self.issues.ReadOnly = True
        self.issues.Wrap = True
        self.issues.Size = drawing.Size(410, 105)
        self.issues.Font = drawing.Font('Segoe UI', area.panel_font_size(area.ui.BODY_SIZE))
        self.issues.TextColor = area.ui.colour('#a34535', '#f0ab99')
        self.issues.BackgroundColor = area.ui.FIELD
        self.issues.Visible = False
        f.body.AddRow(self.issues)
        self.copy_section = area.panel_button('Copy section area', True)
        self.copy_base = area.panel_button('Copy base plane area')
        self.copy_section.Click += lambda s, e: self.copy(True)
        self.copy_base.Click += lambda s, e: self.copy(False)
        f.finish(area.ui.action_row(self.copy_base, self.copy_section))
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import SizeToContent
            f.ControlObject.SizeToContent = SizeToContent.WidthAndHeight
        self.height.ValueChanged += self.height_changed
        self.decimals.ValueChanged += lambda s, e: self.render()
        f.Closed += self.on_closed
        f.Shown += self.fit_content
        # A Form has no dialog AbortButton; explicitly consume Escape on Windows.
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            f.ControlObject.PreviewKeyDown += self.on_key
        self.timer = forms.UITimer()
        self.timer.Interval = 0.15
        self.timer.Elapsed += self.on_tick

    def on_key(self, sender, event):
        from System.Windows.Input import Key
        if event.Key == Key.Escape:
            event.Handled = True

    def step_height(self, increment):
        self.height.Value = min(self.height.MaxValue, max(self.height.MinValue,
                                round(float(self.height.Value) + increment, 3)))

    def height_changed(self, sender=None, event=None):
        self.height_down.Enabled = self.height.Value > self.height.MinValue
        self.height_up.Enabled = self.height.Value < self.height.MaxValue
        self.mark_dirty()

    def fit_content(self, sender=None, event=None):
        if Rhino.Runtime.HostUtils.RunningOnWindows and self.form.Visible:
            from System.Windows import SizeToContent
            native = self.form.ControlObject
            native.SizeToContent = SizeToContent.WidthAndHeight
            native.InvalidateMeasure()
            native.UpdateLayout()

    def choose_unit(self, index):
        self.unit_index = index
        for i, control in enumerate(self.units):
            area.ui.set_button_selected(control, i == index)
        self.render()

    def mark_dirty(self, sender=None, event=None):
        event_doc = getattr(event, 'Document', self.doc)
        if event_doc is not None and event_doc.RuntimeSerialNumber != self.doc.RuntimeSerialNumber:
            return
        self.dirty = True
        # Immediately invalidate old totals, including during a running edit command.
        self.clear_preview()
        self.section_label.Text = self.base_label.Text = self.reduction_label.Text = '—'
        self.copy_section.Enabled = self.copy_base.Enabled = False

    def clear_preview(self):
        if self.preview:
            self.preview.Enabled = False
            self.preview = None
            self.doc.Views.Redraw()

    def on_tick(self, sender=None, event=None):
        if self.closed or not self.dirty or self.doc.InCommand(True):
            return
        self.refresh()

    def refresh(self):
        self.dirty = False
        self.clear_preview()
        if self.result:
            self.result.dispose()
            self.result = None
        ids = area.selected_ids(self.doc)
        self.input_ids = ids
        self.form.set_status('')
        try:
            if ids:
                self.result = area.measure(self.doc, ids, sections=True, height=float(self.height.Value))
                self.preview = area.SectionPreview(self.doc, self.result.curves if self.result.valid else [])
                self.preview.set_failures(self.result.failures)
                self.preview.Enabled = True
            self.render()
        except Exception as error:
            self.clear_preview()
            if self.result:
                self.result.dispose()
                self.result = None
            self.render()
            self.form.set_status('Measurement failed: ' + str(error))
        self.doc.Views.Redraw()

    def render(self):
        r = self.result
        valid = r is not None and r.valid and not self.dirty
        self.copy_section.Enabled = self.copy_base.Enabled = valid
        self.decimal_label.Text = str(self.decimals.Value)
        self.issues.Visible = bool(r and r.issues)
        self.issues.Text = '\n'.join('{}: {}'.format(area.object_label(self.doc, oid), reason)
                                     for oid, reason in r.issues) if r else ''
        if not valid:
            self.section_label.Text = self.base_label.Text = self.reduction_label.Text = '—'
            self.context_label.Text = ('Cannot calculate totals. Coral outlines mark faulty geometry.'
                                       if r and r.issues else 'Select solids or blocks to measure.')
            self.fit_content()
            return
        self.section_label.Text = area.area_value(self.doc, r.section, self.unit_index, self.decimals.Value)
        self.base_label.Text = area.area_value(self.doc, r.base, self.unit_index, self.decimals.Value)
        reduction = (r.base - r.section) / r.base * 100 if r.base else 0
        self.reduction_label.Text = area.format_display_number(reduction, self.decimals.Value) + '%'
        blocks = [oid for oid in self.input_ids
                  if isinstance(self.doc.Objects.FindId(oid), Rhino.DocObjects.InstanceObject)]
        summary = '{} valid, closed {}'.format(r.solids, 'solid' if r.solids == 1 else 'solids')
        if blocks:
            inputs = 'blocks' if len(blocks) == len(self.input_ids) else 'objects'
            if len(self.input_ids) == 1:
                inputs = inputs[:-1]
            summary += ' in {} selected {}.'.format(len(self.input_ids), inputs)
        else:
            summary += ' selected.'
        self.context_label.Text = summary
        self.fit_content()

    def copy(self, section):
        if self.dirty or not self.result or not self.result.valid:
            return
        value = self.result.section if section else self.result.base
        try:
            area.ui.copy_text_to_clipboard(area.area_value(
                self.doc, value, self.unit_index, self.decimals.Value, include_unit=False))
            self.form.set_status('Copied section area.' if section else 'Copied base plane area.')
        except Exception:
            self.form.set_status('Clipboard unavailable. Try copying again.')
        self.fit_content()

    def on_document_closed(self, sender, event):
        if event.Document.RuntimeSerialNumber == self.doc.RuntimeSerialNumber:
            self.form.Close()

    def show(self):
        try:
            for name in self.EVENTS:
                getattr(Rhino.RhinoDoc, name).__iadd__(self.mark_dirty)
                self.subscriptions.append((name, self.mark_dirty))
            Rhino.RhinoDoc.CloseDocument += self.on_document_closed
            self.subscriptions.append(('CloseDocument', self.on_document_closed))
            sc.sticky[self.key] = self
            self.refresh()
            self.form.show_for_doc(self.doc)
            self.timer.Start()
        except Exception:
            self.on_closed()
            raise

    def on_closed(self, sender=None, event=None):
        if self.closed:
            return
        self.closed = True
        self.timer.Stop()
        self.timer.Elapsed -= self.on_tick
        self.timer.Dispose()
        for name, handler in self.subscriptions:
            getattr(Rhino.RhinoDoc, name).__isub__(handler)
        self.subscriptions.clear()
        self.clear_preview()
        if self.result:
            self.result.dispose()
            self.result = None
        if sc.sticky.get(self.key) is self:
            del sc.sticky[self.key]


def main():
    doc = sc.doc
    key = 'RUT.FloorArea.' + str(doc.RuntimeSerialNumber)
    existing = sc.sticky.get(key)
    if existing and not existing.closed:
        existing.form.BringToFront()
        return existing
    controller = FloorAreaController(doc)
    controller.show()
    return controller


if __name__ == '__main__':
    main()
