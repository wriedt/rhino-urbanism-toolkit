#! python 3
# -*- coding: utf-8 -*-
"""Shared aqua drawing-office components for Rhino 8 Python tools."""
import Rhino
import Eto.Forms as forms
import Eto.Drawing as drawing


DARK = Rhino.Runtime.HostUtils.RunningInDarkMode


def colour(light, dark):
    return drawing.Color.Parse(dark if DARK else light)


# Exact light/dark colour pairs from the approved aqua reference.
INK = colour('#263f4b', '#e9f5f6')
MUTED = colour('#526d76', '#b9d0d5')
ACCENT = colour('#246e7b', '#b1e4df')
PAPER = colour('#f6f8f8', '#223138')
AQUA = colour('#e2f1ed', '#294944')
LINE = colour('#c6d8da', '#49616b')
FIELD = colour('#fcfefe', '#263b43')
ON_ACCENT = colour('#f5ffff', '#123d46')
BODY_SIZE, CAPTION_SIZE, TITLE_SIZE, VALUE_SIZE = 10.5, 9, 18, 24


def refresh_theme():
    """Follow appearance changes between invocations of a cached script module."""
    global DARK, INK, MUTED, ACCENT, PAPER, AQUA, LINE, FIELD, ON_ACCENT
    DARK = Rhino.Runtime.HostUtils.RunningInDarkMode
    INK = colour('#263f4b', '#e9f5f6')
    MUTED = colour('#526d76', '#b9d0d5')
    ACCENT = colour('#246e7b', '#b1e4df')
    PAPER = colour('#f6f8f8', '#223138')
    AQUA = colour('#e2f1ed', '#294944')
    LINE = colour('#c6d8da', '#49616b')
    FIELD = colour('#fcfefe', '#263b43')
    ON_ACCENT = colour('#f5ffff', '#123d46')


def label(text, size=BODY_SIZE, muted=False):
    control = forms.Label()
    control.Text = text
    control.Font = drawing.Font('Segoe UI', size)
    control.TextColor = MUTED if muted else INK
    control.BackgroundColor = drawing.Colors.Transparent
    return control


def button(text, primary=False):
    control = forms.Button()
    control.Text = text
    control.Font = drawing.Font('Segoe UI', BODY_SIZE)
    control.Height = 42
    control.BackgroundColor = ACCENT if primary else FIELD
    control.TextColor = ON_ACCENT if primary else INK
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        _round_windows_button(control, primary)
    return control


def checkbox(text):
    control = forms.CheckBox()
    control.Text = text
    control.Font = drawing.Font('Segoe UI', BODY_SIZE)
    control.TextColor = INK
    control.BackgroundColor = drawing.Colors.Transparent
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        # Eto's WPF access-label has a local foreground that overrides inheritance.
        native = control.ControlObject
        native.Content.Foreground = native.Foreground
        _theme_windows_checkbox(control)
    return control


def _theme_windows_checkbox(control):
    """Aqua checkbox, retaining native mouse, keyboard and accessibility behavior."""
    import clr
    clr.AddReference('PresentationFramework')
    from System.Windows.Markup import XamlReader
    from System.Windows.Automation import AutomationProperties
    field = '#263b43' if DARK else '#fcfefe'
    line = '#49616b' if DARK else '#c6d8da'
    accent = '#b1e4df' if DARK else '#246e7b'
    tick = '#123d46' if DARK else '#f5ffff'
    native = control.ControlObject
    native.MinHeight = 22
    native.FocusVisualStyle = None
    AutomationProperties.SetName(native, control.Text)
    template = '''<ControlTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="CheckBox">
 <Grid x:Name="Root" Background="Transparent" MinHeight="22">
  <Border x:Name="Box" Width="16" Height="16" CornerRadius="3" Background="FIELD"
   BorderBrush="LINE" BorderThickness="1" HorizontalAlignment="Left" VerticalAlignment="Center" Margin="3,0,0,0">
   <Grid>
    <Path x:Name="Tick" Data="M 2 7 L 5 10 L 11 3" Stroke="TICK" StrokeThickness="1.8"
     StrokeStartLineCap="Round" StrokeEndLineCap="Round" Visibility="Collapsed" />
    <Border x:Name="Mixed" Height="2" Margin="3,0" Background="TICK" VerticalAlignment="Center" Visibility="Collapsed" />
   </Grid>
  </Border>
  <ContentPresenter Margin="28,0,0,0" HorizontalAlignment="Left" VerticalAlignment="Center"
   RecognizesAccessKey="True" />
 </Grid>
 <ControlTemplate.Triggers>
  <Trigger Property="IsChecked" Value="True">
   <Setter TargetName="Box" Property="Background" Value="ACCENT" />
   <Setter TargetName="Box" Property="BorderBrush" Value="ACCENT" />
   <Setter TargetName="Tick" Property="Visibility" Value="Visible" />
  </Trigger>
  <Trigger Property="IsChecked" Value="{x:Null}">
   <Setter TargetName="Box" Property="Background" Value="ACCENT" />
   <Setter TargetName="Mixed" Property="Visibility" Value="Visible" />
  </Trigger>
  <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Box" Property="BorderBrush" Value="ACCENT" /></Trigger>
  <Trigger Property="IsEnabled" Value="False"><Setter TargetName="Root" Property="Opacity" Value="0.45" /></Trigger>
 </ControlTemplate.Triggers>
</ControlTemplate>'''
    for key, colour in [('FIELD', field), ('LINE', line), ('ACCENT', accent), ('TICK', tick)]:
        template = template.replace(key, colour)
    native.Template = XamlReader.Parse(template)


def theme_slider(control):
    """Aqua track and round thumb, retaining native slider input semantics."""
    if not Rhino.Runtime.HostUtils.RunningOnWindows:
        return
    import clr
    clr.AddReference('PresentationFramework')
    from System.Windows.Markup import XamlReader
    from System.Windows.Automation import AutomationProperties
    accent = '#b1e4df' if DARK else '#246e7b'
    track = '#49616b' if DARK else '#c6d8da'
    field = '#263b43' if DARK else '#fcfefe'
    native = control.ControlObject
    native.FocusVisualStyle = None
    native.IsMoveToPointEnabled = True
    native.SmallChange = 1
    native.LargeChange = 1
    AutomationProperties.SetName(native, 'Decimal places')
    native.Template = XamlReader.Parse('''
<ControlTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="Slider">
 <Grid Background="Transparent" Margin="2,0">
  <Grid.RowDefinitions><RowDefinition Height="20" /><RowDefinition Height="4" /></Grid.RowDefinitions>
  <Track x:Name="PART_Track" Orientation="Horizontal"
   Minimum="{TemplateBinding Minimum}" Maximum="{TemplateBinding Maximum}"
   Value="{TemplateBinding Value}">
   <Track.DecreaseRepeatButton><RepeatButton Command="{x:Static Slider.DecreaseLarge}" Focusable="False">
    <RepeatButton.Template><ControlTemplate><Border Height="4" CornerRadius="2" Background="''' + accent + '''" /></ControlTemplate></RepeatButton.Template>
   </RepeatButton></Track.DecreaseRepeatButton>
   <Track.Thumb><Thumb Width="16" Height="16">
    <Thumb.Template><ControlTemplate TargetType="Thumb">
     <Border x:Name="Grip" CornerRadius="8" Background="''' + accent + '''"
      BorderBrush="''' + field + '''" BorderThickness="2" />
     <ControlTemplate.Triggers>
      <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Grip" Property="BorderThickness" Value="1" /></Trigger>
      <Trigger Property="IsDragging" Value="True"><Setter TargetName="Grip" Property="BorderThickness" Value="1" /></Trigger>
     </ControlTemplate.Triggers>
    </ControlTemplate></Thumb.Template>
   </Thumb></Track.Thumb>
   <Track.IncreaseRepeatButton><RepeatButton Command="{x:Static Slider.IncreaseLarge}" Focusable="False">
    <RepeatButton.Template><ControlTemplate><Border Height="4" CornerRadius="2" Background="''' + track + '''" /></ControlTemplate></RepeatButton.Template>
   </RepeatButton></Track.IncreaseRepeatButton>
  </Track>
  <TickBar Grid.Row="1" Height="3" Placement="Bottom" Fill="''' + track + '''"
   Minimum="{TemplateBinding Minimum}" Maximum="{TemplateBinding Maximum}"
   TickFrequency="1" ReservedSpace="16" />
 </Grid>
 <ControlTemplate.Triggers>
  <Trigger Property="IsEnabled" Value="False"><Setter Property="Opacity" Value="0.45" /></Trigger>
 </ControlTemplate.Triggers>
</ControlTemplate>''')


def set_button_selected(control, selected):
    control.BackgroundColor = ACCENT if selected else FIELD
    control.TextColor = ON_ACCENT if selected else INK
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        from System.Windows.Automation import AutomationProperties
        padding = control.ControlObject.Padding
        _round_windows_button(control, selected)
        control.ControlObject.Padding = padding
        AutomationProperties.SetItemStatus(control.ControlObject, 'Selected' if selected else '')


def copy_text_to_clipboard(text):
    forms.Clipboard.Instance.Text = text


def theme_scrollbars(control):
    """Scope native rounded aqua scrollbars to this control and its descendants."""
    if not Rhino.Runtime.HostUtils.RunningOnWindows:
        return
    import clr
    clr.AddReference('PresentationFramework')
    from System.Windows.Markup import XamlReader
    from System.Windows.Controls.Primitives import ScrollBar
    track_colour = '#223138' if DARK else '#e2f1ed'
    thumb_colour = '#b1e4df' if DARK else '#246e7b'

    def template(vertical):
        orientation = 'Vertical' if vertical else 'Horizontal'
        reverse = 'True' if vertical else 'False'
        before, after = ('PageUpCommand', 'PageDownCommand') if vertical else ('PageLeftCommand', 'PageRightCommand')
        minimum = 'MinHeight="24"' if vertical else 'MinWidth="24"'
        return '''<ControlTemplate TargetType="ScrollBar">
 <Border Background="''' + track_colour + '''" CornerRadius="6" Padding="3">
  <Track x:Name="PART_Track" Orientation="''' + orientation + '''" IsDirectionReversed="''' + reverse + '''"
   Minimum="{TemplateBinding Minimum}" Maximum="{TemplateBinding Maximum}"
   Value="{TemplateBinding Value}" ViewportSize="{TemplateBinding ViewportSize}">
   <Track.DecreaseRepeatButton><RepeatButton Command="{x:Static ScrollBar.''' + before + '''}" Focusable="False">
    <RepeatButton.Template><ControlTemplate><Border Background="Transparent" /></ControlTemplate></RepeatButton.Template>
   </RepeatButton></Track.DecreaseRepeatButton>
   <Track.Thumb><Thumb ''' + minimum + '''>
    <Thumb.Template><ControlTemplate TargetType="Thumb">
     <Border x:Name="Grip" Background="''' + thumb_colour + '''" CornerRadius="3" Opacity="0.75" />
     <ControlTemplate.Triggers>
      <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Grip" Property="Opacity" Value="1" /></Trigger>
      <Trigger Property="IsDragging" Value="True"><Setter TargetName="Grip" Property="Opacity" Value="1" /></Trigger>
     </ControlTemplate.Triggers>
    </ControlTemplate></Thumb.Template>
   </Thumb></Track.Thumb>
   <Track.IncreaseRepeatButton><RepeatButton Command="{x:Static ScrollBar.''' + after + '''}" Focusable="False">
    <RepeatButton.Template><ControlTemplate><Border Background="Transparent" /></ControlTemplate></RepeatButton.Template>
   </RepeatButton></Track.IncreaseRepeatButton>
  </Track>
 </Border>
</ControlTemplate>'''

    style = XamlReader.Parse('''<Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="ScrollBar">
 <Setter Property="Width" Value="12" />
 <Setter Property="Template"><Setter.Value>''' + template(True) + '''</Setter.Value></Setter>
 <Style.Triggers><Trigger Property="Orientation" Value="Horizontal">
  <Setter Property="Width" Value="Auto" /><Setter Property="Height" Value="12" />
  <Setter Property="Template"><Setter.Value>''' + template(False) + '''</Setter.Value></Setter>
 </Trigger></Style.Triggers>
</Style>''')
    control.ControlObject.Resources[clr.GetClrType(ScrollBar)] = style


def _round_windows_button(control, primary):
    """Style the real WPF Button; retain native keyboard/accessibility behavior."""
    import clr
    clr.AddReference('PresentationFramework')
    from System.Windows.Markup import XamlReader
    from System.Windows import Thickness
    from System.Windows.Media import SolidColorBrush, Color as MediaColor
    native = control.ControlObject
    native.UseLayoutRounding = True
    native.SnapsToDevicePixels = True
    native.Padding = Thickness(14, 8, 14, 8)
    border = (
        '#b1e4df' if DARK and primary else '#49616b' if DARK else
        '#246e7b' if primary else '#c6d8da')
    native.BorderBrush = SolidColorBrush(MediaColor.FromRgb(
        int(border[1:3], 16), int(border[3:5], 16), int(border[5:7], 16)))
    hover = ('#c4eeea' if primary else '#304c54') if DARK else (
        '#1d616d' if primary else '#edf5f3')
    # A same-colour stroke and fill create a dark antialiasing seam along
    # WPF Border's inner corner. Filled buttons need only one painted shape.
    thickness = '0' if primary else '1'
    native.FocusVisualStyle = None
    native.Template = XamlReader.Parse('''
<ControlTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
 xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="Button">
 <Border x:Name="Surface" CornerRadius="6" BorderThickness="''' + thickness + '''"
  BorderBrush="{TemplateBinding BorderBrush}" Background="{TemplateBinding Background}"
  Padding="{TemplateBinding Padding}" SnapsToDevicePixels="True">
  <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"
   RecognizesAccessKey="True" />
 </Border>
 <ControlTemplate.Triggers>
  <Trigger Property="IsMouseOver" Value="True">
   <Setter TargetName="Surface" Property="Background" Value="''' + hover + '''" />
  </Trigger>
  <Trigger Property="IsPressed" Value="True">
   <Setter TargetName="Surface" Property="Opacity" Value="0.8" />
  </Trigger>
  <Trigger Property="IsEnabled" Value="False">
   <Setter TargetName="Surface" Property="Opacity" Value="0.45" />
  </Trigger>
 </ControlTemplate.Triggers>
</ControlTemplate>''')


def divider():
    control = forms.Panel()
    control.Height = 1
    control.BackgroundColor = LINE
    return control


class AquaSurface(forms.Drawable):
    """A real Eto gradient behind transparent native controls, with DPI scaling."""
    def __init__(self):
        super().__init__()
        self.BackgroundColor = PAPER
        self.Paint += self._paint
        self.SizeChanged += lambda s, e: self.Invalidate()

    def _paint(self, sender, event):
        width, height = self.Width, self.Height
        if width <= 0 or height <= 0:
            return
        brush = drawing.LinearGradientBrush(
            PAPER, AQUA, drawing.PointF(0, 0), drawing.PointF(width, height))
        try:
            event.Graphics.FillRectangle(brush, 0, 0, width, height)
        finally:
            brush.Dispose()


class InfoPanel(forms.Panel if Rhino.Runtime.HostUtils.RunningOnWindows else forms.Drawable):
    """Rounded, opaque information surface matching the reference's fields."""
    def __init__(self, content, padding=18):
        super().__init__()
        self.BackgroundColor = FIELD
        self.Padding = drawing.Padding(padding)
        self.Content = content
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import Thickness, CornerRadius
            from System.Windows.Media import SolidColorBrush, Color as MediaColor
            native = self.ControlObject
            native.BorderThickness = Thickness(1)
            native.CornerRadius = CornerRadius(8)
            native.BorderBrush = SolidColorBrush(MediaColor.FromRgb(
                *([73, 97, 107] if DARK else [198, 216, 218])))
            native.UseLayoutRounding = True
            native.SnapsToDevicePixels = True
        else:
            self.Paint += self._paint
            self.SizeChanged += lambda s, e: self.Invalidate()

    def _paint(self, sender, event):
        if self.Width <= 1 or self.Height <= 1:
            return
        path = drawing.GraphicsPath.GetRoundRect(
            drawing.RectangleF(1.5, 1.5, self.Width - 3, self.Height - 3), 8)
        pen = drawing.Pen(LINE, 1)
        try:
            event.Graphics.FillPath(FIELD, path)
            event.Graphics.DrawPath(pen, path)
        finally:
            pen.Dispose()
            path.Dispose()


def content_layout(spacing=10):
    layout = forms.DynamicLayout()
    layout.Spacing = drawing.Size(12, spacing)
    layout.BackgroundColor = drawing.Colors.Transparent
    return layout


class _AquaWindow:
    """Common header, content, actions and status; tied to the calling document."""
    def __init__(self, title, category, heading, description):
        refresh_theme()
        self.Title = 'RUT | ' + title
        self.WindowStyle = forms.WindowStyle.NONE
        self.MovableByWindowBackground = True
        self.Resizable = False
        self.Padding = drawing.Padding(0)
        self.BackgroundColor = PAPER
        self.MinimumSize = drawing.Size(450, 0)
        self.surface = AquaSurface()
        self.body = forms.DynamicLayout()
        self.body.Padding = drawing.Padding(24)
        self.body.Spacing = drawing.Size(12, 16)
        self.body.BackgroundColor = drawing.Colors.Transparent
        self.header = content_layout(0)
        brand = label('RUT | ' + category.split('/')[-1].strip(), CAPTION_SIZE, True)
        brand.VerticalAlignment = forms.VerticalAlignment.Center
        self.close_button = button('×')
        self.close_button.Width = 30
        self.close_button.Height = 30
        self.close_button.ToolTip = 'Close'
        self.close_button.Click += lambda s, e: self.Close(False)
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows import Thickness
            from System.Windows.Automation import AutomationProperties
            self.close_button.ControlObject.Padding = Thickness(0)
            AutomationProperties.SetName(self.close_button.ControlObject, 'Close window')
        self.header.AddRow(brand, None, self.close_button)
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            self.header.ControlObject.MouseLeftButtonDown += self._drag_header
        self.body.AddRow(self.header)
        self.body.AddRow(divider())
        if heading:
            self.body.AddRow(label(heading, TITLE_SIZE))
        if description:
            self.body.AddRow(label(description, BODY_SIZE, True))
        self.surface.Content = self.body
        self.Content = self.surface
        if Rhino.Runtime.HostUtils.RunningOnWindows:
            from System.Windows.Media import Brushes
            native = self.ControlObject
            native.AllowsTransparency = True
            native.Background = Brushes.Transparent
            native.Content.SizeChanged += self._clip_window_corners
            native.SizeChanged += lambda s, e: self._apply_window_region()
        self.status = label('', CAPTION_SIZE, True)
        self.status.Visible = False
        self.Shown += self._focus_default

    def _clip_window_corners(self, sender, event):
        from System.Windows import Rect
        from System.Windows.Media import RectangleGeometry
        content = self.ControlObject.Content
        if content.ActualWidth > 0 and content.ActualHeight > 0:
            content.Clip = RectangleGeometry(
                Rect(0, 0, content.ActualWidth, content.ActualHeight), 12, 12)
            self._apply_window_region()

    def _apply_window_region(self):
        """Clip the HWND itself so no rectangular WPF backing shows at corners."""
        if not Rhino.Runtime.HostUtils.RunningOnWindows:
            return
        import ctypes
        from ctypes import wintypes
        from System.Windows.Interop import WindowInteropHelper
        from System.Windows.Media import VisualTreeHelper
        handle = WindowInteropHelper(self.ControlObject).Handle.ToInt64()
        if not handle:
            return
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
        user32.SetWindowRgn.restype = ctypes.c_int
        gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        gdi32.CreateRoundRectRgn.restype = wintypes.HANDLE
        gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        gdi32.DeleteObject.restype = wintypes.BOOL
        rect = wintypes.RECT()
        if not user32.GetWindowRect(handle, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        dpi = VisualTreeHelper.GetDpi(self.ControlObject)
        region = gdi32.CreateRoundRectRgn(0, 0, rect.right - rect.left + 1,
            rect.bottom - rect.top + 1, round(24 * dpi.DpiScaleX), round(24 * dpi.DpiScaleY))
        if not region:
            raise ctypes.WinError(ctypes.get_last_error())
        # Windows owns this region on success, including releasing a replaced one.
        if not user32.SetWindowRgn(handle, region, True):
            gdi32.DeleteObject(region)
            raise ctypes.WinError(ctypes.get_last_error())

    def _focus_default(self, sender, event):
        self._apply_window_region()
        if getattr(self, 'DefaultButton', None) is not None and self.DefaultButton.Enabled:
            self.DefaultButton.Focus()

    def _drag_header(self, sender, event):
        from System.Windows.Input import Mouse, MouseButtonState
        if Mouse.LeftButton == MouseButtonState.Pressed:
            event.Handled = True
            self.ControlObject.DragMove()

    def finish(self, actions, status=''):
        self.body.AddRow(actions)
        self.status.Text = status
        self.status.Visible = bool(status)
        self.body.AddRow(self.status)

    def set_status(self, text):
        self.status.Text = text
        self.status.Visible = bool(text)

    def show_for_doc(self, doc, picking=False):
        parent = Rhino.UI.RhinoEtoApp.MainWindowForDocument(doc)
        if picking:
            return Rhino.UI.EtoExtensions.ShowSemiModal[bool](self, doc, parent)
        return self.ShowModal(parent)

class AquaDialog(forms.Dialog[bool]):
    """Modal/semi-modal aqua window."""
    def __init__(self, title, category, heading, description):
        super().__init__()
        _AquaWindow.__init__(self, title, category, heading, description)


class AquaForm(forms.Form):
    """Modeless aqua window using the same styling as command dialogs."""
    def __init__(self, title, category, heading, description):
        super().__init__()
        _AquaWindow.__init__(self, title, category, heading, description)

    def Close(self, result=False):
        return super().Close()

    def show_for_doc(self, doc, picking=False):
        Rhino.UI.EtoExtensions.Show(self, doc)


# Python.NET cannot mix Python and .NET base classes. Share the window methods
# explicitly while retaining the native Eto dialog/form types.
for _window_type in (AquaDialog, AquaForm):
    for _method in ('_clip_window_corners', '_apply_window_region', '_focus_default',
                    '_drag_header', 'finish', 'set_status'):
        setattr(_window_type, _method, getattr(_AquaWindow, _method))
AquaDialog.show_for_doc = _AquaWindow.show_for_doc


def action_row(*controls):
    row = forms.DynamicLayout()
    row.Spacing = drawing.Size(8, 8)
    row.BackgroundColor = drawing.Colors.Transparent
    row.AddRow(None, *controls)
    return row


def message_dialog(doc, title, heading, text):
    dlg = AquaDialog(title, 'Measurement / QuickArea', heading, '')
    detail = forms.TextArea()
    detail.Text = text
    detail.ReadOnly = True
    detail.Wrap = True
    detail.Size = drawing.Size(410, 180)
    detail.Font = drawing.Font('Segoe UI', BODY_SIZE)
    detail.TextColor = INK
    detail.BackgroundColor = FIELD
    theme_scrollbars(detail)
    if Rhino.Runtime.HostUtils.RunningOnWindows:
        from System.Windows import Thickness
        detail.ControlObject.BorderThickness = Thickness(0)
    dlg.body.AddRow(InfoPanel(detail))
    done = button('Close', True)
    done.Click += lambda s, e: dlg.Close(True)
    dlg.DefaultButton = done
    dlg.AbortButton = done
    dlg.finish(action_row(done), 'Review the geometry before relying on the total.')
    dlg.show_for_doc(doc)
