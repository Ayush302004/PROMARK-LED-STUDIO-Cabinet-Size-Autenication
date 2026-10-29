"""Editable quotation matching the supplied reference layout."""
import json
import math
import re
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from decimal import Decimal, InvalidOperation
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.properties import CalcProperties
from engine import calculate 

# Quotation wording supplied in the user's four reference screenshots.
# Kept separate from native cabinet geometry and catalogue specifications.
REFERENCE_QUOTES = {
    'uda-ii-1-5': ('SMD', 'Indoor', '1.5', '208x104=21632', '422500', 'W320mmxH160mm', 'IP30', '600', '5000:1'),
    'uda-ii-2-5': ('SMD', 'Indoor', '2.5', '128x64=8192', '160000', 'W320mmxH160mm', 'IP30', '400-800', '5000:1'),
    'uda-ii-1-2': ('COB', 'Indoor', '1.2', '480x270', '640000', 'W300mmxH168mm', 'IP65', '600', '≥5000:1'),
    'pm-1-2-cob': ('COB', 'Indoor', '1.2', '480x270', '640000', 'W300mmxH168mm', 'IP65', '600', '≥5000:1'),
    'pm-3-9-smd': ('SMD', 'Outdoor', '4', '80x40=3200', '62500', 'W320mmxH160mm', 'IP65 (Front), IP54 (Rear)', '6000', '5000:1'),
}

def reference_description(product, width, height, unit, area):
    profile = REFERENCE_QUOTES.get(product.get('id'))
    if profile is None:
        return None
    tech, location, pitch, pixels, density, size, ip, brightness, contrast = profile
    return (f'Supply of {tech} {location} LED video wall ({width}W x {height}H {unit} = {area} sq.feet). '
            f'Pixel Pitch: {pitch}mm.\n'
            f'Module Resolution: (WxH): {pixels} Pixels.\n'
            f'Pixel density (pixels/sq.m.): {density} dot/m².\n'
            f'Module Size (WxH): {size}.\n'
            f'Ingress Protection: {ip}. Brightness: {brightness} cd/m².\n'
            f'Contrast Ratio: {contrast}. Refresh Rate: 3840Hz.\n'
            'Video Support: 2K, 4K. Life Span (hrs): 100000hrs.')

COMPANY_FOOTER = {
    'corporate': 'Promark Corporate Mansion, Plot No E-250, Industrial Area 8-B, Mohali, Punjab, India-160071',
    'factory': 'Village Baddi Madouli, Morinda By-Pass. Adjoining Preet Palace, Ludhiana Highway (NH-95), Morinda, Distt Ropar, Punjab, India -140101',
    'sales': 'Tower-5, Office No-414, RPS 12th Avenue, Adjoining Sarai Metro Station, Faridabad (NCR)-121001 India',
    'cin': 'U3109PB2010PTC034337',
    'gstin': '03AAFCP7669C1Z5',
    'pan': 'AAFCP7669C',
}

TERMS = [
'Order should be placed in the name of M/s Promark Techsolutions Pvt. Ltd.',
'Prices are for supply and installation including taxes.',
'Freight prices extra as applicable.', 'Electrical Work is not included.',
'Civil Work is not included.', 'Scaffolding is not included.',
'Power points, UPS and backup power required for AV system shall be provided by others / electrical contractor.',
'LAN ports for AV System as required shall be provided by others.',
'Cable and speaker quantities may vary and charges shall be as per actual.']

def text(value):
    s=str(value or '')[:16000]
    return "'"+s if s.startswith(('=','+','-','@')) else s


def strip_controller_names(description, controllers):
    """Remove known controller names/models while preserving all specifications."""
    cleaned = ' '.join(str(description or '').split())
    names = set()
    for controller in controllers:
        for key in ('name', 'model', 'id'):
            value = str(controller.get(key, '')).strip()
            if value and len(value) >= 3:
                names.add(value)
        names.update(str(value).strip() for value in controller.get('legacy_names', []) if str(value).strip())
    for name in sorted(names, key=len, reverse=True):
        cleaned = re.sub(re.escape(name) + r'\s*,?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'Controller\s+supporting', 'Controller, supporting', cleaned, flags=re.I)
    cleaned = re.sub(r'Controller\s*,\s*,+', 'Controller,', cleaned, flags=re.I)
    cleaned = re.sub(r'Controller\s*,?\s+(?=[Ss]upporting)', 'Controller, ', cleaned)
    return re.sub(r'\s{2,}', ' ', cleaned).strip()


def canonical_controller_description(description, controllers):
    """Use the selected controller's exact specification text when a known name appears."""
    text_value = ' '.join(str(description or '').split())
    for controller in controllers:
        identifiers = [controller.get('name'), controller.get('model'), controller.get('id')]
        identifiers += controller.get('legacy_names', [])
        if any(str(identifier).strip() and re.search(re.escape(str(identifier).strip()), text_value, re.I)
               for identifier in identifiers if identifier):
            return strip_controller_names(controller.get('description'), controllers)
    return strip_controller_names(text_value, controllers)

def numeric(value,label,default=None,maximum=1e12):
    if value in ('',None):return default
    try:n=Decimal(str(value))
    except (InvalidOperation,TypeError):raise ValueError(f'{label} must be numeric')
    if not n.is_finite() or n<0 or n>Decimal(str(maximum)):raise ValueError(f'Invalid {label}')
    return float(n)

def selected_specification_sheets(product):
    """Use only reference sheets matching the selected LED technology."""
    selected=product.get('technology')
    if not selected:
        match=re.search(r'COB|SMD',str(product.get('name','')),re.I)
        selected=match.group().upper() if match else None
    for sheet in product.get('supplied_specifications',[]):
        specs=sheet.get('specs',{})
        label=' '.join(str(value or '') for value in (sheet.get('technology'),sheet.get('model'),specs.get('LAMP Type'),specs.get('LED Type'),specs.get('Technology')))
        match=re.search(r'COB|SMD',label,re.I)
        technology=match.group().upper() if match else None
        if not selected or not technology or technology==str(selected).upper():
            yield sheet

def sheet_quotation_details(product):
    """Use matching supplied sheets; indoor references cannot rate outdoor models."""
    aliases = {
        'Module Resolution': ('Module Resolution', 'Module Resolution (W×H)', 'Module Pixels'),
        'Pixel Density': ('Pixel Density', 'Pixel Density (Pixels/Sq.m.)', 'Pixel density (dot/m²)'),
        'Module Size': ('Module Size (W×H)', 'Module Dimension (W×H×D)', 'Module — Size (mm)'),
        'Contrast Ratio': ('Contrast Ratio', 'Contrast (illumination 10 Lux)'),
        'Video Support': ('Video Support',),
        'Life Span': ('Life Span', 'Life Span (hrs)', 'Lifetime Typical Value'),
    }
    specs = {}
    for sheet in selected_specification_sheets(product):
        if product.get('environment') == 'outdoor' and 'indoor' in sheet.get('model', '').lower():
            continue
        specs.update(sheet.get('specs', {}))
    if not product.get('ip_rating'):
        aliases['Ingress Protection'] = ('Ingress Protection', 'IP Rating', 'IP protection level')
    lines = []
    required = {'Pixel Density', 'Contrast Ratio', 'Video Support', 'Life Span'}
    for label, keys in aliases.items():
        value = next((specs[k] for k in keys if specs.get(k)), None)
        if value is not None or label in required:
            lines.append(f'{label}: {value if value is not None else "Not provided"}.')
    return '\n'.join(lines)

def build_quotation(data,base):
    result=calculate(data);p=data['product'];q=data.get('quotation') or {}
    if not isinstance(q,dict):raise ValueError('Invalid quotation details')
    q=dict(q)
    controllers=json.loads((Path(base)/'controllers.json').read_text(encoding='utf-8'))
    controller=next((c for c in controllers if c['id']==data.get('controller')),None)
    if data.get('controller') and not controller:
        raise ValueError('This controller is no longer available. Select a current PROMARK controller before downloading.')
    controller_desc=' '.join(str((controller or {}).get('description') or q.get('controller_description') or 'Supply of LED Wall Controller. Capacity and compatibility to be confirmed.').split())
    controller_desc=strip_controller_names(controller_desc, controllers)
    q.pop('controller_rate', None)
    if 'wall_rate' not in q:q['wall_rate']=p.get('base_rate_sqft')
    gst=numeric(q.get('gst'),'GST',18,100)/100
    wb=Workbook();ws=wb.active;ws.title='Quotation';wb.calculation=CalcProperties(calcId=191029,fullCalcOnLoad=True)
    widths=[6,22,80,7,9,16,9,16,17,18]
    for i,width in enumerate(widths,1):ws.column_dimensions[chr(64+i)].width=width
    ws.sheet_view.showGridLines=True
    ws.sheet_view.showRowColHeaders=True
    ws.print_options.gridLines=True
    ws.print_options.gridLinesSet=True
    def merged(row,start,end,value,bold=False):
        ws.merge_cells(start_row=row,start_column=start,end_row=row,end_column=end)
        cell=ws.cell(row,start,text(value));cell.font=Font(name='Calibri',size=11,bold=bold);cell.alignment=Alignment(vertical='center',wrap_text=True)
    merged(1,1,7,'Client Name: '+str(q.get('client','')))
    merged(1,8,10,'Date: '+str(q.get('date') or date.today().isoformat()))
    merged(2,1,7,'Project Detail: '+str(q.get('project') or 'Quotation of Video Wall'))
    merged(2,8,10,'Sales Person: '+str(q.get('salesperson','')))
    merged(3,1,7,'Location: '+str(q.get('location','')));merged(3,8,10,'Version: '+str(q.get('version','1')))
    merged(4,1,10,'Contact Details: '+str(q.get('contact','')))
    merged(6,1,10,'Sub: '+str(q.get('subject') or q.get('project') or 'Quotation of Video Wall'))
    headers=['Sr. No.','Item','Description','Qty','Unit','Rate','GST','GST amount','Rate incl. taxes','Amount']
    for i,h in enumerate(headers,1):ws.cell(8,i,h)
    merged(9,1,10,'LED Video Wall System',True)
    sw=result['width_m'];sh=result['height_m']
    exact=data.get('preview_mode','exact')=='exact'
    unit=data.get('unit','m')
    if exact and data.get('mode','dimensions')=='dimensions':
        width=Decimal(str(data['screen_width']));height=Decimal(str(data['screen_height']))
    else:
        dimensions=result['design'] if exact else result
        divisor=Decimal('0.3048') if unit=='ft' else Decimal(1)
        outdoor=p.get('environment')=='outdoor' or Decimal(str(p.get('pitch_mm',0)))==4
        width=(Decimal(str(dimensions['width_m']))/divisor).quantize(Decimal('0.001'),rounding='ROUND_DOWN' if outdoor else 'ROUND_HALF_UP')
        height=(Decimal(str(dimensions['height_m']))/divisor).quantize(Decimal('0.001'),rounding='ROUND_DOWN' if outdoor else 'ROUND_HALF_UP')
    if p.get('environment')=='outdoor' or Decimal(str(p.get('pitch_mm',0)))==4:
        width=width.quantize(Decimal('0.001'),rounding='ROUND_DOWN')
        height=height.quantize(Decimal('0.001'),rounding='ROUND_DOWN')
    width=width.quantize(Decimal('0.001'),rounding='ROUND_DOWN' if p.get('environment')=='outdoor' or Decimal(str(p.get('pitch_mm',0)))==4 else 'ROUND_HALF_UP')
    height=height.quantize(Decimal('0.001'),rounding='ROUND_DOWN' if p.get('environment')=='outdoor' or Decimal(str(p.get('pitch_mm',0)))==4 else 'ROUND_HALF_UP')
    area=width*height
    sqft_decimal=area if unit=='ft' else area/Decimal('0.09290304')
    width_display = format(width.quantize(Decimal("0.001"), rounding="ROUND_HALF_UP"), ".3f")
    sqft=float(sqft_decimal)
    sqft_display = format(sqft_decimal.quantize(Decimal("0.001"), rounding="ROUND_HALF_UP"), ".3f")
    known=lambda key,unit='':str(p[key])+unit if p.get(key) is not None else 'Not provided'
    resolution=lambda item: f"{item['pixels_w']} × {item['pixels_h']}" if item.get('pixels_w') is not None and item.get('pixels_h') is not None else 'Not provided'
    dimensions=f"{p['width_mm']} × {p['height_mm']}" + (f" × {p['depth_mm']}" if p.get('depth_mm') is not None else '')
    description=(f"Supply of {p['environment']} LED video wall — {p['name']}; technology: {p.get('technology','Not specified')}. "
        f"Pricing dimensions: {width_display} × {height} {unit}; pricing area: {sqft_display} sq.ft. "
        f"Buildable cabinet dimensions: {sw} W × {sh} H m. "
        f"Layout: {result['columns']} × {result['rows']} = {result['count']} cabinets. "
        f"Total resolution: {resolution(result)}. "
        f"Pixel pitch: {p['pitch_mm']} mm. Cabinet dimensions: {dimensions} mm. "
        f"Cabinet resolution: {resolution(p)}. Brightness: {known('brightness_nits',' nits')}; "
        f"refresh: {known('refresh_hz',' Hz')}; IP rating: {known('ip_rating')}; maintenance: {known('maintenance')}.")
    reference = reference_description(p,width_display,height,unit,sqft_display)
    if reference:
        description = reference + f" Cabinet dimensions (W × H × D): {dimensions} mm."
    else:
        details = sheet_quotation_details(p)
        if details:
            description += '\n' + details
    description = ' '.join(description.split())
    actual_price='As per the company actual price.'
    def manual_description(value, fallback):
        description=str(value or fallback).strip()
        return description if actual_price.lower() in description.lower() else description.rstrip('. ') + '. ' + actual_price
    lines=[('Videowall',description,1,'Nos',q.get('wall_rate')),
      ((controller or {}).get('kind','LED Wall Controller'),controller_desc,numeric(q.get('controller_qty'),'Controller quantity',1,100000),'Nos',(controller or {}).get('rate_inr')),
      ('UniPole',manual_description(q.get('mount_description'),'Supply of Uni-Pole.'),1,'Nos',None),
      ('Installation',manual_description(q.get('installation_description'),'Installation charges'),1,'Nos',None)]
    last_item_row=9+len(lines)
    total_row=last_item_row+1
    for rn,(item,desc,qty,unit,rate) in enumerate(lines,10):
        for col,value in enumerate([rn-9,item,desc,qty,unit,numeric(rate,item+' rate'),gst],1):ws.cell(rn,col,text(value) if isinstance(value,str) else value)
        ws.cell(rn,8,f'=IF(F{rn}="","",ROUND(F{rn}*G{rn},2))')
        ws.cell(rn,9,f'=IF(F{rn}="","",ROUND(F{rn}+H{rn},2))')
        ws.cell(rn,10,f'=IF(F{rn}="","",ROUND(D{rn}*I{rn},2))')
        ws.row_dimensions[rn].height=max(180, 15 * (len(desc) // 75 + desc.count('\n') + 2)) if rn==10 else (max(100, 15 * (math.ceil(len(desc) / 70) + 2)) if rn==11 else 35)
        for col in [1,2,3,4,5,6,7,8,9,10]:
            ws.cell(rn,col).fill=PatternFill('solid',fgColor='FFFFFFFF')
        ws.cell(rn,7).number_format='0%'
        for col in [6,8,9,10]:ws.cell(rn,col).number_format='#,##0.00'
    for row, source in ((10,2),):
        factor=''
        ws.cell(row,6,f'=IF(\'Design & Specifications\'!B{source}="","",ROUND(\'Design & Specifications\'!B{source}{factor}*\'Design & Specifications\'!B3,2))')
        ws.cell(row,4).number_format='0'
    merged(total_row,1,9,'Total Amount',True)
    ws.cell(total_row,10,f'=IFERROR(ROUND(SUM(J10:J{last_item_row}),2),0)')
    ws.cell(total_row,10).number_format='#,##0.00'
    merged(18,1,10,'Terms and conditions:',True)
    for row,term in enumerate(TERMS,19):merged(row,1,10,f'{row-18}.) {term}');ws.row_dimensions[row].height=22
    merged(29,1,10,'Corporate Office: '+COMPANY_FOOTER['corporate'])
    merged(30,1,10,'Factory: '+COMPANY_FOOTER['factory'])
    merged(31,1,10,'Sales Office: '+COMPANY_FOOTER['sales'],True)
    merged(32,1,10,f"CIN: {COMPANY_FOOTER['cin']}    GSTIN: {COMPANY_FOOTER['gstin']}    PAN: {COMPANY_FOOTER['pan']}",True)
    merged(33,1,10,'We hope the estimate is in line with your requirements. For any clarifications, please get back to us.')
    merged(34,1,10,'Thanks & Regards')
    thin=Side(style='thin',color='000000')
    white_fill=PatternFill('solid',fgColor='FFFFFFFF')
    for row in ws.iter_rows(min_row=1,max_row=max(34,ws.max_row),max_col=max(10,ws.max_column)):
        for cell in row:
            cell.fill=white_fill
    for row in ws.iter_rows(min_row=8,max_row=total_row,max_col=10):
        for cell in row:
            cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
            cell.font=Font(name='Calibri',size=11,bold=cell.row in (8,9,total_row))
            cell.alignment=Alignment(wrap_text=True,vertical='center',horizontal='left' if cell.column==3 else 'center')
    ws.row_dimensions[8].height=34
    for cells,maxval in [(f'F10:F{last_item_row}',1e12),(f'D10:D{last_item_row}',100000),(f'G10:G{last_item_row}',1)]:
        dv=DataValidation(type='decimal',operator='between',formula1=0,formula2=maxval,allow_blank=True);dv.showErrorMessage=True;dv.error='Enter a non-negative number within the allowed range.';ws.add_data_validation(dv);dv.add(cells)
    ws.freeze_panes='D10';ws.print_options.horizontalCentered=True;ws.print_area='A1:J34'
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.sheet_properties.pageSetUpPr.fitToPage=True
    specs=wb.create_sheet('Design & Specifications');specs.column_dimensions['A'].width=42;specs.column_dimensions['B'].width=100
    rows=[('LED rate calculation','Cabinet rate per sq.ft. × screen area'),('LED base rate',numeric(q.get('wall_rate'),'LED base rate')),('Screen area (sq.ft.)',sqft),('UniPole rate (enter in Quotation!F12)',None),('Installation rate (enter in Quotation!F13)',None),('Controller pricing',f"RMB {(controller or {}).get('rmb_rate', 'Not provided')} × 15 × 2 = INR {(controller or {}).get('rate_inr', 'Not provided')}" if controller else 'Select a controller to calculate its price.'),('Selected model',p['name']),('Selected cabinet dimensions (mm)',dimensions),('Technology',p.get('technology','Not specified')),('Cabinet quantity',result['count']),('Columns × rows',f"{result['columns']} × {result['rows']}"),('Buildable dimensions (m)',f'{sw} × {sh}'),('Pricing area (sq.ft.)',sqft),('Video resolution',resolution(result)),('Total pixels',result['total_pixels'] if result['total_pixels'] is not None else 'Not provided'),('Controller','LED Wall Controller' if controller else 'To be selected'),('Controller verification','Supplied model specifications; receiving-card compatibility and port mapping require confirmation' if controller else 'Capacity and compatibility pending'),('Specification notes',p.get('notes',''))]
    if p.get('id') in REFERENCE_QUOTES:
        rows.append(('Quotation specification source','User-supplied quotation screenshot for this video wall type. Quotation wording is separate from configured cabinet geometry.'))
        rows.append(('Quotation technical description',description))
    if controller:
        rows.extend([('Controller specification source',controller['source']),('Controller technical description',controller_desc)])
        rows.extend(('Controller '+key,value) for key,value in controller.get('specifications',{}).items())
    catalogue_path=Path(base)/'catalogue.json'
    canonical_products=json.loads(catalogue_path.read_text(encoding='utf-8')) if catalogue_path.exists() else []
    canonical_options=[option for item in canonical_products for option in item.get('cabinet_options',[item])]
    canonical_product=next((item for item in canonical_options if item.get('id')==p.get('id')), {})
    canonical_sheets={sheet.get('model'):sheet for sheet in canonical_product.get('supplied_specifications',[])}
    for sheet in selected_specification_sheets(p):
        rows.append(('Supplied specification reference',sheet['model']))
        values=sheet.get('specs',{})
        reference=canonical_sheets.get(sheet.get('model'),{})
        order=sheet.get('specification_order') or reference.get('specification_order') or []
        keys=list(dict.fromkeys([key for key in order if key in values]+list(values)))
        rows.extend((key,values[key]) for key in keys)
    for row in rows:specs.append([text(v) if isinstance(v,str) else v for v in row])
    for row in specs:
        for cell in row:cell.alignment=Alignment(wrap_text=True,vertical='top')
        specs.row_dimensions[row[0].row].height=180 if row[0].value in ('Quotation technical description','Controller technical description') else 32
    specs_white=PatternFill('solid',fgColor='FFFFFFFF')
    for row in specs.iter_rows(min_row=1,max_row=max(specs.max_row,34),max_col=2):
        for cell in row:
            cell.fill=specs_white
    specs['B2'].number_format='#,##0.00'
    for cell in ('B3', 'B12'):
        specs[cell].number_format='0.000'
    image_path=(Path(base)/'static'/str(p.get('image',''))).resolve();allowed=(Path(base)/'static/models').resolve()
    if image_path.is_relative_to(allowed) and image_path.is_file():
        img=Image(str(image_path));img.width=260;img.height=180;specs.add_image(img,'D2')
    specs.sheet_view.showGridLines=True
    specs.sheet_view.showRowColHeaders=True
    specs.print_options.gridLines=True
    specs.print_options.gridLinesSet=True
    for row in specs.iter_rows(min_row=1,max_row=specs.max_row,max_col=2):
        for cell in row:cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
    specs.freeze_panes='B2'
    output=BytesIO();wb.save(output)
    # Store formula results for viewers that do not recalculate on opening.
    def money(value):return float(Decimal(str(value)).quantize(Decimal('0.01'),rounding='ROUND_HALF_UP'))
    cached={}
    unit_rates=[numeric(q.get('wall_rate'),'LED rate'),numeric((controller or {}).get('rate_inr'),'Controller rate')]+[None]*4
    for row,rate in zip(range(10,last_item_row+1),unit_rates):
        if rate is None:
            for col in ('F','H','I','J'):
                if ws[f'{col}{row}'].data_type=='f':cached[f'{col}{row}']=''
            continue
        full=money(Decimal(str(rate))*sqft_decimal) if row==10 else money(rate)
        cached[f'F{row}']=full
        tax=money(full*gst);gross=money(full+tax)
        cached[f'H{row}']=tax;cached[f'I{row}']=gross;cached[f'J{row}']=money(float(ws.cell(row,4).value)*gross)
    cached[f'J{total_row}']=money(sum(cached[f'J{r}'] for r in range(10,last_item_row+1) if isinstance(cached.get(f'J{r}'), (int,float))))
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    final=BytesIO()
    with ZipFile(output) as src, ZipFile(final,'w',ZIP_DEFLATED) as dst:
        for item in src.infolist():
            content=src.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                tree=ET.fromstring(content)
                for cell in tree.findall('.//s:c',ns):
                    key=cell.get('r')
                    if key not in cached:continue
                    value=cached[key];v=cell.find('s:v',ns)
                    if v is None:v=ET.SubElement(cell,'{'+ns['s']+'}v')
                    if isinstance(value,str):cell.set('t','str')
                    else:cell.attrib.pop('t',None)
                    v.text=str(value)
                content=ET.tostring(tree,encoding='utf-8')
            dst.writestr(item,content)
    final.seek(0);return final


def build_quotation_pdf(data, base):
    """Build a landscape PROMARK quotation matching the supplied reference layout."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    result = calculate(data)
    product = data['product']
    quotation = dict(data.get('quotation') or {})
    gst_percent = numeric(quotation.get('gst'), 'GST', 18, 100)
    gst = gst_percent / 100
    unit = data.get('unit', 'm')

    controllers = json.loads((Path(base) / 'controllers.json').read_text(encoding='utf-8'))
    controller = next((item for item in controllers if item['id'] == data.get('controller')), None)
    if data.get('controller') and not controller:
        raise ValueError('This controller is no longer available. Select a current PROMARK controller before downloading.')

    if data.get('preview_mode', 'exact') == 'exact' and data.get('mode') == 'dimensions':
        width = Decimal(str(data['screen_width']))
        height = Decimal(str(data['screen_height']))
    else:
        dimensions = result.get('design') or result
        divisor = Decimal('0.3048') if unit == 'ft' else Decimal(1)
        width = Decimal(str(dimensions['width_m'])) / divisor
        height = Decimal(str(dimensions['height_m'])) / divisor

    area = width * height
    area_sqft = area if unit == 'ft' else area / Decimal('0.09290304')
    wall_rate = numeric(quotation.get('wall_rate'), 'LED rate')
    controller_quantity = numeric(quotation.get('controller_qty'), 'Controller quantity', 1, 100000)
    controller_rate = numeric((controller or {}).get('rate_inr'), 'Controller rate')

    def indian(value):
        try:
            value = Decimal(str(value or 0)).quantize(Decimal('0.01'))
            whole, frac = f'{value:.2f}'.split('.')
            if len(whole) <= 3:
                return f'{whole}.{frac}'
            last3, rest = whole[-3:], whole[:-3]
            rest = rest[-2:] and format(int(rest), ',')
            return f'{rest},{last3}.{frac}' if rest else f'{last3}.{frac}'
        except Exception:
            return '0.00'

    def parsed_date(value):
        try:
            return date.fromisoformat(str(value)).strftime('%d-%m-%Y')
        except Exception:
            return date.today().strftime('%d-%m-%Y')

    output = BytesIO()
    page_width, page_height = landscape(A4)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Small', parent=styles['BodyText'], fontName='Helvetica', fontSize=7, leading=7))
    styles.add(ParagraphStyle(name='SmallBold', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7, leading=8))
    styles.add(ParagraphStyle(name='Center', parent=styles['BodyText'], fontName='Helvetica', fontSize=7, leading=8, alignment=1))

    def page_decor(canvas, doc):
        import textwrap
        canvas.saveState()
        logo_path = Path(base) / 'static' / 'logo.png'
        if logo_path.exists():
            canvas.drawImage(str(logo_path), 18*mm, page_height-28*mm, width=48*mm, height=14*mm, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, page_width, 38*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.rect(0, 29*mm, page_width, 9*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawCentredString(page_width/2, 32.4*mm, 'PROMARK TECHNOLOGIES PRIVATE LIMITED')
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.setFont('Helvetica-Bold', 8.5)
        column_centers = [page_width*0.167, page_width*0.5, page_width*0.833]
        for center, label in zip(column_centers, ('CORPORATE OFFICE', 'FACTORY', 'SALES OFFICE')):
            canvas.drawCentredString(center, 25.5*mm, label)
        canvas.setFillColor(colors.black)
        canvas.setFont('Helvetica', 7.2)
        address_values = (COMPANY_FOOTER['corporate'], COMPANY_FOOTER['factory'], COMPANY_FOOTER['sales'])
        for center, address in zip(column_centers, address_values):
            wrapped = textwrap.wrap(address, width=38, break_long_words=False, break_on_hyphens=False)
            y = 22.2*mm
            for line in wrapped[:4]:
                canvas.drawCentredString(center, y, line)
                y -= 3.0*mm
        canvas.setStrokeColor(colors.HexColor('#0878c9'))
        canvas.setLineWidth(1.0)
        canvas.line(page_width/3, 14.5*mm, page_width/3, 28*mm)
        canvas.line(2*page_width/3, 14.5*mm, 2*page_width/3, 28*mm)
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.setFont('Helvetica-Bold', 8.5)
        ids = [f"CIN: {COMPANY_FOOTER['cin']}", f"GSTIN: {COMPANY_FOOTER['gstin']}", f"PAN: {COMPANY_FOOTER['pan']}"]
        for center, value in zip(column_centers, ids):
            canvas.drawCentredString(center, 8.5*mm, value)
        canvas.setFillColor(colors.HexColor('#111111'))
        canvas.rect(0, 0, page_width, 2*mm, fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=(page_width, page_height), leftMargin=12*mm,
                            rightMargin=12*mm, topMargin=24*mm, bottomMargin=40*mm,
                            title='Promark Video Wall Quotation')
    story = [Spacer(1, 0*mm)]

    reference_name = 'Quotations of Video Wall'
    if product.get('environment') and product.get('pitch_mm') is not None:
        reference_name = f"{float(product['pitch_mm']):g}mm {product.get('technology', 'SMD')} {str(product['environment']).title()} Video Wall"

    wall_description = reference_description(product, indian(width), indian(height), unit, indian(area_sqft)) if reference_description(product, width, height, unit, area_sqft) else None
    if not wall_description:
        wall_description = (f"Supply of {product.get('technology', 'LED')} LED video wall ({indian(width)}W x {indian(height)}H {unit}). "
                            f"Pixel Pitch: {product.get('pitch_mm', '—')}mm. Cabinet layout: {result.get('columns', 0)}W x {result.get('rows', 0)}H.")

    left_info = [
        [Paragraph('<b>Client Name:</b> '+str(quotation.get('client','')), styles['Small'])],
        [Paragraph('<b>Project Detail:</b> '+str(quotation.get('project') or reference_name), styles['Small'])],
        [Paragraph('<b>Location:</b> '+str(quotation.get('location','')), styles['Small'])],
        [Paragraph('<b>Sub:</b> '+str(quotation.get('subject') or f"Quotation of {reference_name}"), styles['Small'])],
    ]
    right_info = [
        [Paragraph('<b>Date:</b> '+parsed_date(quotation.get('date')), styles['Small'])],
        [Paragraph('<b>Sales Person:</b> '+str(quotation.get('salesperson','')), styles['Small'])],
        [Paragraph('<b>Version:</b> '+str(quotation.get('version','1')), styles['Small'])],
        ['',],
    ]
    info = Table([[Table(left_info, colWidths=[112*mm]), Table(right_info, colWidths=[112*mm])]],
                 colWidths=[112*mm, 112*mm], rowHeights=[24*mm])
    info.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,0),(-1,-1),0,colors.white)]))
    story += [info, Spacer(1, 2*mm)]

    headers = ['Sr. No.', 'Item', 'Description', 'Qty', 'Unit', 'Rate', 'GST', 'GST amount', 'Rate incl.\ntaxes', 'Amount']
    pdf_rows = [headers]
    subtotal = Decimal('0')
    gst_total = Decimal('0')

    wall_base = Decimal(str(area_sqft)) * Decimal(str(wall_rate or 0))
    wall_gst_amount = wall_base * Decimal(str(gst))
    wall_gross = wall_base + wall_gst_amount
    subtotal += wall_gross
    gst_total += wall_gst_amount
    pdf_rows.append(['1', 'Videowall', wall_description.replace('\n','<br/>'), '1', 'Nos', indian(wall_base), f'{gst_percent:g}%', indian(wall_gst_amount), indian(wall_gross), indian(wall_gross)])

    if controller:
        controller_base = Decimal(str(controller_rate or 0)) * Decimal(str(controller_quantity))
        controller_gst = controller_base * Decimal(str(gst))
        controller_gross = controller_base + controller_gst
        subtotal += controller_gross
        gst_total += controller_gst
        controller_description = ' '.join(str(controller.get('description') or 'Supply of LED Wall Controller. Capacity and compatibility to be confirmed.').split())
        all_controllers=json.loads((Path(base)/'controllers.json').read_text(encoding='utf-8')) if 'base' in locals() else []
        controller_description=strip_controller_names(controller_description, all_controllers)
        pdf_rows.append(['2', 'LED Wall\nController', controller_description, f'{controller_quantity:g}', 'Nos', indian(controller_rate), f'{gst_percent:g}%', indian(controller_gst), indian(controller_rate * (1 + gst)), indian(controller_gross)])

    mount_rate = numeric(quotation.get('mount_rate'), 'Mounting rate', 0)
    mount_qty = numeric(quotation.get('mount_qty'), 'Mounting quantity', 1)
    install_rate = numeric(quotation.get('installation_rate'), 'Installation rate', 0)
    mount_base = Decimal(str(mount_rate)) * Decimal(str(mount_qty))
    install_base = Decimal(str(install_rate))
    for number, (item_name, desc, rate_base) in enumerate([
        ('UniPole', str(quotation.get('mount_description') or 'Supply of Uni-Pole.'), mount_base),
        ('Installation', str(quotation.get('installation_description') or 'Supply of Installation charges.'), install_base),
    ], start=len(pdf_rows)-1):
        rate = rate_base
        gst_amount = rate * Decimal(str(gst))
        gross = rate + gst_amount
        if rate:
            subtotal += gross
            gst_total += gst_amount
        pdf_rows.append([str(number+1), item_name, desc, '1', 'Nos', indian(rate) if rate else 'As per actual', f'{gst_percent:g}%', indian(gst_amount) if rate else '-', indian(gross) if rate else '-', indian(gross) if rate else '-'])

    table = Table([[Paragraph(str(v).replace('\n','<br/>'), styles['Small']) for v in pdf_rows[0]]] +
                  [[Paragraph(str(v).replace('\n','<br/>'), styles['Small']) for v in row] for row in pdf_rows[1:]],
                  repeatRows=1, colWidths=[12*mm,26*mm,66*mm,10*mm,12*mm,19*mm,12*mm,20*mm,22*mm,25*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,1),(-1,-1),colors.white),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d9e9f4')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black), ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.5,colors.black), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ALIGN',(3,0),(5,-1),'CENTER'), ('ALIGN',(6,0),(-1,-1),'RIGHT'),
        ('TOPPADDING',(0,0),(-1,-1),2), ('BOTTOMPADDING',(0,0),(-1,-1),2),
    ]))
    story += [table]

    story.append(Table([
        ['', '', '', '', '', '', '', '', Paragraph('<b>Total Amount</b>', styles['Small']), Paragraph(indian(subtotal), styles['Small'])],
        ['', '', '', '', '', '', '', '', Paragraph('<b>GST Amount</b>', styles['Small']), Paragraph(indian(gst_total), styles['Small'])],
    ], colWidths=[12*mm,26*mm,66*mm,10*mm,12*mm,19*mm,12*mm,20*mm,22*mm,25*mm], style=[
        ('GRID',(8,0),(-1,-1),0.5,colors.black), ('ALIGN',(8,0),(-1,-1),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story += [Spacer(1, 2*mm), Paragraph('<b>Terms and conditions:</b>', styles['SmallBold'])]
    for index, term in enumerate(TERMS, 1):
        story.append(Paragraph(f'{index}) {term}', styles['Small']))
    story += [Spacer(1, 1*mm)]

    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    output.seek(0)
    return output


def build_pdf_from_excel(file_stream, filename='Quotation-edited'):
    """Convert an edited quotation worksheet into the branded reference PDF layout."""
    from openpyxl import load_workbook
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    workbook = load_workbook(file_stream, data_only=True)
    if 'Quotation' not in workbook.sheetnames:
        raise ValueError('The Excel file must contain a Quotation worksheet.')
    sheet = workbook['Quotation']
    controllers=json.loads((Path(__file__).parent/'controllers.json').read_text(encoding='utf-8'))
    white_fill = PatternFill('solid', fgColor='FFFFFFFF')
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                cell.fill = white_fill

    def merged_value(row, start_col, end_col):
        for col in range(start_col, end_col + 1):
            value = sheet.cell(row, col).value
            if value not in (None, ''):
                return str(value)
        return ''

    def number(value):
        if isinstance(value, (int, float)):
            return float(value)
        if value in (None, ''):
            return 0.0
        try:
            return float(str(value).replace(',', '').replace('₹', '').strip())
        except ValueError:
            return 0.0

    def indian(value):
        return f'{number(value):,.2f}'

    import html

    header_row = 8
    for candidate in range(1, 15):
        first_cell = str(sheet.cell(candidate, 1).value or '').strip().lower()
        second_cell = str(sheet.cell(candidate, 2).value or '').strip().lower()
        if first_cell in ('sr. no.', 'sr no.', 'sr.') and second_cell == 'item':
            header_row = candidate
            break

    headers = [sheet.cell(header_row, col).value or '' for col in range(1, 11)]
    rows = []
    total_amount = 0.0
    total_gst = 0.0

    for item_row, serial_number in ((10, 1), (11, 2), (12, 3), (13, 4)):
        sr = sheet.cell(item_row, 1).value
        item = sheet.cell(item_row, 2).value
        description = sheet.cell(item_row, 3).value
        item_text = str(item or '').strip()
        if not item_text:
            continue

        try:
            serial_number = int(float(str(sr))) if sr not in (None, '') else serial_number
        except (TypeError, ValueError):
            serial_number = serial_number

        if serial_number not in (1, 2, 3, 4):
            continue
        item_key = item_text.lower()
        if 'mounting structure' in item_key:
            item_text = 'UniPole'
        if 'controller' in item_key:
            description = canonical_controller_description(description, controllers)

        qty_value = sheet.cell(item_row, 4).value
        qty = number(qty_value)
        unit = sheet.cell(item_row, 5).value or 'Nos'
        rate_cell = sheet.cell(item_row, 6).value
        rate = number(rate_cell)
        gst_value = number(sheet.cell(item_row, 7).value)
        gst_fraction = gst_value / 100 if gst_value > 1 else gst_value

        has_rate = rate_cell not in (None, '') and str(rate_cell).strip() != ''
        if has_rate:
            gst_amount = rate * gst_fraction * qty
            inclusive_rate = rate * (1 + gst_fraction)
            amount = qty * inclusive_rate
            total_gst += gst_amount
            total_amount += amount
            rate_display = indian(rate)
            gst_display = indian(gst_amount)
            inclusive_display = indian(inclusive_rate)
            amount_display = indian(amount)
        else:
            gst_amount = Decimal('0')
            inclusive_rate = Decimal('0')
            amount = Decimal('0')
            rate_display = 'As per actual'
            gst_display = '-'
            inclusive_display = '-'
            amount_display = '-'

        description_text = str(description or '')[:900]
        rows.append([
            serial_number,
            item_text,
            description_text,
            qty if qty else '',
            unit,
            rate_display,
            f'{gst_fraction:.0%}' if gst_fraction else '0%',
            gst_display,
            inclusive_display,
            amount_display,
        ])

    output = BytesIO()
    page_width, page_height = landscape(A4)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReferenceSmall', parent=styles['BodyText'], fontName='Helvetica', fontSize=5.7, leading=6.2))
    styles.add(ParagraphStyle(name='ReferenceBold', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=5.7, leading=6.2))

    def page_decor(canvas, doc):
        import textwrap
        canvas.saveState()
        logo_path = Path(__file__).parent / 'static' / 'logo.png'
        if logo_path.exists():
            canvas.drawImage(str(logo_path), 12*mm, page_height-27*mm, width=55*mm, height=17*mm, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, page_width, 38*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.rect(0, 29*mm, page_width, 9*mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawCentredString(page_width/2, 32.4*mm, 'PROMARK TECHNOLOGIES PRIVATE LIMITED')
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.setFont('Helvetica-Bold', 8.5)
        column_centers = [page_width*0.167, page_width*0.5, page_width*0.833]
        for center, label in zip(column_centers, ('CORPORATE OFFICE', 'FACTORY', 'SALES OFFICE')):
            canvas.drawCentredString(center, 25.5*mm, label)
        canvas.setFillColor(colors.black)
        canvas.setFont('Helvetica', 7.2)
        address_values = (COMPANY_FOOTER['corporate'], COMPANY_FOOTER['factory'], COMPANY_FOOTER['sales'])
        for center, address in zip(column_centers, address_values):
            wrapped = textwrap.wrap(address, width=38, break_long_words=False, break_on_hyphens=False)
            y = 22.2*mm
            for line in wrapped[:4]:
                canvas.drawCentredString(center, y, line)
                y -= 3.0*mm
        canvas.setStrokeColor(colors.HexColor('#0878c9'))
        canvas.setLineWidth(1.0)
        canvas.line(page_width/3, 14.5*mm, page_width/3, 28*mm)
        canvas.line(2*page_width/3, 14.5*mm, 2*page_width/3, 28*mm)
        canvas.setFillColor(colors.HexColor('#0878c9'))
        canvas.setFont('Helvetica-Bold', 8.5)
        ids = [f"CIN: {COMPANY_FOOTER['cin']}", f"GSTIN: {COMPANY_FOOTER['gstin']}", f"PAN: {COMPANY_FOOTER['pan']}"]
        for center, value in zip(column_centers, ids):
            canvas.drawCentredString(center, 8.5*mm, value)
        canvas.setFillColor(colors.HexColor('#111111'))
        canvas.rect(0, 0, page_width, 2*mm, fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=(page_width, page_height), leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=21*mm, bottomMargin=40*mm, title='Edited PROMARK Video Wall Quotation')

    def clean_label(value, label):
        text = str(value or '').strip()
        if text.startswith(label + ':'):
            return text
        return f'<b>{label}:</b> {text}' if text else f'<b>{label}:</b>'

    story = []
    left_rows = [[Paragraph(clean_label(sheet.cell(1, 1).value, 'Client Name'), styles['ReferenceSmall'])],
                 [Paragraph(clean_label(sheet.cell(2, 1).value, 'Project Detail'), styles['ReferenceSmall'])],
                 [Paragraph(clean_label(sheet.cell(3, 1).value, 'Location'), styles['ReferenceSmall'])],
                 [Paragraph(clean_label(sheet.cell(6, 1).value, 'Sub'), styles['ReferenceSmall'])]]
    right_rows = [[Paragraph(clean_label(sheet.cell(1, 8).value, 'Date'), styles['ReferenceSmall'])],
                  [Paragraph(clean_label(sheet.cell(2, 8).value, 'Sales Person'), styles['ReferenceSmall'])],
                  [Paragraph(clean_label(sheet.cell(3, 8).value, 'Version'), styles['ReferenceSmall'])]]
    contact_value = str(sheet.cell(4, 1).value or '').strip()
    if contact_value:
        right_rows.append([Paragraph(clean_label(contact_value, 'Contact Details'), styles['ReferenceSmall'])])
    info = Table([[Table(left_rows, colWidths=[112*mm]), Table(right_rows, colWidths=[112*mm])]],
                 colWidths=[112*mm,112*mm], rowHeights=[28*mm])
    info.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [info, Spacer(1, 2*mm)]

    table_rows = [[Paragraph(html.escape(str(value)), styles['ReferenceBold']) for value in headers]]
    for row in rows:
        table_rows.append([
            Paragraph(html.escape(str(value)).replace('\n', '<br/>'), styles['ReferenceSmall'])
            for value in row
        ])

    table = Table(table_rows, repeatRows=1, splitByRow=1, splitInRow=1,
                  colWidths=[12*mm,27*mm,66*mm,10*mm,12*mm,20*mm,12*mm,20*mm,22*mm,23*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,1),(-1,-1),colors.white),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#d9e9f4')),
        ('GRID',(0,0),(-1,-1),0.5,colors.black), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ALIGN',(3,0),(5,-1),'CENTER'), ('ALIGN',(6,0),(-1,-1),'RIGHT'),
        ('TOPPADDING',(0,0),(-1,-1),2), ('BOTTOMPADDING',(0,0),(-1,-1),2),
    ]))
    story.append(table)

    totals = Table([
        ['', '', '', '', '', '', '', '', Paragraph('<b>Total Amount</b>', styles['ReferenceBold']), Paragraph(indian(total_amount), styles['ReferenceBold'])],
        ['', '', '', '', '', '', '', '', Paragraph('<b>GST Amount</b>', styles['ReferenceBold']), Paragraph(indian(total_gst), styles['ReferenceBold'])],
    ], colWidths=[12*mm,27*mm,66*mm,10*mm,12*mm,20*mm,12*mm,20*mm,22*mm,23*mm])
    totals.setStyle(TableStyle([('GRID',(8,0),(-1,-1),0.5,colors.black), ('ALIGN',(8,0),(-1,-1),'RIGHT')]))
    story += [totals, Spacer(1, 2*mm), Paragraph('<b>Terms and conditions:</b>', styles['ReferenceBold'])]

    terms = []
    for row_number in range(19, 28):
        value = sheet.cell(row_number, 1).value
        if value:
            term_text = str(value).strip()
            if term_text and not term_text.lower().startswith('terms and conditions'):
                terms.append(Paragraph(html.escape(term_text), styles['ReferenceSmall']))
    if not terms:
        terms = []
        for index, term in enumerate(TERMS, 1):
            term_text = html.escape(f'{index}) {term}')
            terms.append(Paragraph(term_text, styles['ReferenceSmall']))

    for term in terms:
        story.append(term)

    story.append(Spacer(1, 1*mm))

    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    output.seek(0)
    return output
