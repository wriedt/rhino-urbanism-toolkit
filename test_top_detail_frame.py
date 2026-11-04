"""Exercise movement restrictions without pretending to run Rhino integration."""
import ast
import math
from pathlib import Path
import unittest

source = Path(__file__).with_name("TopDetailFrame.py").read_text(encoding="utf-8")
tree = ast.parse(source)
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "xy_translation")
namespace = {"math": math}
exec(compile(ast.Module(body=[function], type_ignores=[]), "TopDetailFrame.py", "exec"), namespace)
translation = namespace["xy_translation"]


class TranslationTests(unittest.TestCase):
    frame = [(0., 0., 0.), (20., 0., 0.), (20., 10., 0.), (0., 10., 0.), (0., 0., 0.)]

    def test_pan_and_undo(self):
        moved = [(x + 12.5, y - 3., z) for x, y, z in self.frame]
        self.assertEqual(translation(self.frame, moved, 1e-6), (12.5, -3., 0.))
        self.assertEqual(translation(moved, self.frame, 1e-6), (-12.5, 3., 0.))

    def test_reject_scale_rotation_and_vertical(self):
        for changed in ([ (2*x, 2*y, z) for x,y,z in self.frame ],
                        [ (-y, x, z) for x,y,z in self.frame ],
                        [ (x, y, z+1) for x,y,z in self.frame ]):
            with self.assertRaises(ValueError):
                translation(self.frame, changed, 1e-6)

    def test_reject_vertex_edit_and_open_frame(self):
        edited = list(self.frame)
        edited[2] = (22., 10., 0.)
        for changed in (edited, self.frame[:-1]):
            with self.assertRaises(ValueError):
                translation(self.frame, changed, 1e-6)

    def test_large_coordinates_small_pan(self):
        a = [(x+700000, y+6200000, z) for x,y,z in self.frame]
        b = [(x+.125, y-.25, z) for x,y,z in a]
        self.assertEqual(translation(a, b, 1e-6), (.125, -.25, 0.))

    def test_invalid_coordinates(self):
        edited = list(self.frame)
        edited[1] = (float("nan"), 0., 0.)
        with self.assertRaises(ValueError):
            translation(self.frame, edited, 1e-6)


if __name__ == "__main__":
    unittest.main()
