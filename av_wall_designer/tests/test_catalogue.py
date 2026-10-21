import json
from pathlib import Path
import unittest
from engine import calculate


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.products = [p for p in json.loads((Path(__file__).resolve().parents[1] / "catalogue.json").read_text(encoding="utf-8")) if p["id"].startswith(("uda-", "umate-"))]

    def data(self, product, **changes):
        return dict(product=product, environment=product["environment"], unit="m", wall_width=6, wall_height=4, mode="grid", columns=5, rows=4, **changes)

    def test_supplied_geometry_and_pixel_settings(self):
        self.assertEqual(len(self.products), 4)
        for p in self.products:
            with self.subTest(model=p["name"]):
                r = calculate(self.data(p))
                self.assertEqual(r["count"], 20)
                outdoor = p["environment"] == "outdoor"
                self.assertAlmostEqual(r["width_m"], 4.8 if outdoor else 3.2)
                self.assertAlmostEqual(r["height_m"], 3.84 if outdoor else 1.92)
                self.assertEqual(r["pixels_w"], 5 * p["pixels_w"])
                self.assertEqual(r["pixels_h"], 4 * p["pixels_h"])
                self.assertIsNone(r["totals"]["maximum_w"])
                self.assertFalse(p["demo"])

    def test_resolution_requires_confirmed_counts(self):
        data = self.data({**self.products[0], "pixels_w": None, "pixels_h": None})
        data.update(mode="resolution", target_pixels_w=1920, target_pixels_h=1080)
        with self.assertRaisesRegex(ValueError, "confirmed cabinet pixel"):
            calculate(data)
        data["product"] = {**data["product"], "pixels_w": 512, "pixels_h": 384}
        result = calculate(data)
        self.assertEqual((result["columns"], result["rows"]), (4, 3))
        self.assertEqual((result["pixels_w"], result["pixels_h"]), (2048, 1152))

    def test_partial_resolution_rejected(self):
        p = {**self.products[0], "pixels_w": 512, "pixels_h": None}
        with self.assertRaisesRegex(ValueError, "both cabinet pixel"):
            calculate(self.data(p))

    def test_exact_feet_and_buildable_option(self):
        data = self.data(self.products[0])
        data.update(unit="ft", wall_width=16, wall_height=10, mode="dimensions", screen_width="12.611", screen_height=7, policy="within")
        r = calculate(data)
        self.assertEqual((r["columns"], r["rows"]), (6, 4))
        self.assertAlmostEqual(r["design"]["width_m"] / .3048, 12.611)
        self.assertAlmostEqual(r["width_m"], 3.84)


    def test_each_model_has_its_own_picture(self):
        root = Path(__file__).resolve().parents[1] / "static"
        images = [p["image"] for p in self.products]
        self.assertEqual(len(set(images)), 4)
        for image in images:
            self.assertTrue((root / image).is_file(), image)


    def test_pixels_match_pitch_and_known_counts(self):
        expected = {"uda-ii-1-2": (512, 384), "uda-ii-1-5": (416, 312), "uda-ii-1-8": (344, 258), "uda-ii-2-5": (256, 192), "umate-sf4": (216, 216)}
        for p in self.products:
            self.assertEqual((p["pixels_w"], p["pixels_h"]), expected[p["id"]])
            self.assertLessEqual(abs(p["width_mm"] / p["pixels_w"] - p["pitch_mm"]), 0.05)

    def test_7_by_5_in_feet_is_3584_by_1920_and_exact_area(self):
        p = self.products[0]
        r = calculate(dict(product=p, environment="indoor", unit="ft", wall_width=16.4, wall_height=9.84, mode="dimensions", policy="within", screen_width="14.6982", screen_height="7.874"))
        self.assertEqual((r["columns"], r["rows"]), (7, 5))
        self.assertEqual((r["pixels_w"], r["pixels_h"]), (3584, 1920))
        self.assertAlmostEqual(r["design"]["area_m2"], 7 * 0.64 * 5 * 0.48, places=9)


    def test_3_decimal_feet_still_snap_to_whole_cabinets(self):
        p = self.products[0]
        r = calculate(dict(product=p, environment="indoor", unit="ft", wall_width=16.4, wall_height=9.84, mode="dimensions", policy="within", screen_width="14.698", screen_height="7.874"))
        self.assertEqual((r["columns"], r["rows"]), (7, 5))
        self.assertEqual((r["pixels_w"], r["pixels_h"]), (3584, 1920))


if __name__ == "__main__":
    unittest.main()
