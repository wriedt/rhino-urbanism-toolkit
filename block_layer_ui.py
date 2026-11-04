#! python 3
# -*- coding: utf-8 -*-
"""Staged assignment editor and scoped cleanup preview for Rhino 8."""
from collections import Counter

import Rhino
import Eto.Forms as forms
import Eto.Drawing as drawing
from System import Array, Object, Guid

import block_layers as rules
import urbanism_ui as ui


def table(columns, height=235):
    grid = forms.GridView()
    grid.AllowMultipleSelection = True
    grid.ShowHeader = True
    grid.Size = drawing.Size(730, height)
    grid.BackgroundColor = ui.FIELD
    grid.TextColor = ui.INK
    grid.Font = drawing.Font('Segoe UI', ui.BODY_SIZE)
    for index, (heading, width) in enumerate(columns):
        column = forms.GridColumn()
        column.HeaderText = heading
        column.DataCell = forms.TextBoxCell(index)
        column.Editable = False
        column.Width = width
        column.Sortable = False
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
 <Style.Triggers><Trigger Property="IsSelected" Value="True">
 <Setter Property="Background" Value="{accent}"/><Setter Property="Foreground" Value="{on}"/>
 </Trigger></Style.Triggers></Style>'''), (DataGridColumnHeader, '''<Style TargetType="DataGridColumnHeader">
 <Setter Property="Background" Value="{aqua}"/><Setter Property="Foreground" Value="{ink}"/>
 <Setter Property="Padding" Value="4,8"/>
 </Style>''')]:
            source = template.replace('<Style ', '<Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" ', 1)
            grid.ControlObject.Resources[clr.GetClrType(native_type)] = XamlReader.Parse(source.format(**colours))
    return grid


def set_rows(grid, rows):
    grid.DataStore = Array[Object]([Array[Object](list(row)) for row in rows])


class AssignmentDialog(ui.AquaDialog):
    def Close(self, result=False):
        # Eto's generic Close(bool) overload is hidden on a Python-derived dialog.
        self.Result = result
        super().Close()

    def __init__(self, doc, definition_ids=None):
        super().__init__('Block layer assignments', 'Blocks', 'Block layer assignments',
            'Stage rules for block definitions. Instances move only if you apply cleanup.')
        self.doc = doc
        self.scope_ids = list(definition_ids) if definition_ids is not None else None
        self.records = rules.definition_inventory(doc, definition_ids)
        self.expected = {r['id']: r['raw'] for r in self.records}
        self.pending = {}
        self.changed_ids = []
        self.apply_requested = False
        self.visible_records = []
        self.nested_box = ui.checkbox('Include nested definitions')
        self.nested_box.Checked = False
        self.body.AddRow(self.nested_box)
        self.search = forms.TextBox()
        self.search.BackgroundColor = ui.FIELD
        self.search.TextColor = ui.INK
        self.search.PlaceholderText = 'Filter block names'
        self.body.AddRow(self.search)
        self.grid = table([('Block definition', 215), ('Editable / total', 110),
                           ('Assigned layer', 255), ('Status', 145)])
        self.body.AddRow(ui.InfoPanel(self.grid))
        self.selection_label = ui.label('', ui.CAPTION_SIZE, True)
        self.body.AddRow(self.selection_label)
        self.choose_button = ui.button('Choose layer')
        self.remove_button = ui.button('Remove assignment')
        self.revert_button = ui.button('Revert selected')
        self.body.AddRow(ui.action_row(self.choose_button, self.remove_button, self.revert_button))
        self.apply_box = ui.checkbox('Apply now after saving (preview first)')
        self.apply_box.Checked = False
        self.body.AddRow(self.apply_box)
        self.body.AddRow(ui.label('Nested cleanup skips shared edits that would affect hidden or locked copies.',
                                 ui.CAPTION_SIZE, True))
        self.save_button = ui.button('Save assignments', True)
        cancel = ui.button('Cancel')
        cancel.Click += lambda s, e: self.Close(False)
        self.choose_button.Click += lambda s, e: self.choose_layer()
        self.remove_button.Click += lambda s, e: self.stage_layer(None)
        self.revert_button.Click += lambda s, e: self.revert_selected()
        self.save_button.Click += lambda s, e: self.save()
        self.search.TextChanged += lambda s, e: self.refresh()
        self.nested_box.CheckedChanged += lambda s, e: self.change_nested_scope()
        self.grid.SelectionChanged += lambda s, e: self.update_actions()
        self.DefaultButton = self.save_button
        self.AbortButton = cancel
        self.finish(ui.action_row(cancel, self.save_button))
        self.refresh()
        if definition_ids is not None:
            self.grid.SelectAll()
        self.update_actions()

    def change_nested_scope(self):
        selected = set(self.selected_keys())
        previous = {r['id'] for r in self.records}
        self.records = rules.definition_inventory(self.doc, self.scope_ids,
            include_nested=bool(self.nested_box.Checked))
        current = {r['id'] for r in self.records}
        removed = set(self.pending) - current
        for key in removed:
            self.pending.pop(key)
        for record in self.records:
            self.expected.setdefault(record['id'], record['raw'])
        if self.nested_box.Checked and self.scope_ids is not None:
            selected.update(current - previous)
        self.refresh(selected)
        self.set_status(('Discarded {0} pending nested changes.'.format(len(removed)) if removed else
            'Nested definitions are included; linked contents are excluded.' if self.nested_box.Checked else
            'Only definitions with top-level instances are shown.'))

    def selected_keys(self):
        return [self.visible_records[i]['id'] for i in self.grid.SelectedRows
                if 0 <= i < len(self.visible_records)]

    def describe(self, record):
        key = record['id']
        if key in self.pending:
            target_id = self.pending[key]
            if target_id is None:
                return 'Unassigned', 'Pending removal'
            target = self.doc.Layers.FindId(Guid(target_id))
            return (target.FullPath if target and not target.IsDeleted else 'Missing layer',
                    'Pending change')
        definition = self.doc.InstanceDefinitions.FindId(Guid(key))
        try:
            assignment = rules.read_assignment(definition)
            if assignment is None:
                return 'Unassigned', 'No assignment'
            target = rules.find_target(self.doc, assignment)
            if target is None:
                return assignment['layer_path'], 'Missing layer'
            return target.FullPath, 'Assigned'
        except ValueError:
            return 'Invalid saved rule', 'Needs assignment'

    def refresh(self, selected=None):
        selected = set(self.selected_keys() if selected is None else selected)
        query = (self.search.Text or '').casefold()
        self.visible_records = [r for r in self.records if query in r['name'].casefold()]
        values = []
        for r in self.visible_records:
            path, status = self.describe(r)
            if not r['editable']:
                status = 'Read-only copies'
            elif r['nested_count'] and status == 'Assigned':
                status = 'Assigned · nested'
            values.append([r['name'], '{0} / {1}'.format(r['editable'], r['count']), path, status])
        set_rows(self.grid, values)
        self.grid.SelectedRows = Array[int]([i for i, r in enumerate(self.visible_records)
                                            if r['id'] in selected])
        self.update_actions()

    def update_actions(self):
        selected = set(self.selected_keys())
        editable = bool(selected) and all(r['editable'] for r in self.records if r['id'] in selected)
        self.choose_button.Enabled = editable
        self.remove_button.Enabled = editable
        self.revert_button.Enabled = any(key in self.pending for key in selected)
        self.save_button.Enabled = bool(self.pending)
        self.selection_label.Text = '{0} definitions selected; {1} pending changes. Ctrl/Shift selects multiple rows.'.format(
            len(selected), len(self.pending))

    def stage_layer(self, target_id):
        selected = self.selected_keys()
        if not selected:
            return
        if any(not r['editable'] for r in self.records if r['id'] in selected):
            self.set_status('Select definitions with at least one visible, unlocked, editable instance.')
            return
        for key in selected:
            self.pending[key] = target_id
            if target_id is None and self.expected[key] is None:
                self.pending.pop(key)
            elif target_id is not None:
                definition = self.doc.InstanceDefinitions.FindId(Guid(key))
                try:
                    original = rules.read_assignment(definition)
                    target = rules.find_target(self.doc, original) if original else None
                    if target is not None and str(target.Id) == target_id:
                        self.pending.pop(key)
                except ValueError:
                    pass
        self.set_status('Changes are staged. Cancel discards them; Save writes them to the model.')
        self.refresh(selected)

    def choose_layer(self):
        keys = self.selected_keys()
        if not keys:
            return
        initial = self.doc.Layers.CurrentLayerIndex
        path, _ = self.describe(next(r for r in self.records if r['id'] == keys[0]))
        index = self.doc.Layers.FindByFullPath(path, -1)
        if index >= 0:
            initial = index
        accepted, index, _ = Rhino.UI.Dialogs.ShowSelectLayerDialog(
            initial, 'Assign layer to {0} block definitions'.format(len(keys)), False, False, False)
        if accepted:
            self.stage_layer(str(self.doc.Layers[index].Id))

    def revert_selected(self):
        selected = self.selected_keys()
        for key in selected:
            self.pending.pop(key, None)
        self.refresh(selected)
        self.set_status('Selected changes reverted.')

    def save(self):
        try:
            self.changed_ids = rules.save_assignments(self.doc, self.pending, self.expected)
            self.apply_requested = bool(self.apply_box.Checked) and bool(self.changed_ids)
            self.Close(True)
        except Exception as error:
            self.set_status(str(error))


class CleanupPreview(ui.AquaDialog):
    def Close(self, result=False):
        self.Result = result
        super().Close()

    def __init__(self, doc, definition_ids):
        super().__init__('Block layer cleanup preview', 'Blocks', 'Review layer changes',
            'Assignments are saved. Review the changed definitions at every local nesting level.')
        self.doc = doc
        self.definition_ids = list(definition_ids)
        self.excluded_ids = set()
        self.rows = []
        self.result_rows = None
        self.summary = ui.label('')
        self.body.AddRow(self.summary)
        self.grid = table([('Block / reference ID', 200), ('Copies', 65), ('Current layer', 145),
                           ('Target layer', 145), ('Result', 170)], height=270)
        self.body.AddRow(ui.InfoPanel(self.grid))
        self.body.AddRow(ui.label('Nested edits affect every copy of the containing definition.\n'
                                 'Shared references with hidden or locked copies are skipped.',
                                 ui.CAPTION_SIZE, True))
        self.apply_button = ui.button('Apply cleanup', True)
        self.refresh_button = ui.button('Refresh preview')
        self.resolve_button = ui.button('Resolve missing layers')
        cancel = ui.button('Keep assignments only')
        self.apply_button.Click += lambda s, e: self.apply()
        self.refresh_button.Click += lambda s, e: self.refresh_preview()
        self.resolve_button.Click += lambda s, e: self.resolve_targets()
        cancel.Click += lambda s, e: self.Close(False)
        self.DefaultButton = self.apply_button
        self.AbortButton = cancel
        self.body.AddRow(ui.action_row(self.resolve_button))
        self.finish(ui.action_row(cancel, self.refresh_button, self.apply_button))
        self.refresh_preview()

    def refresh_preview(self):
        try:
            self.rows = rules.plan_cleanup(self.doc, self.definition_ids,
                excluded_definition_ids=self.excluded_ids)
            counts = Counter(row['status'] for row in self.rows)
            self.summary.Text = '{0} reference edits; {1} already correct; {2} skipped.'.format(
                counts['move'], counts['already correct'],
                len(self.rows) - counts['move'] - counts['already correct'])
            set_rows(self.grid, [[r['block'] + ' · ' + str(r['id'])[:8], str(r['occurrences']), r['source_path'],
                r.get('target_path', r.get('saved_path', 'Unassigned')), r['status']]
                for r in self.rows])
            self.resolve_button.Visible = bool(counts['missing target layer'])
            self.apply_button.Enabled = bool(counts['move']) and not counts['missing target layer']
            shared = [r for r in self.rows if r['status'] == 'shared with protected copies']
            if len(shared) > 3:
                for row in shared:
                    Rhino.RhinoApp.WriteLine('Preview skip: {0} inside {1}; {2} protected copies ({3}).'.format(
                        row['block'], row['parent_name'], sum(row['protection'].values()),
                        ', '.join(sorted(row['protection']))))
            self.set_status('\n'.join('{0} inside {1}: {2} protected copies ({3}).'.format(
                r['block'], r['parent_name'], sum(r['protection'].values()),
                ', '.join(sorted(r['protection']))) for r in shared[:3]) +
                ('\nSee command history for the remaining shared skips.' if len(shared) > 3 else ''))
        except Exception as error:
            self.apply_button.Enabled = False
            self.set_status(str(error))

    def apply(self):
        try:
            self.result_rows = rules.cleanup(self.doc, self.definition_ids, expected=self.rows,
                excluded_definition_ids=self.excluded_ids)
            self.Close(True)
        except Exception as error:
            self.apply_button.Enabled = False
            self.set_status(str(error))

    def resolve_targets(self):
        result = resolve_missing_layers(self.doc, self.definition_ids, owner=self,
            excluded_definition_ids=self.excluded_ids)
        if result is not None:
            self.excluded_ids.update(result['skipped'])
            self.refresh_preview()


class MissingLayerDialog(ui.AquaDialog):
    def Close(self, result=False):
        self.Result = result
        super().Close()

    def __init__(self, doc, groups, definition_ids=None, excluded_definition_ids=(), preview=False):
        super().__init__('Missing block layers', 'Blocks', 'Resolve missing target layers',
            'Resolve each missing path once. Skipping retains its rule and placement for this cleanup.')
        self.doc = doc
        self.groups = groups
        self.definition_ids = definition_ids
        self.excluded_ids = set(excluded_definition_ids)
        self.choices = {}
        self.resolution = None
        self.create_box = ui.checkbox('Create missing target layers with default settings')
        self.create_box.Checked = False
        self.body.AddRow(self.create_box)
        self.grid = table([('Missing target layer', 330), ('Blocks', 65), ('Copies', 70), ('Resolution', 260)])
        self.body.AddRow(ui.InfoPanel(self.grid))
        choose = ui.button('Choose existing layer')
        skip = ui.button('Skip selected')
        reset = ui.button('Reset selected')
        self.body.AddRow(ui.action_row(choose, skip, reset))
        self.body.AddRow(ui.label('Creation includes missing parent layers. Existing layer settings are preserved.',
                                 ui.CAPTION_SIZE, True))
        self.continue_button = ui.button('Save resolutions' if preview else 'Continue cleanup', True)
        refresh = ui.button('Refresh list')
        cancel = ui.button('Cancel')
        self.create_box.CheckedChanged += lambda s, e: self.refresh()
        choose.Click += lambda s, e: self.choose_existing()
        skip.Click += lambda s, e: self.set_choice(dict(mode='skip'))
        reset.Click += lambda s, e: self.reset_selected()
        refresh.Click += lambda s, e: self.refresh_groups()
        self.continue_button.Click += lambda s, e: self.commit()
        cancel.Click += lambda s, e: self.Close(False)
        self.DefaultButton = self.continue_button
        self.AbortButton = cancel
        self.finish(ui.action_row(cancel, refresh, self.continue_button))
        self.refresh()
        self.grid.SelectAll()

    def selected_keys(self):
        return [self.groups[i]['key'] for i in self.grid.SelectedRows if 0 <= i < len(self.groups)]

    def decisions(self):
        return {g['key']: self.choices.get(g['key'], dict(mode='create' if self.create_box.Checked else 'skip'))
                for g in self.groups}

    def refresh(self):
        selected = set(self.selected_keys())
        choices = self.decisions()
        values = []
        for group in self.groups:
            choice = choices[group['key']]
            if choice['mode'] == 'existing':
                layer = self.doc.Layers.FindId(Guid(choice['target_id']))
                action = 'Use ' + layer.FullPath if layer and not layer.IsDeleted else 'Chosen layer missing'
            else:
                action = 'Create intended path' if choice['mode'] == 'create' else 'Skip this cleanup'
            values.append([group['path'], str(len(group['definitions'])), str(group['occurrences']), action])
        set_rows(self.grid, values)
        self.grid.SelectedRows = Array[int]([i for i, g in enumerate(self.groups) if g['key'] in selected])

    def set_choice(self, choice):
        for key in self.selected_keys():
            self.choices[key] = dict(choice)
        self.refresh()

    def reset_selected(self):
        for key in self.selected_keys():
            self.choices.pop(key, None)
        self.refresh()

    def choose_existing(self):
        if not self.selected_keys():
            self.set_status('Select the missing target paths to map.')
            return
        accepted, index, _ = Rhino.UI.Dialogs.ShowSelectLayerDialog(
            self.doc.Layers.CurrentLayerIndex, 'Use existing layer for missing targets', False, False, False)
        if accepted:
            self.set_choice(dict(mode='existing', target_id=str(self.doc.Layers[index].Id)))

    def refresh_groups(self):
        self.groups = rules.missing_targets(self.doc, self.definition_ids, self.excluded_ids)
        self.choices = {k: v for k, v in self.choices.items() if k in {g['key'] for g in self.groups}}
        self.refresh()
        self.set_status('Missing targets refreshed. Review the choices before continuing.')

    def commit(self):
        try:
            self.resolution = rules.resolve_missing_targets(self.doc, self.groups, self.decisions())
            self.Close(True)
        except Exception as error:
            self.set_status(str(error))


def resolve_missing_layers(doc, definition_ids=None, owner=None, excluded_definition_ids=()):
    groups = rules.missing_targets(doc, definition_ids, excluded_definition_ids)
    if not groups:
        return dict(created=[], changed=[], skipped=[])
    dlg = MissingLayerDialog(doc, groups, definition_ids, excluded_definition_ids, preview=owner is not None)
    try:
        accepted = dlg.ShowModal(owner) if owner is not None else dlg.show_for_doc(doc)
        if not accepted:
            return None
        result = dlg.resolution
        Rhino.RhinoApp.WriteLine('Missing targets resolved: {0} layers created, {1} rules updated, {2} definitions skipped.'.format(
            len(result['created']), len(result['changed']), len(result['skipped'])))
        return result
    finally:
        dlg.Dispose(True)


def edit_assignments(doc, definition_ids=None):
    dlg = AssignmentDialog(doc, definition_ids)
    try:
        if not dlg.records:
            Rhino.RhinoApp.WriteLine('No top-level block definitions to assign.')
            return
        accepted = dlg.show_for_doc(doc)
        changed = dlg.changed_ids[:]
        apply_requested = dlg.apply_requested
    finally:
        dlg.Dispose(True)
    if not accepted:
        Rhino.RhinoApp.WriteLine('Block layer assignment cancelled; staged changes discarded.')
        return
    Rhino.RhinoApp.WriteLine('Saved layer assignments for {0} block definitions.'.format(len(changed)))
    if apply_requested:
        preview = CleanupPreview(doc, changed)
        try:
            if preview.show_for_doc(doc):
                rules.report(preview.result_rows)
            else:
                Rhino.RhinoApp.WriteLine('Assignments kept. Cleanup was not applied.')
        finally:
            preview.Dispose(True)
