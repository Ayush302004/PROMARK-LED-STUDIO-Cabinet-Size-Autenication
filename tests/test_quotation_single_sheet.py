"""Quotation exports must be self-contained and preserve displayed dates."""
import json
import unittest
from io import BytesIO

from openpyxl import load_workbook

from test_mounting_quotation import BASE, pdf_content
from quotation import build_quotation, build_quotation_pdf, build_pdf_from_excel, read_excel_quotation


class SingleSheetQuotationTests(unittest.TestCase):
    def data(self, **quotation):
        catalogue = json.loads((BASE / 'catalogue.json').read_text(encoding='utf-8'))
        return {
            'product': next(p for p in catalogue if p['id'] == 'uda-ii-2-5'),
            'controller': 'HD-KV410', 'unit': 'ft', 'mode': 'dimensions',
            'wall_width': 20, 'wall_height': 20,
            'screen_width': '8.399', 'screen_height': '4.724',
            'quotation': {'date': '2026-10-31', 'wall_rate': 7250, 'gst': 18, **quotation},
        }

    def test_only_quotation_sheet_and_local_formulas(self):
        for mounting in ('none', 'unipole', 'structure'):
            with self.subTest(mounting=mounting):
                workbook = load_workbook(build_quotation(self.data(mount_type=mounting), BASE))
                self.assertEqual(workbook.sheetnames, ['Quotation'])
                sheet = workbook['Quotation']
                self.assertEqual(sheet['F10'].data_type, 'n')
                self.assertEqual(sheet['F10'].value, 287657.35)
                for row in sheet:
                    for cell in row:
                        self.assertNotEqual(cell.data_type, 'e')
                        if cell.data_type == 'f':
                            self.assertNotIn('!', cell.value)
                            self.assertNotIn('#REF!', cell.value)
                workbook.close()

    def test_cached_prices_preserve_area_precision_and_tax(self):
        workbook = load_workbook(build_quotation(self.data(), BASE), data_only=True)
        sheet = workbook['Quotation']
        self.assertEqual(sheet['F10'].value, 287657.35)
        self.assertEqual(sheet['H10'].value, 51778.32)
        self.assertEqual(sheet['I10'].value, 339435.67)
        self.assertEqual(sheet['J10'].value, 339435.67)
        self.assertIn('39.677 sq.feet', sheet['C10'].value)
        workbook.close()

    def test_rates_remain_editable_and_convert_to_pdf(self):
        workbook = load_workbook(build_quotation(self.data(mount_type='structure'), BASE))
        sheet = workbook['Quotation']
        description = sheet['C10'].value
        sheet['F10'] = 1500
        sheet['D10'] = 2
        sheet['G10'] = 0.05
        sheet['F12'] = 8000
        edited = BytesIO()
        workbook.save(edited)
        workbook.close()
        edited.seek(0)
        reopened = load_workbook(edited, data_only=True)
        self.assertEqual(reopened.sheetnames, ['Quotation'])
        self.assertEqual(reopened['Quotation']['C10'].value, description)
        _, rows, _, _, _ = read_excel_quotation(reopened['Quotation'])
        self.assertEqual(rows[0][5:], ['1,500.00', '5.00%', '75.00', '1,575.00', '3,150.00'])
        mounting = next(row for row in rows if row[1] == 'Mounting structure')
        self.assertEqual(mounting[-1], '9,440.00')
        reopened.close()
        edited.seek(0)
        content = pdf_content(build_pdf_from_excel(edited))
        self.assertIn('3,150.00', content)
        self.assertIn('9,440.00', content)

    def test_unpriced_and_zero_rates_remain_distinct(self):
        for rate, expected in ((None, None), ('', None), (0, 0)):
            with self.subTest(rate=rate):
                workbook = load_workbook(build_quotation(self.data(wall_rate=rate), BASE), data_only=True)
                sheet = workbook['Quotation']
                self.assertEqual(sheet['F10'].value, expected)
                self.assertEqual(sheet['J10'].value, expected)
                workbook.close()

    def test_day_month_year_date_in_every_export(self):
        for value, expected in (('2026-10-31', '31-10-2026'), ('09-02-2024', '09-02-2024')):
            with self.subTest(date=value):
                data = self.data(date=value)
                output = build_quotation(data, BASE)
                workbook = load_workbook(output, data_only=True)
                self.assertEqual(workbook['Quotation']['H1'].value, 'Date: ' + expected)
                workbook.close()
                self.assertIn(expected, pdf_content(build_quotation_pdf(data, BASE)))
                output.seek(0)
                self.assertIn(expected, pdf_content(build_pdf_from_excel(output)))


if __name__ == '__main__':
    unittest.main()
