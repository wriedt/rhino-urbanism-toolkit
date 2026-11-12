# -*- coding: utf-8 -*-
"""Shared screen-pixel spacing and typography for RUT viewport panels."""

# Leave the viewport title/dropdown a clear strip above the panel.
PANEL_LEFT = 32
PANEL_TOP = 48
CAPTION_PIXELS = 13
BODY_PIXELS = 15
HEADING_PIXELS = 24
VALUE_PIXELS = 28


class AquaPanel:
    """Cached, fixed viewport panel using the PushPullCurve drawing-office style."""
    WIDTH = 450
    HEIGHT = 244

    def __init__(self):
        self.bitmap = None
        self.key = None

    def contains(self, point):
        return (PANEL_LEFT <= point.X <= PANEL_LEFT + self.WIDTH and
                PANEL_TOP <= point.Y <= PANEL_TOP + self.HEIGHT)

    def dispose(self):
        if self.bitmap is not None:
            self.bitmap.Dispose()
            self.bitmap = None
        self.key = None

    def draw(self, display, title, heading, lines, footer):
        import Rhino
        import System.Drawing as sd
        from System.Drawing.Drawing2D import GraphicsPath, LinearGradientBrush, LinearGradientMode, SmoothingMode
        from System.Drawing.Text import TextRenderingHint
        dark = Rhino.Runtime.HostUtils.RunningInDarkMode
        key = (dark,title,heading,tuple(lines),footer)
        if self.key != key:
            self.dispose()
            image = sd.Bitmap(self.WIDTH,self.HEIGHT)
            graphics = sd.Graphics.FromImage(image)
            resources = []
            try:
                graphics.SmoothingMode = SmoothingMode.AntiAlias
                graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
                def colour(light,dark_value):
                    return sd.ColorTranslator.FromHtml(dark_value if dark else light)
                path = GraphicsPath()
                resources.append(path)
                for x,y,angle in [(1,1,180),(424,1,270),(424,218,0),(1,218,90)]:
                    path.AddArc(x,y,24,24,angle,90)
                path.CloseFigure()
                gradient = LinearGradientBrush(sd.RectangleF(0,0,self.WIDTH,self.HEIGHT),
                    colour('#f6f8f8','#223138'),colour('#e2f1ed','#294944'),LinearGradientMode.ForwardDiagonal)
                border = sd.Pen(colour('#c6d8da','#49616b'),1)
                resources.extend([gradient,border])
                graphics.FillPath(gradient,path)
                graphics.DrawPath(border,path)
                ink = colour('#263f4b','#e9f5f6')
                muted = colour('#526d76','#b9d0d5')
                def text(value,size,color,y,height):
                    font = sd.Font('Segoe UI',size,sd.FontStyle.Regular,sd.GraphicsUnit.Pixel)
                    brush = sd.SolidBrush(color)
                    resources.extend([font,brush])
                    graphics.DrawString(value,font,brush,sd.RectangleF(20,y,410,height))
                text(title,CAPTION_PIXELS,muted,15,22)
                graphics.DrawLine(border,sd.PointF(20,43),sd.PointF(430,43))
                text(heading,HEADING_PIXELS,ink,53,38)
                for index,line in enumerate(lines[:3]):
                    text(line,BODY_PIXELS,muted,102+index*29,26)
                text(footer,12,muted,211,22)
                self.bitmap = Rhino.Display.DisplayBitmap(image)
                self.key = key
            finally:
                for resource in reversed(resources):
                    resource.Dispose()
                graphics.Dispose()
                image.Dispose()
        display.DrawBitmap(self.bitmap,PANEL_LEFT,PANEL_TOP)
