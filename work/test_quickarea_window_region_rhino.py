"""Verify the OS-level round window shape, not just the painted content clip."""
import ctypes
from ctypes import wintypes
import runpy
import scriptcontext as sc
import Eto.Forms as forms
from System.Windows.Interop import WindowInteropHelper

sc.doc = __rhino_doc__
q = runpy.run_path(r'C:\Projects\rhino-urbanism\QuickArea.py', run_name='qa_region_test')
ui = q['ui']
exec(compile(open(ui.__file__, encoding='utf-8').read(), ui.__file__, 'exec'), ui.__dict__)
d = q['create_result_dialog']('68 meters²', '80 meters²', 68, 80, 15, 1, 1, 1, 68, 80)
g = q['create_result_dialog'].__globals__
original_prompt = g['prompt_section_height']
errors = []
timer = forms.UITimer()
timer.Interval = 0.8


def inspect(sender, event):
    timer.Stop()
    region = None
    try:
        user32, gdi32 = ctypes.WinDLL('user32'), ctypes.WinDLL('gdi32')
        gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
        gdi32.CreateRectRgn.restype = wintypes.HANDLE
        user32.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE]
        user32.GetWindowRgn.restype = ctypes.c_int
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        gdi32.PtInRegion.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int]
        gdi32.PtInRegion.restype = wintypes.BOOL
        gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
        handle = WindowInteropHelper(d.ControlObject).Handle.ToInt64()
        region = gdi32.CreateRectRgn(0, 0, 0, 0)
        assert user32.GetWindowRgn(handle, region) > 0
        rect = wintypes.RECT()
        user32.GetWindowRect(handle, ctypes.byref(rect))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        corners = [(0,0), (width-1,0), (0,height-1), (width-1,height-1)]
        assert all(not gdi32.PtInRegion(region, x, y) for x, y in corners)
        assert gdi32.PtInRegion(region, width//2, height//2)
        g['prompt_section_height'] = lambda current: None
        d.height_button.PerformClick()
        assert d.Visible and not d.recalculate
        print('NATIVE_ROUND_CORNERS_PASS: all four corner pixels excluded from the real HWND')
        print('CANCEL_HEIGHT_PASS: existing result stays open without recalculation')
    except Exception as error:
        errors.append(str(error))
    finally:
        if region:
            gdi32.DeleteObject(region)
        g['prompt_section_height'] = original_prompt
        d.done_button.PerformClick()


timer.Elapsed += inspect
d.Shown += lambda s, e: timer.Start()
try:
    d.show_for_doc(__rhino_doc__, picking=True)
finally:
    timer.Dispose()
assert not errors, errors
