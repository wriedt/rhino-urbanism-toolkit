"""Focused aqua dialogs shared by the six block commands."""
import re
import Rhino
import Eto.Forms as forms
import Eto.Drawing as drawing
from System import Array, Object, Guid
import urbanism_ui as ui
import block_versions as naming
import block_actions as actions

def table(columns, height=170):
    grid = forms.GridView()
    grid.AllowMultipleSelection = True
    grid.ShowHeader = True
    grid.Size = drawing.Size(sum(width for heading, width in columns) + 20, height)
    grid.BackgroundColor = ui.FIELD
    grid.TextColor = ui.INK
    grid.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
    for index, (heading, width) in enumerate(columns):
        column = forms.GridColumn()
        column.HeaderText = heading
        column.DataCell = forms.TextBoxCell(index)
        column.Editable = False
        column.Width = width
        column.Sortable = True
        column.Resizable = True
        grid.Columns.Add(column)
    ui.theme_scrollbars(grid)
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        import clr
        from System.Windows.Markup import XamlReader
        from System.Windows.Controls import DataGridRow, DataGridCell
        from System.Windows.Controls.Primitives import DataGridColumnHeader
        colours = dict(field='#263b43' if ui.DARK else '#fcfefe',
            ink='#e9f5f6' if ui.DARK else '#263f4b',
            aqua='#294944' if ui.DARK else '#e2f1ed',
            accent='#b1e4df' if ui.DARK else '#246e7b',
            on='#123d46' if ui.DARK else '#f5ffff')
        for native_type, template in [(DataGridRow, '''<Style TargetType="DataGridRow">
 <Setter Property="Background" Value="{field}"/><Setter Property="Foreground" Value="{ink}"/>
 <Style.Triggers><Trigger Property="IsSelected" Value="True">
 <Setter Property="Background" Value="{accent}"/><Setter Property="Foreground" Value="{on}"/>
 </Trigger></Style.Triggers></Style>'''), (DataGridCell, '''<Style TargetType="DataGridCell">
 <Setter Property="Background" Value="Transparent"/><Setter Property="Foreground" Value="{ink}"/>
 <Setter Property="Padding" Value="4"/>
 <Setter Property="ClipToBounds" Value="True"/>
 <Style.Triggers><Trigger Property="IsSelected" Value="True">
 <Setter Property="Background" Value="{accent}"/><Setter Property="Foreground" Value="{on}"/>
 </Trigger></Style.Triggers></Style>'''), (DataGridColumnHeader, '''<Style TargetType="DataGridColumnHeader">
 <Setter Property="Background" Value="{aqua}"/><Setter Property="Foreground" Value="{ink}"/>
 <Setter Property="Padding" Value="4,8"/>
 </Style>''')]:
            source = template.replace('<Style ', '<Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" ', 1)
            grid.ControlObject.Resources[clr.GetClrType(native_type)] = XamlReader.Parse(source.format(**colours))
        text_style = XamlReader.Parse('''<Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" TargetType="TextBlock">
 <Setter Property="TextTrimming" Value="CharacterEllipsis" />
 <Setter Property="TextWrapping" Value="NoWrap" />
 <Setter Property="Margin" Value="0,0,6,0" />
 <Setter Property="ToolTip" Value="{Binding Text, RelativeSource={RelativeSource Self}}" />
</Style>''')
        for column in grid.ControlObject.Columns:
            column.ElementStyle = text_style
    grid.Tag = dict(rows=[], column=None, descending=False)
    def header_click(sender, event):
        column = event.Column
        index = column if isinstance(column, int) else list(grid.Columns).index(column)
        sort_table(grid, index)
    grid.ColumnHeaderClick += header_click
    return grid


def set_rows(grid, rows, keys=None):
    rows = [list(row) for row in rows]
    if keys is not None:
        rows = [row + [key] for row, key in zip(rows, keys)]
    grid.Tag['rows'] = rows
    sort_table(grid, grid.Tag['column'], toggle=False)


def sort_table(grid, column, toggle=True):
    state = grid.Tag
    if toggle:
        state['descending'] = not state['descending'] if state['column'] == column else False
    state['column'] = column
    selected = list(grid.SelectedItem) if grid.SelectedItem is not None else None
    rows = list(state['rows'])
    if column is not None:
        def key(row):
            return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                         for part in re.split(r'([0-9]+)', str(row[column])))
        rows.sort(key=key, reverse=state['descending'])
    grid.DataStore = Array[Object]([Array[Object](row) for row in rows])
    if selected in rows:
        grid.SelectedRow = rows.index(selected)
    for i, item in enumerate(grid.Columns):
        item.HeaderText = item.HeaderText.rstrip(' ↑↓')
        if i == column:
            item.HeaderText += ' ↓' if state['descending'] else ' ↑'


def selected_record(grid, records):
    item = grid.SelectedItem
    if item is None:
        return None
    key = str(item[grid.Columns.Count])
    return next((record for record in records if record['id'] == key), None)


def field(text='', width=440):
    control = forms.TextBox()
    control.Text = text
    control.Width = width
    control.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
    control.BackgroundColor, control.TextColor = ui.FIELD, ui.INK
    return control


def name_preview(before, after):
    # Keep both version endings visible on a single line; tooltip/review retain full names.
    def short(name):
        return name if len(name) <= 27 else name[:12] + '…' + name[-14:]
    return short(before) + ' → ' + short(after)


def version_choices(name, names):
    """Preferred detection first, then explicit alternatives marked in their context."""
    choices = naming.suggestions(name, names)
    for match in re.finditer(r'[A-Za-z]+[0-9]+|[0-9]+|[A-Z]+|[a-z]+', name):
        try:
            spec = naming.describe(name, match.group(), match.start())
        except ValueError:
            continue
        if not any((s['prefix'], s['token']) == (spec['prefix'], spec['token']) for s in choices):
            choices.append(spec)
        # A combined A01 token can also mean family A, version 01.
        digits = re.search(r'[0-9]+$', match.group())
        if digits:
            spec = naming.describe(name, digits.group(), match.start() + digits.start())
            if not any((s['prefix'], s['token']) == (spec['prefix'], spec['token']) for s in choices):
                choices.append(spec)
    return choices


def theme_dropdown(control):
    """Keep collapsed/later-revealed native choices in the dialog's aqua theme."""
    if not Rhino.Runtime.HostUtils.RunningOnWindows:
        return
    from System.Windows.Markup import XamlReader
    native = control.ControlObject
    source = '''<ControlTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="ComboBox">
 <Grid>
  <Border Background="FIELD" BorderBrush="LINE" BorderThickness="1" CornerRadius="3" />
  <ToggleButton Focusable="False" IsChecked="{Binding IsDropDownOpen, Mode=TwoWay, RelativeSource={RelativeSource TemplatedParent}}">
   <ToggleButton.Template><ControlTemplate TargetType="ToggleButton">
    <Border Background="Transparent"><Path Data="M 0 0 L 4 4 L 8 0" Stroke="INK" StrokeThickness="1.2"
     HorizontalAlignment="Right" VerticalAlignment="Center" Margin="0,0,10,0" /></Border>
   </ControlTemplate></ToggleButton.Template>
  </ToggleButton>
  <TextBlock Text="{Binding SelectedItem.Text, RelativeSource={RelativeSource TemplatedParent}}" Foreground="INK"
   IsHitTestVisible="False" Margin="8,4,28,4" VerticalAlignment="Center" TextTrimming="CharacterEllipsis" />
  <Popup Name="PART_Popup" IsOpen="{TemplateBinding IsDropDownOpen}" Placement="Bottom" AllowsTransparency="True" Focusable="False">
   <Border Background="FIELD" BorderBrush="LINE" BorderThickness="1" Padding="2" MinWidth="{Binding ActualWidth, RelativeSource={RelativeSource TemplatedParent}}">
    <ScrollViewer MaxHeight="250" CanContentScroll="True"><ItemsPresenter /></ScrollViewer>
   </Border>
  </Popup>
 </Grid>
</ControlTemplate>'''
    for name, value in [('FIELD', '#263b43' if ui.DARK else '#fcfefe'),
                        ('LINE', '#49616b' if ui.DARK else '#c6d8da'),
                        ('INK', '#e9f5f6' if ui.DARK else '#263f4b')]:
        source = source.replace(name, value)
    native.Template = XamlReader.Parse(source)
    ink = '#e9f5f6' if ui.DARK else '#263f4b'
    native.ItemTemplate = XamlReader.Parse('''<DataTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">
 <TextBlock Text="{Binding Text}" Foreground="''' + ink + '''" Padding="6,4" />
</DataTemplate>''')


class BlockDialog(ui.AquaDialog):
    def __init__(self, title, category, heading, description):
        super().__init__(title, category, heading, description)
        self.MinimumSize = drawing.Size(380, 0)
        self.Resizable = True
        self._table_metrics = []
        self.body.Padding = drawing.Padding(16)
        self.body.Spacing = drawing.Size(8, 8)
        # The command name belongs in the draggable header, not in a second title row.
        for child in self.header.Children:
            if isinstance(child, forms.Label):
                child.Text = 'RUT | ' + heading
                child.Font = drawing.Font('Segoe UI', 12)
        for child in self.body.Children:
            if isinstance(child, forms.Label) and child.Text == heading:
                child.Visible = False
        self.AbortButton = self.close_button
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            self.ControlObject.KeyDown += self.cancel_key
            self.ControlObject.PreviewKeyDown += self.primary_key
            from System.Windows import Thickness, CornerRadius
            from System.Windows.Shell import WindowChrome
            chrome = WindowChrome()
            chrome.CaptionHeight = 0
            chrome.ResizeBorderThickness = Thickness(6)
            chrome.CornerRadius = CornerRadius(12)
            chrome.GlassFrameThickness = Thickness(0)
            chrome.UseAeroCaptionButtons = False
            WindowChrome.SetWindowChrome(self.ControlObject, chrome)
            self.ControlObject.SizeChanged += self.resize_tables
        self.Shown += lambda s, e: self.fit_content()

    def cancel_key(self, sender, event):
        from System.Windows.Input import Key
        if event.Key == Key.Escape:
            event.Handled = True
            self.Close(False)

    def primary_key(self, sender, event):
        from System.Windows import RoutedEventArgs
        from System.Windows.Input import Key, Keyboard
        from System.Windows.Controls import Button, ComboBox
        from System.Windows.Controls.Primitives import TextBoxBase
        from System.Windows.Media import VisualTreeHelper
        if event.Key not in (Key.Return, Key.Space) or int(Keyboard.Modifiers) != 0:
            return
        node = Keyboard.FocusedElement
        while node is not None:
            if event.Key == Key.Space and isinstance(node, TextBoxBase):
                return
            if isinstance(node, ComboBox) and node.IsDropDownOpen:
                return
            try:
                node = VisualTreeHelper.GetParent(node)
            except Exception:
                break
        event.Handled = True
        primary = self.DefaultButton
        if not event.IsRepeat and primary is not None and primary.Enabled:
            primary.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))

    def fit_content(self):
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import SizeToContent
            self.ControlObject.SizeToContent = SizeToContent.WidthAndHeight
            self.ControlObject.InvalidateMeasure()
            self.ControlObject.UpdateLayout()
            native = self.ControlObject
            def collect(control):
                if isinstance(control, forms.GridView):
                    yield control
                if isinstance(control, forms.Container):
                    for child in control.Children:
                        yield from collect(child)
            self._table_metrics = [(grid, native.ActualWidth-grid.Width, native.ActualHeight-grid.Height)
                                   for grid in collect(self.body) if grid.ControlObject.IsVisible]

    def resize_tables(self, sender, event):
        from System.Windows import SizeToContent
        native = self.ControlObject
        if native.SizeToContent != SizeToContent.Manual:
            return
        for grid, horizontal, vertical in self._table_metrics:
            grid.Width = max(300, round(native.ActualWidth-horizontal))
            grid.Height = max(100, round(native.ActualHeight-vertical))

    def toggle_panel(self, panel, visible):
        panel.Visible = visible
        self.fit_content()

    def detail_button(self, text, panel):
        button = ui.button(text)
        button.ToolTip = 'Show or hide ' + text.lower()
        def toggle(sender, event):
            self.toggle_panel(panel, not panel.Visible)
            ui.set_button_selected(button, panel.Visible)
        button.Click += toggle
        return button

    def finish(self, actions, status=''):
        self.body.AddRow(actions)
        self.status.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
        self.status.TextColor = ui.colour('#a34535', '#f0ab99')
        self.status.Width = 440
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import TextWrapping
            self.status.ControlObject.TextWrapping = TextWrapping.Wrap
        self.error_panel = ui.InfoPanel(self.status)
        self.error_panel.Visible = False
        self.body.AddRow(self.error_panel)
        self.set_status(status)
        # Compact controls only in these dialogs; other toolkit tools keep their sizing.
        def compact(control):
            if isinstance(control, forms.Button):
                control.Height = 32
                if Rhino.Runtime.HostUtils.RunningOnWindows:
                    from System.Windows import Thickness
                    control.ControlObject.Padding = (Thickness(0) if control.Text == '×'
                                                     else Thickness(12, 3, 12, 3))
            if isinstance(control, forms.DropDown):
                theme_dropdown(control)
            if isinstance(control, forms.Container):
                for child in control.Children:
                    compact(child)
        compact(self.body)

    def set_status(self, text):
        self.status.Text = '⚠ ' + text if text else ''
        self.status.Visible = bool(text)
        if hasattr(self, 'error_panel'):
            changed = self.error_panel.Visible != bool(text)
            self.error_panel.Visible = bool(text)
            if changed and Rhino.Runtime.HostUtils.RunningOnWindows and self.ControlObject.IsLoaded:
                self.fit_content()

    def Close(self, result=False):
        # Python subclasses hide Eto's generic Close(bool) overload.
        self.Result = result
        super().Close()


def message(doc, heading, text):
    dialog = BlockDialog(heading, 'Blocks', heading, text)
    dialog.DefaultButton = dialog.close_button
    dialog.finish(ui.action_row())
    dialog.show_for_doc(doc)


def field_row(label, control):
    row = forms.DynamicLayout()
    row.Spacing = drawing.Size(12, 0)
    row.BackgroundColor = drawing.Colors.Transparent
    caption = ui.label(label)
    caption.Width = 115
    caption.VerticalAlignment = forms.VerticalAlignment.Center
    control.Width = 315
    row.AddRow(caption, control)
    return row


class FamilyDialog(BlockDialog):
    """Interpretation, scoped review and Apply in a single task dialog."""
    def __init__(self, doc, source, operation, ids=()):
        title = {'create': 'Create block version', 'rename': 'Rename block family',
                 'consolidate': 'Consolidate block versions'}[operation]
        super().__init__(title, 'Blocks', title, '')
        self.doc, self.source, self.operation, self.ids = doc, source, operation, ids
        self.definitions = actions.read_definitions(doc)
        self.result_plan = None
        self.loading = True
        names = [d['name'] for d in self.definitions]
        self.options = naming.suggestions(source.Name, names)
        self.original_base = naming.strip_duplicates(source.Name, names)[0]
        self.base = self.original_base
        self.starting_versioning = operation == 'create' and not self.options
        self.example = field(source.Name + '_v01')
        self.naming_panel = ui.content_layout(6)
        self.starting_panel = ui.content_layout(6)
        if operation == 'create':
            self.starting_panel.AddRow(ui.label('Starting name'))
            self.starting_panel.AddRow(self.example)
            self.starting_panel.Visible = self.starting_versioning
            self.body.AddRow(self.starting_panel)
        self.choice = forms.DropDown()
        self.choice.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
        self.choice.BackgroundColor, self.choice.TextColor = ui.FIELD, ui.INK
        self.choice.Width = 440
        self.choice.ToolTip = 'Brackets mark the version. Choose No version if numbers are dimensions or product codes.'
        self.naming_panel.AddRow(ui.label('Version part'))
        self.naming_panel.AddRow(self.choice)
        self.rebuild_choices()
        spec = self.options[0] if self.options else dict(prefix=self.base, suffix='')
        self.new_family = field(re.sub(r'[_ -]+$', '', spec['prefix']))
        self.new_suffix = field(spec['suffix'])
        self.separator = forms.DropDown()
        self.separator.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
        self.separator.BackgroundColor, self.separator.TextColor = ui.FIELD, ui.INK
        for text in ['None', 'Space', 'Underscore', 'Hyphen', 'Custom']:
            self.separator.Items.Add(text)
        self.separator_text = field('', 95)
        self.separator_text.ToolTip = 'Exact characters between family and version. Blank means none.'
        self.set_separator(spec['prefix'])
        if operation == 'rename':
            self.body.AddRow(field_row('New family name', self.new_family))
            separator_row = ui.content_layout(0)
            self.separator.Width = 160
            separator_row.AddRow(ui.label('Separator'), self.separator, self.separator_text, None)
            self.body.AddRow(separator_row)
            if spec['suffix']:
                self.body.AddRow(field_row('Family ending', self.new_suffix))
        self.lowest = ui.checkbox('Start at lowest existing version')
        self.lowest.ToolTip = 'Unchecked: start at 1 (or A for alphabetic versions).'
        if operation == 'consolidate':
            self.body.AddRow(self.lowest)
        self.summary = ui.label('', ui.CAPTION_SIZE, True)
        self.preview = ui.label('')
        self.preview.Width = 440
        self.body.AddRow(self.preview)
        self.body.AddRow(self.summary)
        self.naming_panel.Visible = operation == 'consolidate' and not self.options
        self.adjust_button = self.detail_button('Adjust naming', self.naming_panel)
        self.body.AddRow(self.naming_panel)
        self.grid = table([('Current name', 210), ('Proposed name', 210)], 140)
        self.grid.AllowMultipleSelection = False
        self.review_panel = ui.InfoPanel(self.grid)
        self.review_panel.Visible = False
        self.review_button = self.detail_button('Full review', self.review_panel)
        self.body.AddRow(self.review_panel)
        self.apply_button = ui.button({'create': 'Create version', 'rename': 'Rename family',
                                       'consolidate': 'Consolidate versions'}[operation], True)
        self.apply_button.Click += self.apply
        self.DefaultButton = self.apply_button
        self.finish(ui.action_row(self.review_button, self.adjust_button, self.apply_button))
        self.choice.SelectedIndexChanged += self.choose
        self.example.TextChanged += self.starting_name_changed
        self.new_family.TextChanged += self.refresh
        self.new_suffix.TextChanged += self.refresh
        self.separator.SelectedIndexChanged += self.separator_changed
        self.separator_text.TextChanged += self.refresh
        self.lowest.CheckedChanged += self.refresh
        self.loading = False
        self.refresh()

    def rebuild_choices(self, selected=None):
        names = [d['name'] for d in self.definitions]
        records = [dict(origin='original', spec=s) for s in version_choices(self.original_base, names)]
        records.append(dict(origin='none', spec=None))
        if self.starting_versioning:
            records.extend(dict(origin='starting', spec=s) for s in version_choices(self.example.Text, names))
        self.version_records = records
        self.choice.Items.Clear()
        index = next((i for i, r in enumerate(records) if r['origin'] == 'none'), 0)
        if not self.starting_versioning and self.options:
            index = 0
        for i, record in enumerate(records):
            spec = record['spec']
            text = (spec['prefix'] + '[' + spec['token'] + ']' + spec['suffix']) if spec else 'No version'
            self.choice.Items.Add(text)
            if selected and spec and record['origin'] == selected['origin']:
                old = selected['spec']
                if old and (spec['prefix'], spec['token'], spec['suffix']) == (old['prefix'], old['token'], old['suffix']):
                    index = i
        self.choice.SelectedIndex = index

    def starting_name_changed(self, sender=None, event=None):
        if self.loading:
            return
        selected = self.version_records[self.choice.SelectedIndex]
        self.loading = True
        self.rebuild_choices(selected)
        self.loading = False
        self.interpretation_changed()

    def set_separator(self, prefix):
        match = re.search(r'[_ -]+$', prefix)
        text = match.group() if match else ''
        choices = ['', ' ', '_', '-']
        self.separator.SelectedIndex = choices.index(text) if text in choices else 4
        self.separator_text.Text = text
        self.separator_text.Visible = self.separator.SelectedIndex == 4

    def separator_changed(self, sender=None, event=None):
        self.separator_text.Visible = self.separator.SelectedIndex == 4
        self.refresh()

    def separator_value(self):
        index = self.separator.SelectedIndex
        return ['', ' ', '_', '-'][index] if 0 <= index < 4 else self.separator_text.Text

    def choose(self, sender=None, event=None):
        if self.loading:
            return
        selected = self.version_records[self.choice.SelectedIndex]
        self.loading = True
        starting = self.operation == 'create' and selected['origin'] != 'original'
        if starting != self.starting_versioning:
            self.starting_versioning = starting
            self.rebuild_choices(selected)
        if self.operation == 'create':
            self.toggle_panel(self.starting_panel, starting)
        self.loading = False
        self.interpretation_changed()

    def interpreted_spec(self):
        record = self.version_records[self.choice.SelectedIndex]
        if record['spec']:
            return record['spec']
        if self.operation == 'rename':
            return dict(kind='plain', prefix=self.original_base, suffix='', marker='', width=0)
        if self.operation == 'create':
            proposals = naming.suggestions(self.example.Text, [self.example.Text])
            if proposals:
                return proposals[0]
            raise ValueError('Add a version to the starting name, then select its version part.')
        raise ValueError('Choose the version part before consolidating this family.')

    def interpretation_changed(self, sender=None, event=None):
        if self.loading:
            return
        self.loading = True
        try:
            spec = self.interpreted_spec()
            self.new_family.Text = re.sub(r'[_ -]+$', '', spec['prefix'])
            self.set_separator(spec['prefix'])
            self.new_suffix.Text = spec['suffix']
        except ValueError:
            pass
        finally:
            self.loading = False
        self.refresh()

    def build(self):
        spec = self.interpreted_spec()
        self.spec = spec
        if self.operation == 'create':
            baseline = self.example.Text if self.starting_versioning else None
            return actions.version_plan(self.doc, self.ids, spec, baseline=baseline)
        if self.operation == 'rename':
            if not self.new_family.Text.strip():
                raise ValueError('Enter the new family name.')
            prefix = self.new_family.Text.strip() + (self.separator_value() if spec['kind'] != 'plain' else '')
            return naming.rename_plan(self.definitions, spec, prefix, self.new_suffix.Text)
        return naming.consolidation_plan(self.definitions, spec, bool(self.lowest.Checked))

    def refresh(self, sender=None, event=None):
        if self.loading:
            return
        self.result_plan = None
        try:
            plan = self.build()
            if self.operation == 'create':
                rows = [(r['old'], r['new']) for r in plan['renames']]
                rows.append((plan['original_name'] + ' (selected copies)', plan['new_name']))
                self.summary.Text = ('Starting name changes for all original copies.' if plan['renames'] else '')
                before, after = plan['original_name'], plan['new_name']
            else:
                changes = {r['id']: r['new'] for r in plan['renames']}
                rows = [(d['name'], changes.get(d['id'], d['name'])) for d in plan['members']]
                self.summary.Text = '{} family definitions · {} names change'.format(
                    len(plan['members']), len(plan['renames']))
                example = next((row for row in rows if row[0] == self.source.Name), rows[0])
                before, after = example
            self.preview.Text = name_preview(before, after)
            self.summary.Visible = bool(self.summary.Text)
            self.preview.ToolTip = before + ' → ' + after
            self.separator.Enabled = self.spec['kind'] != 'plain'
            set_rows(self.grid, rows)
            self.result_plan = plan
            self.apply_button.Enabled = bool(plan['renames']) or self.operation == 'create'
            self.set_status('')
        except Exception as error:
            self.apply_button.Enabled = False
            self.summary.Text = ''
            self.summary.Visible = False
            self.preview.Text = ''
            set_rows(self.grid, [])
            self.set_status(str(error))

    def apply(self, sender=None, event=None):
        try:
            plan = self.result_plan
            if plan is None:
                raise ValueError('Correct the naming interpretation before applying.')
            if self.operation == 'create':
                actions.apply_versions(self.doc, [plan])
            else:
                actions.apply_names(self.doc, plan)
            self.result_plan = plan
            self.Close(True)
        except Exception as error:
            self.set_status(str(error))


def pick_instances(doc, prompt, multiple=False):
    picker = Rhino.Input.Custom.GetObject()
    picker.SetCommandPrompt(prompt)
    picker.GeometryFilter = Rhino.DocObjects.ObjectType.InstanceReference
    picker.SubObjectSelect = picker.GroupSelect = False
    try:
        if multiple:
            picker.GetMultiple(1, 0)
        else:
            picker.Get()
        if picker.CommandResult() != Rhino.Commands.Result.Success:
            return []
        ids = [picker.Object(i).ObjectId for i in range(picker.ObjectCount)]
        if any(not actions.editable_instance(doc, doc.Objects.FindId(i)) for i in ids):
            raise ValueError('Select visible, unlocked, local top-level block instances.')
        return ids
    finally:
        picker.Dispose()


def run_family(doc, operation):
    try:
        ids = pick_instances(doc, 'Select block copies' if operation == 'create' else 'Select a block in the family',
                             multiple=operation == 'create')
        if not ids:
            return
        source = doc.Objects.FindId(ids[0]).InstanceDefinition
        if any(doc.Objects.FindId(i).InstanceDefinition.Id != source.Id for i in ids):
            raise ValueError('Select copies of one definition at a time.')
        return FamilyDialog(doc, source, operation, ids).show_for_doc(doc)
    except Exception as error:
        message(doc, 'Block command', str(error))


class AssignLayerDialog(BlockDialog):
    def __init__(self, doc, definition_ids):
        import block_layers as rules
        super().__init__('Assign block layer', 'Blocks', 'Assign home layer',
                         '')
        self.doc, self.ids = doc, list(definition_ids)
        definitions = [doc.InstanceDefinitions.FindId(Guid(key)) for key in self.ids]
        if any(d is None or d.IsDeleted or not rules.contents_are_local(d) for d in definitions):
            raise ValueError('Choose local definitions. Linked/reference blocks are skipped.')
        self.expected = {str(d.Id): d.GetUserString(rules.ASSIGNMENT_KEY) for d in definitions}
        self.body.AddRow(ui.label(definitions[0].Name if len(definitions) == 1 else
                                 '{} block definitions'.format(len(definitions)), ui.CAPTION_SIZE, True))
        self.layers = sorted([l for l in doc.Layers if not l.IsDeleted and not l.IsReference],
                             key=lambda l: l.FullPath.casefold())
        self.choice = forms.DropDown()
        self.choice.Width = 440
        self.choice.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
        self.choice.BackgroundColor, self.choice.TextColor = ui.FIELD, ui.INK
        self.choice.Items.Add('No home layer (remove rule)')
        for layer in self.layers:
            self.choice.Items.Add(layer.FullPath)
        selected = 0
        try:
            assignment = rules.read_assignment(definitions[0])
            target = rules.find_target(doc, assignment) if assignment else None
            if target:
                selected = next(i + 1 for i, layer in enumerate(self.layers) if layer.Id == target.Id)
        except (ValueError, StopIteration):
            pass
        self.choice.SelectedIndex = selected
        self.body.AddRow(ui.label('Home layer'))
        self.body.AddRow(self.choice)
        save = ui.button('Save', True)
        save.Click += self.save
        self.DefaultButton = save
        self.finish(ui.action_row(save))

    def save(self, sender=None, event=None):
        import block_layers as rules
        try:
            index = self.choice.SelectedIndex
            if index < 0:
                raise ValueError('Choose a home layer.')
            target_id = str(self.layers[index - 1].Id) if index else None
            rules.save_assignments(self.doc, {key: target_id for key in self.ids}, self.expected)
            self.Close(True)
        except Exception as error:
            self.set_status(str(error))


class LayerOverview(BlockDialog):
    def __init__(self, doc):
        super().__init__('Show block layers', 'Blocks', 'Block home layers', '')
        self.doc = doc
        self.search = field('')
        self.search.PlaceholderText = 'Find a block or home layer'
        self.body.AddRow(self.search)
        self.unassigned = ui.checkbox('Include unassigned blocks')
        self.unassigned.Checked = True
        self.body.AddRow(self.unassigned)
        self.grid = table([('Block', 180), ('Home layer', 160), ('Status', 100)], 180)
        self.grid.AllowMultipleSelection = False
        self.body.AddRow(ui.InfoPanel(self.grid))
        self.assign_button = ui.button('Assign layer', True)
        refresh = ui.button('Refresh')
        self.assign_button.Click += self.assign
        refresh.Click += self.refresh
        self.search.TextChanged += self.refresh
        self.unassigned.CheckedChanged += self.refresh
        self.grid.SelectionChanged += self.selection_changed
        self.DefaultButton = self.assign_button
        self.finish(ui.action_row(refresh, self.assign_button))
        self.refresh()

    def refresh(self, sender=None, event=None):
        import block_layers as rules
        self.records = []
        query = self.search.Text.casefold()
        for definition in sorted(self.doc.InstanceDefinitions, key=lambda d: (d.Name or '').casefold()):
            if definition.IsDeleted:
                continue
            raw = definition.GetUserString(rules.ASSIGNMENT_KEY)
            if raw is None and not self.unassigned.Checked:
                continue
            path, status = '', 'Unassigned'
            try:
                assignment = rules.read_assignment(definition)
                if assignment:
                    target = rules.find_target(self.doc, assignment)
                    path = target.FullPath if target else assignment['layer_path']
                    status = 'Assigned' if target else 'Missing layer'
            except ValueError:
                status = 'Invalid rule'
            local = rules.contents_are_local(definition)
            if not local:
                status = 'Linked / reference'
            if query not in (definition.Name + ' ' + path).casefold():
                continue
            self.records.append(dict(id=str(definition.Id), name=definition.Name, path=path,
                                     status=status, local=local))
        set_rows(self.grid, [(r['name'], r['path'], r['status']) for r in self.records],
                 keys=[r['id'] for r in self.records])
        self.selection_changed()
        self.set_status('')

    def selection_changed(self, sender=None, event=None):
        record = selected_record(self.grid, self.records)
        self.assign_button.Enabled = bool(record and record['local'])

    def assign(self, sender=None, event=None):
        record = selected_record(self.grid, self.records)
        if record is None:
            return
        try:
            AssignLayerDialog(self.doc, [record['id']]).ShowModal(self)
            self.refresh()
        except Exception as error:
            self.set_status(str(error))


class ApplyLayersDialog(BlockDialog):
    def __init__(self, doc, definition_ids=None):
        super().__init__('Apply block layers', 'Blocks', 'Apply home layers',
                         '')
        self.doc = doc
        self.definition_ids = definition_ids
        self.nested = ui.checkbox('Include nested block instances')
        self.body.AddRow(self.nested)
        self.summary = ui.label('', ui.CAPTION_SIZE, True)
        self.body.AddRow(self.summary)
        self.grid = table([('Block', 140), ('Current layer', 110), ('Home layer', 110), ('Result', 120)], 170)
        self.review_panel = ui.InfoPanel(self.grid)
        self.review_panel.Visible = False
        self.review_button = self.detail_button('Full review', self.review_panel)
        self.body.AddRow(self.review_panel)
        self.apply_button = ui.button('Apply layers', True)
        refresh = ui.button('Refresh')
        self.apply_button.Click += self.apply
        refresh.Click += self.refresh
        self.nested.CheckedChanged += self.refresh
        self.DefaultButton = self.apply_button
        self.finish(ui.action_row(self.review_button, refresh, self.apply_button))
        self.refresh()

    def refresh(self, sender=None, event=None):
        import block_layers as rules
        try:
            self.rows = rules.plan_cleanup(self.doc, self.definition_ids, include_nested=bool(self.nested.Checked))
            visible = [r for r in self.rows if r['status'] != 'unassigned']
            set_rows(self.grid, [(r['block'], r['source_path'], r.get('target_path', r.get('saved_path', '')),
                                 r['status']) for r in visible])
            moves = [r for r in self.rows if r['status'] == 'move']
            nested = sum(r['occurrences'] for r in moves if r['parent_id'])
            skipped = sum(1 for r in visible if r['status'] not in ('move', 'already correct'))
            self.summary.Text = '{} instances to move · {} skipped'.format(len(moves), skipped)
            if nested:
                self.summary.Text += '\n{} nested occurrences affected.'.format(nested)
            self.apply_button.Enabled = bool(moves)
            self.set_status('')
        except Exception as error:
            self.apply_button.Enabled = False
            self.set_status(str(error))

    def apply(self, sender=None, event=None):
        import block_layers as rules
        try:
            rules.cleanup(self.doc, self.definition_ids, expected=self.rows, include_nested=bool(self.nested.Checked))
            self.Close(True)
        except Exception as error:
            self.set_status(str(error))


def run_layers(doc, operation, definition_ids=None):
    try:
        if operation == 'assign':
            if definition_ids is None:
                ids = pick_instances(doc, 'Select blocks to assign a home layer', multiple=True)
                if not ids:
                    return
                definition_ids = list({str(doc.Objects.FindId(i).InstanceDefinition.Id) for i in ids})
            dialog = AssignLayerDialog(doc, definition_ids)
        elif operation == 'apply':
            dialog = ApplyLayersDialog(doc)
        else:
            dialog = LayerOverview(doc)
        return dialog.show_for_doc(doc)
    except Exception as error:
        message(doc, 'Block home layers', str(error))



