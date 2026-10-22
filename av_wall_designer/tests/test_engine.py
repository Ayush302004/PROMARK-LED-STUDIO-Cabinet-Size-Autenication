import unittest
from engine import calculate


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"product": {"width_mm": 600, "height_mm": 337.5, "pixels_w": 240, "pixels_h": 135, "environment": "indoor", "demo": True}, "unit": "m", "environment": "indoor", "wall_width": 5, "wall_height": 3, "screen_width": 4.8, "screen_height": 2.7, "mode": "dimensions", "policy": "within"}

    def test_exact_boundary(self):
        r = calculate(self.data)
        self.assertEqual((r["columns"], r["rows"], r["count"]), (8, 8, 64))
        self.assertEqual((r["pixels_w"], r["pixels_h"]), (1920, 1080))
        self.assertAlmostEqual(r["margins_m"]["left"], .1)

    def test_policies(self):
        self.data["screen_width"] = 4.7
        self.assertEqual(calculate(self.data)["columns"], 7)
        self.data["policy"] = "nearest"
        self.assertEqual(calculate(self.data)["columns"], 8)
        self.data["policy"] = "cover"
        self.assertEqual(calculate(self.data)["columns"], 8)

    def test_feet_and_metres_match(self):
        self.data.update(unit="ft", wall_width="16.404199475", wall_height="9.842519685", screen_width="15.748031496", screen_height="8.858267717")
        r = calculate(self.data)
        self.assertEqual((r["columns"], r["rows"]), (8, 8))

    def test_wall_preserved_with_overflow(self):
        self.data.update(mode="grid", columns=10, rows=10)
        r = calculate(self.data)
        self.assertFalse(r["fits"])
        self.assertEqual(r["wall_width_m"], 5)

    def test_resolution_rounds_up(self):
        self.data.update(mode="resolution", target_pixels_w=1930, target_pixels_h=1081)
        r = calculate(self.data)
        self.assertEqual((r["pixels_w"], r["pixels_h"]), (2160, 1215))

    def test_unknown_data_not_zero(self):
        self.assertIsNone(calculate(self.data)["totals"]["weight_kg"])
        self.assertIsNone(calculate(self.data)["quote"])

    def test_partial_quote(self):
        self.data.update(cabinet_price=1000, installation_cost=100, tax_percent=10)
        self.assertEqual(calculate(self.data)["quote"]["total"], 70510)

    def test_invalid_values(self):
        for value in (-1, "NaN", "Infinity", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate({**self.data, "wall_width": value})
        with self.assertRaises(ValueError):
            calculate({**self.data, "mode": "grid", "columns": 1.5, "rows": 1})

    def test_custom_offset(self):
        r = calculate({**self.data, "position": "custom", "left": .3, "bottom": .1})
        self.assertAlmostEqual(r["margins_m"]["right"], -.1)
        self.assertFalse(r["fits"])

    def test_user_screenshot_requested_vs_actual(self):
        self.data.update(unit="ft", wall_width="16.961942257", wall_height="10.433070866", screen_width="15.127952756", screen_height="8.074146982")
        r = calculate(self.data)
        self.assertEqual((r["columns"], r["rows"]), (7, 7))
        self.assertGreater(r["size_difference_m"]["width"], 0)
        self.assertAlmostEqual(r["cover_size_m"]["width"], 4.8)
        self.data["policy"] = "cover"
        r = calculate(self.data)
        self.assertEqual((r["columns"], r["rows"]), (8, 8))
        self.assertTrue(r["fits"])

    def test_exact_design_keeps_feet_input(self):
        self.data.update(unit="ft", wall_width=16, wall_height=10, screen_width="12.611", screen_height=7)
        r = calculate(self.data)
        self.assertAlmostEqual(r["design"]["width_m"] / .3048, 12.611, places=7)
        self.assertEqual(r["columns"], 6)
        self.assertAlmostEqual(r["design"]["margins_m"]["left"] / .3048, (16 - 12.611) / 2)
        self.data["screen_width"] = "12.6"
        r = calculate(self.data)
        self.assertAlmostEqual(r["design"]["width_m"] / .3048, 12.6)

    def test_snapped_cabinet_count_preserves_entered_dimensions(self):
        self.data.update(unit="ft", screen_width="13.78", screen_height="5.536")
        r = calculate(self.data)
        self.assertEqual((r["columns"], r["rows"]), (7, 5))
        self.assertAlmostEqual(r["design"]["width_m"], 13.78 * .3048)
        self.assertAlmostEqual(r["design"]["height_m"], 5.536 * .3048)
        self.assertAlmostEqual(r["size_difference_m"]["width"], 13.78 * .3048 - 4.2)
        self.assertAlmostEqual(r["size_difference_m"]["height"], 5.536 * .3048 - 1.6875)

    def test_exact_design_fit_separate_from_cabinet_fit(self):
        self.data.update(screen_width=5, screen_height=3, policy="cover")
        r = calculate(self.data)
        self.assertTrue(r["design"]["fits"])
        self.assertFalse(r["fits"])


if __name__ == "__main__":
    unittest.main()
