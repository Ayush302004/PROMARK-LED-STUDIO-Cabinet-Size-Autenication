import json
from pathlib import Path
import unittest
from engine import calculate


class DefaultsTests(unittest.TestCase):
    def test_model_defaults_and_step_counts(self):
        products = json.loads((Path(__file__).resolve().parents[1] / 'catalogue.json').read_text(encoding='utf-8'))
        for product in products:
            for unit in ('m', 'ft'):
                defaults = product['design_defaults'][unit]
                for increments in (0, 1, 2, 10):
                    with self.subTest(model=product['name'], unit=unit, increments=increments):
                        result = calculate(dict(product=product, environment=product['environment'], unit=unit,
                            wall_width=5 if unit == 'm' else 16.4, wall_height=3 if unit == 'm' else 9.84,
                            mode='dimensions', policy='nearest',
                            screen_width=round(defaults['width'] + increments * defaults['width_step'], 4),
                            screen_height=round(defaults['height'] + increments * defaults['height_step'], 4)))
                        self.assertEqual(result['columns'], increments + 1)
                        self.assertEqual(result['rows'], increments + 1)
                        self.assertEqual(result['pixels_w'], None if product['pixels_w'] is None else (increments + 1) * product['pixels_w'])
                        self.assertEqual(result['pixels_h'], None if product['pixels_h'] is None else (increments + 1) * product['pixels_h'])


    def test_requested_decimal_text_is_retained(self):
        product = json.loads((Path(__file__).resolve().parents[1] / 'catalogue.json').read_text(encoding='utf-8'))[0]
        result = calculate(dict(product=product, environment='indoor', unit='m', wall_width=5, wall_height=3, mode='dimensions', policy='nearest', screen_width='0.640000000123', screen_height='0.480000000456'))
        self.assertEqual(result['requested']['width_input'], '0.640000000123')
        self.assertEqual(result['requested']['width_m_exact'], '0.640000000123')
        self.assertEqual(result['requested']['height_m_exact'], '0.480000000456')


if __name__ == '__main__':
    unittest.main()
