"""Visible focused dialogs, cancellation and native Undo/Redo; removes all fixtures."""
import importlib
import math
import traceback
from pathlib import Path
import Rhino
import Eto.Forms as forms
import scriptcontext as sc
from System import Action, Guid
from System.Collections.Generic import List
import block_versions as naming
import block_actions as actions
import block_layers as rules
import block_dialogs as screen


def run(doc):
    for module in (naming,actions,rules,screen):
        importlib.reload(module)
    output=Path(r'C:\Projects\rhino-urbanism-toolkit\work\block-command-validation')
    output.mkdir(exist_ok=True)
    previous=sc.doc; sc.doc=doc
    selected=[o.Id for o in doc.Objects.GetSelectedObjects(False,False)]
    modified=doc.Modified
    prefix='RUT_FocusedTest_'+str(Guid.NewGuid()).replace('-','')[:6]
    indices,objects,layer_ids,checks,errors=[],[],[],[],[]

    def check(value,label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def boundary():
        if doc.UndoRecordingIsActive:
            doc.EndUndoRecord(doc.CurrentUndoRecordSerialNumber)

    def undo(redo=False):
        boundary()
        result=doc.Redo() if redo else doc.Undo()
        boundary()
        return result

    def add(name,child=None):
        geo,attrs=List[Rhino.Geometry.GeometryBase](),List[Rhino.DocObjects.ObjectAttributes]()
        geo.Add(Rhino.Geometry.Point(Rhino.Geometry.Point3d.Origin) if child is None else
            Rhino.Geometry.InstanceReferenceGeometry(doc.InstanceDefinitions[child].Id,Rhino.Geometry.Transform.Identity))
        attrs.Add(Rhino.DocObjects.ObjectAttributes())
        index=doc.InstanceDefinitions.Add(prefix+'_'+name,'',Rhino.Geometry.Point3d.Origin,geo,attrs)
        indices.append(index)
        return index

    def place(index):
        object_id=doc.Objects.AddInstanceObject(index,Rhino.Geometry.Transform.Identity)
        objects.append(object_id)
        return object_id

    def capture(dialog,name):
        from System.Windows.Threading import DispatcherPriority
        from System.Windows.Media import VisualTreeHelper,PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap,PngBitmapEncoder,BitmapFrame
        from System.IO import FileStream,FileMode
        native=dialog.ControlObject.Content
        native.UpdateLayout()
        native.Dispatcher.Invoke(Action(lambda:None),DispatcherPriority.ApplicationIdle)
        dpi=VisualTreeHelper.GetDpi(native)
        bitmap=RenderTargetBitmap(int(math.ceil(native.ActualWidth*dpi.DpiScaleX)),
            int(math.ceil(native.ActualHeight*dpi.DpiScaleY)),dpi.PixelsPerInchX,dpi.PixelsPerInchY,PixelFormats.Pbgra32)
        bitmap.Render(native)
        encoder=PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream=FileStream(str(output/name),FileMode.Create)
        try:
            encoder.Save(stream)
        finally:
            stream.Dispose()

    def show(dialog,callback):
        timer=forms.UITimer();timer.Interval=.25
        state={'closed':False}
        def tick(sender,event):
            if state['closed']:
                return
            timer.Stop()
            try:
                callback(dialog)
            except Exception:
                errors.append(traceback.format_exc());dialog.Close(False)
        def shown(sender,event):
            if not state['closed']:
                timer.Start()
        dialog.Shown+=shown
        timer.Elapsed+=tick
        try:
            result=bool(dialog.show_for_doc(doc))
            if errors:
                raise AssertionError(errors[-1])
            return result
        finally:
            state['closed']=True
            dialog.Shown-=shown
            timer.Stop()
            timer.Elapsed-=tick
            timer.Dispose();dialog.Dispose(True)

    def click(button):
        from System.Windows import RoutedEventArgs
        from System.Windows.Controls import Button
        button.ControlObject.RaiseEvent(RoutedEventArgs(Button.ClickEvent))

    def press_key(dialog, name, focused=None):
        from System.Windows import PresentationSource
        from System.Windows.Input import Keyboard, Key, KeyEventArgs
        native=(focused or dialog.DefaultButton).ControlObject
        check(native.IsKeyboardFocused,'expected control is focused before '+name)
        source=PresentationSource.FromVisual(native)
        preview=KeyEventArgs(Keyboard.PrimaryDevice,source,0,getattr(Key,name))
        preview.RoutedEvent=Keyboard.PreviewKeyDownEvent
        native.RaiseEvent(preview)
        if preview.Handled:
            return
        for routed in (Keyboard.KeyDownEvent,Keyboard.KeyUpEvent):
            event=KeyEventArgs(Keyboard.PrimaryDevice,source,0,getattr(Key,name))
            event.RoutedEvent=routed
            native.RaiseEvent(event)

    try:
        a,b,c=[add('House_'+s) for s in ('01','01 copy','04')]
        ids=[place(c),place(c),place(c)]
        child=add('Child_01'); parent=add('Parent_01',child); parent_id=place(parent)
        layer=Rhino.DocObjects.Layer();layer.Name=prefix+'_Home'
        li=doc.Layers.Add(layer);layer_ids.append(doc.Layers[li].Id)
        key=lambda i:str(doc.InstanceDefinitions[i].Id)
        boundary()

        doc.Objects.UnselectAll()
        for object_id in ids[:2]:
            doc.Objects.Select(object_id)
        picked=screen.pick_instances(doc,'Preselection test',multiple=True)
        check(set(picked)==set(ids[:2]),'native picker accepts compatible preselection')
        doc.Objects.UnselectAll()

        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'create',ids[:2])
        def cancel_create(d):
            check(d.result_plan['new_name']==prefix+'_House_05','create dialog preserves existing numeric convention')
            check(d.DefaultButton==d.apply_button and d.apply_button.ControlObject.IsKeyboardFocused,
                  'create action has initial keyboard focus')
            check(d.AbortButton==d.close_button,'Escape uses header X')
            check(not d.summary.Visible and '\n' not in d.preview.Text,'create preview is one line without repeated explanation')
            check(not d.starting_panel.Visible,'versioned sources hide the starting-name field')
            check(len(list(d.naming_panel.Children))==2,'Adjust naming has just one labelled selector')
            click(d.adjust_button)
            capture(d,'adjust-version-part.png')
            none=next(i for i,r in enumerate(d.version_records) if r['origin']=='none')
            d.choice.SelectedIndex=none
            check(d.starting_panel.Visible and d.result_plan['renames'],'No version introduces a starting-name field')
            d.choice.SelectedIndex=0
            check(not d.starting_panel.Visible and not d.result_plan['renames'],
                  'choosing an original version hides starting name again')
            capture(d,'create-version.png');click(d.close_button)
        check(not show(dialog,cancel_create),'create dialog Cancel returns false')
        check(doc.Objects.FindId(ids[0]).InstanceDefinition.Index==c,'Cancel switches no copies')
        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'create',ids[:2])
        def escape_create(d):
            press_key(d,'Escape')
            check(not d.Visible,'Escape closes without applying')
        check(not show(dialog,escape_create),'Escape cancels the create dialog')
        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'create',ids[:2])
        check(show(dialog,lambda d:press_key(d,'Return')),'Enter creates the version')
        check(doc.Objects.FindId(ids[0]).InstanceDefinition.Name==prefix+'_House_05' and
              doc.Objects.FindId(ids[2]).InstanceDefinition.Index==c,'create changes only selected copies')
        check(undo(),'create native Undo succeeds')
        check(all(doc.Objects.FindId(i).InstanceDefinition.Index==c for i in ids),'one Undo restores selected copies')
        check(undo(True),'create Redo succeeds')
        check(doc.Objects.FindId(ids[0]).InstanceDefinition.Name==prefix+'_House_05','Redo restores new version')
        undo()
        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'create',ids[:2])
        check(show(dialog,lambda d:press_key(d,'Space')),'Space creates the version')
        check(doc.Objects.FindId(ids[0]).InstanceDefinition.Name==prefix+'_House_05','Space invokes primary action')
        undo()

        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[a],'consolidate')
        def consolidate(d):
            d.lowest.Checked=True
            check(len(d.result_plan['members'])==3,'consolidation preview finds accidental copy')
            capture(d,'consolidate-versions.png');d.apply()
        check(show(dialog,consolidate),'consolidation dialog applies')
        check([doc.InstanceDefinitions[i].Name for i in (a,b,c)]==
            [prefix+'_House_'+s for s in ('01','02','03')],'consolidation renumbers complete family')
        check(undo(),'consolidation native Undo succeeds')
        check(doc.InstanceDefinitions[b].Name==prefix+'_House_01 copy','Undo restores copy suffix')

        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'rename')
        def rename(d):
            d.new_family.Text=prefix+'_Court'
            check(len(d.result_plan['renames'])==3,'rename review includes all family definitions')
            check(not d.naming_panel.Visible and not d.review_panel.Visible,'naming corrections and full review start collapsed')
            small_height=d.ControlObject.ActualHeight
            d.separator.SelectedIndex=0
            check(all(r['new'].startswith(prefix+'_Court0') for r in d.result_plan['renames']),
                  'None separator joins family and version')
            capture(d,'rename-family-no-separator.png')
            d.separator.SelectedIndex=1
            check(all(r['new'].startswith(prefix+'_Court 0') for r in d.result_plan['renames']), 'Space separator is explicit')
            d.separator.SelectedIndex=4;d.separator_text.Text=' - '
            check(all(r['new'].startswith(prefix+'_Court - 0') for r in d.result_plan['renames']),
                  'Custom separator preserves exact spaces and characters')
            click(d.review_button);click(d.adjust_button)
            check(d.review_panel.Visible and d.naming_panel.Visible,'optional panels can be expanded')
            check(d.ControlObject.ActualHeight>small_height,'expanded review resizes the window to fit')
            capture(d,'rename-family-expanded.png')
            click(d.review_button);click(d.adjust_button)
            check(not d.review_panel.Visible and not d.naming_panel.Visible,'optional panels collapse again')
            check(d.ControlObject.ActualHeight<=small_height+2,'collapsing review restores compact window height')
            d.separator.ControlObject.IsDropDownOpen=True
            capture(d,'separator-options.png')
            d.separator.ControlObject.SelectedIndex=0
            d.separator.ControlObject.IsDropDownOpen=False
            check(d.separator.SelectedIndex==0 and d.result_plan['renames'][0]['new'].startswith(prefix+'_Court0'),
                  'native dropdown selection updates separator preview')
            d.separator.SelectedIndex=2
            capture(d,'rename-family.png');d.apply()
        check(show(dialog,rename),'rename dialog applies')
        check(doc.InstanceDefinitions[b].Name==prefix+'_Court_01 copy','family rename preserves duplicate suffix')
        check(undo(),'rename native Undo succeeds')
        check(doc.InstanceDefinitions[c].Name==prefix+'_House_04','Undo restores family names')

        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'rename')
        def collision(d):
            d.new_family.Text=prefix+'_Child'
            check(not d.apply_button.Enabled and d.error_panel.Visible,'family collision disables Apply and opens error panel')
            check(d.status.Text.startswith('⚠ ') and d.status.Font.Size>=screen.ui.BODY_SIZE,
                  'error has warning icon and readable body size')
            capture(d,'rename-collision-warning.png')
            d.new_family.Text=prefix+'_Available'
            check(not d.error_panel.Visible and d.apply_button.Enabled,'correcting name clears error feedback')
            d.Close(False)
        show(dialog,collision)

        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[c],'rename')
        def join_family(d):
            d.separator.SelectedIndex=0
            d.apply()
        check(show(dialog,join_family),'separator-only rename applies')
        check(doc.InstanceDefinitions[c].Name==prefix+'_House04' and
              doc.InstanceDefinitions[b].Name==prefix+'_House01 copy','separator removal preserves versions and copy suffixes')
        joined=naming.suggestions(doc.InstanceDefinitions[c].Name,[r['name'] for r in actions.read_definitions(doc)])[0]
        check(actions.version_plan(doc,ids[:1],joined)['new_name']==prefix+'_House05',
              'joined family remains detectable for version creation')
        check(undo() and doc.InstanceDefinitions[c].Name==prefix+'_House_04','Undo restores removed separator')

        dialog=screen.AssignLayerDialog(doc,[key(c)])
        def cancel_layer(d):
            d.choice.SelectedIndex=next(i+1 for i,l in enumerate(d.layers) if l.Index==li)
            capture(d,'assign-home-layer.png');d.Close(False)
        show(dialog,cancel_layer)
        check(rules.read_assignment(doc.InstanceDefinitions[c]) is None,'assignment Cancel saves no rule')
        dialog=screen.AssignLayerDialog(doc,[key(c)])
        def assign(d):
            d.choice.SelectedIndex=next(i+1 for i,l in enumerate(d.layers) if l.Index==li)
            press_key(d,'Return')
        check(show(dialog,assign),'assignment dialog saves home rule')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex!=li for i in ids),'assignment does not move copies')
        check(undo(),'assignment native Undo succeeds')
        check(rules.read_assignment(doc.InstanceDefinitions[c]) is None,'Undo restores absence of home rule')
        check(undo(True),'assignment Redo succeeds')
        check(rules.read_assignment(doc.InstanceDefinitions[c])['layer_id']==str(doc.Layers[li].Id),'Redo restores home rule')

        apply_scope=[key(c),key(parent),key(child)]
        dialog=screen.ApplyLayersDialog(doc,apply_scope)
        def cancel_apply(d):
            check(not d.nested.Checked,'nested option defaults off')
            check(len([r for r in d.rows if r['status']=='move'])==3,'apply review includes unselected copies')
            click(d.review_button)
            native=d.ControlObject
            from System.Windows import SizeToContent, Thickness
            from System.Windows.Shell import WindowChrome
            check(d.Resizable and WindowChrome.GetWindowChrome(native).ResizeBorderThickness.Left>0,
                  'frameless dialog has resize borders')
            import ctypes
            from ctypes import wintypes
            from System.Windows.Interop import WindowInteropHelper
            user32=ctypes.WinDLL('user32',use_last_error=True)
            user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
            user32.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            user32.SendMessageW.restype=wintypes.LPARAM
            hwnd=WindowInteropHelper(native).Handle.ToInt64()
            rect=wintypes.RECT();user32.GetWindowRect(hwnd,ctypes.byref(rect))
            x,y=rect.left+2,(rect.top+rect.bottom)//2
            hit=user32.SendMessageW(hwnd,0x84,0,((y&0xffff)<<16)|(x&0xffff))
            check(hit==10,'window edge hit-test supports native drag resizing')
            width,height=d.grid.Width,d.grid.Height
            native.SizeToContent=SizeToContent.Manual
            native.Width=native.ActualWidth+160;native.Height=native.ActualHeight+90
            native.UpdateLayout()
            check(d.grid.Width>=width+150 and d.grid.Height>=height+80,'table grows with window in both directions')
            d.grid.Columns[0].Width=250
            capture(d,'apply-home-layers-resized.png')
            d.Close(False)
        show(dialog,cancel_apply)
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex!=li for i in ids),'apply Cancel moves no copies')
        check(show(screen.ApplyLayersDialog(doc,apply_scope),lambda d:press_key(d,'Space')),'Space applies home layers')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==li for i in ids),'all copies move to home layer')
        check(undo(),'apply native Undo succeeds')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex!=li for i in ids),'one Undo restores all copy layers')
        check(undo(True),'apply Redo succeeds')
        check(all(doc.Objects.FindId(i).Attributes.LayerIndex==li for i in ids),'Redo restores home layers')
        undo()

        dialog=screen.LayerOverview(doc)
        def overview(d):
            from System.Windows import PresentationSource
            from System.Windows.Input import Keyboard, Key, KeyEventArgs
            from System.Windows.Automation.Peers import CheckBoxAutomationPeer
            d.search.Text=prefix
            check(bool(d.unassigned.Checked) and len(d.records)==5,'overview defaults to all definitions')
            check(not d.status.Visible,'overview omits redundant count footer')
            d.unassigned.Checked=False
            check(len(d.records)==1,'unchecking unassigned shows only assigned definitions')
            d.unassigned.Checked=True
            check(len(d.records)==5,'overview can include unused and nested definitions')
            d.unassigned.Focus()
            native=d.unassigned.ControlObject
            press_key(d,'Space',d.unassigned)
            check(d.unassigned.Checked and len(d.records)==5,'Space does not toggle checkbox when primary action is disabled')
            from System.Reflection import BindingFlags
            native.GetType().GetMethod('OnClick',BindingFlags.Instance|BindingFlags.NonPublic).Invoke(native,None)
            check(not d.unassigned.Checked and len(d.records)==1,'mouse checkbox click still updates filtering')
            check(native.FocusVisualStyle is None and native.Template.FindName('Focus',native) is None,
                  'checkbox has no extra focus outline')
            check(CheckBoxAutomationPeer(native).GetName()=='Include unassigned blocks',
                  'themed checkbox retains accessible label')
            capture(d,'home-layers-checkbox-focused.png')
            d.unassigned.Checked=True
            d.search.Text='no match'
            check(len(d.records)==0 and not d.assign_button.Enabled,'empty search disables assignment')
            d.search.Text=prefix
            d.grid.SelectedRow=0
            check(d.assign_button.Enabled,'selected local definition enables assignment')
            selected=screen.selected_record(d.grid,d.records)['id']
            from System import Array, Object
            from System.Reflection import BindingFlags
            from System.Windows.Controls import DataGridSortingEventArgs
            native=d.grid.ControlObject
            method=native.GetType().GetMethod('OnSorting',BindingFlags.Instance|BindingFlags.NonPublic)
            for _ in range(2):
                method.Invoke(native,Array[Object]([DataGridSortingEventArgs(native.Columns[0])]))
            check(d.grid.Tag['column']==0 and d.grid.Tag['descending'],'header clicks toggle ascending and descending sorting')
            check(screen.selected_record(d.grid,d.records)['id']==selected,'sorting preserves selected definition identity')
            screen.sort_table(d.grid,2)
            check(d.grid.Tag['column']==2,'another table column can be sorted')
            def buttons(control):
                if isinstance(control,forms.Button):yield control
                if isinstance(control,forms.Container):
                    for child in control.Children:yield from buttons(child)
            refresh=next(b for b in buttons(d.body) if b.Text=='Refresh')
            refresh.ControlObject.ApplyTemplate()
            from System.Windows import Point
            def text_position():
                surface=refresh.ControlObject.Template.FindName('Surface',refresh.ControlObject)
                return surface.Child.TranslatePoint(Point(0,0),refresh.ControlObject)
            before=text_position()
            refresh.Focus();click(refresh);refresh.ControlObject.UpdateLayout()
            after=text_position()
            check(before.X==after.X and before.Y==after.Y,'Refresh text stays fixed after focus and click')
            check(refresh.ControlObject.FocusVisualStyle is None,'Refresh has no dotted focus rectangle')
            d.grid.SelectedRow=0
            selected_id=screen.selected_record(d.grid,d.records)['id']
            original_dialog=screen.AssignLayerDialog
            opened=[]
            def auto_assign(doc,definition_ids):
                opened.append(list(definition_ids))
                child=original_dialog(doc,definition_ids)
                timer=forms.UITimer();timer.Interval=.1
                state={'closed':False}
                def close_child(s,e):
                    if state['closed']:
                        return
                    state['closed']=True
                    timer.Stop()
                    timer.Elapsed-=close_child
                    child.Shown-=shown
                    timer.Dispose()
                    child.Close(False)
                def shown(s,e):
                    if not state['closed']:
                        timer.Start()
                timer.Elapsed+=close_child
                child.Shown+=shown
                return child
            screen.AssignLayerDialog=auto_assign
            try:
                for key_name in ('Return','Space'):
                    d.grid.SelectedRow=0
                    selected_id=screen.selected_record(d.grid,d.records)['id']
                    refresh.Focus()
                    press_key(d,key_name,refresh)
                    check(opened[-1]==[selected_id],key_name+' invokes Assign layer while Refresh has focus')
            finally:
                screen.AssignLayerDialog=original_dialog
            capture(d,'show-home-layers.png');d.Close(False)
        show(dialog,overview)

        # Repeated tokens must be distinguishable in the single selector.
        repeated=add('Building_03_Floor_03');repeated_id=place(repeated)
        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[repeated],'create',[repeated_id])
        def choose_earlier(d):
            index=next(i for i,r in enumerate(d.version_records) if r['spec'] and
                       r['spec']['prefix'].endswith('Building_') and r['spec']['token']=='03')
            d.choice.SelectedIndex=index
            check(d.result_plan['new_name']==prefix+'_Building_04_Floor_03',
                  'one selector distinguishes identical version tokens by position')
            d.Close(False)
        show(dialog,choose_earlier)

        plain=add('Plain')
        unique='RUTPlain'+''.join(chr(97+int(c,16)) for c in str(Guid.NewGuid()).replace('-',''))
        doc.InstanceDefinitions.Modify(doc.InstanceDefinitions[plain],unique,'',True)
        plain_id=place(plain)
        dialog=screen.FamilyDialog(doc,doc.InstanceDefinitions[plain],'create',[plain_id])
        def introduce(d):
            check(d.starting_panel.Visible,'unversioned source shows starting name immediately')
            d.example.Text=unique+' 001'
            check(d.result_plan['new_name']==unique+' 002','starting format is detected without a second version control')
            capture(d,'introduce-versioning.png');d.Close(False)
        show(dialog,introduce)
        print('PASSED {} visible dialog and Undo checks'.format(len(checks)))
        return checks
    finally:
        for object_id in objects:
            doc.Objects.Unlock(object_id,True);doc.Objects.Delete(object_id,True)
        # Versions created by tests share this unique prefix; delete only those.
        test_definitions=[d for d in doc.InstanceDefinitions if not d.IsDeleted and
                          (d.Name.startswith(prefix) or d.Index in indices)]
        for definition in reversed(test_definitions):
            doc.InstanceDefinitions.Delete(definition.Index,True,True)
        for layer_id in layer_ids:
            layer=doc.Layers.FindId(layer_id)
            if layer and not layer.IsDeleted:
                doc.Layers.Delete(layer.Index,True)
        doc.Objects.UnselectAll()
        for object_id in selected:
            obj=doc.Objects.FindId(object_id)
            if obj and not obj.IsDeleted:
                obj.Select(True)
        doc.Modified=modified
        doc.Views.Redraw()
        sc.doc=previous


if __name__=='__main__':
    run(__rhino_doc__)
