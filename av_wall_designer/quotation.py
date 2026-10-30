"""Editable quotation matching the supplied reference layout."""
import json
import math
import re
from html import escape
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

def quotation_dimensions(data, result):
    """Use the displayed pricing dimensions for both quotation formats."""
    product = data['product']
    exact = data.get('preview_mode', 'exact') == 'exact'
    unit = data.get('unit', 'm')
    if exact and data.get('mode', 'dimensions') == 'dimensions':
        width = Decimal(str(data['screen_width']))
        height = Decimal(str(data['screen_height']))
    else:
        dimensions = result['design'] if exact else result
        divisor = Decimal('0.3048') if unit == 'ft' else Decimal(1)
        width = Decimal(str(dimensions['width_m'])) / divisor
        height = Decimal(str(dimensions['height_m'])) / divisor
    outdoor = product.get('environment') == 'outdoor' or Decimal(str(product.get('pitch_mm', 0))) == 4
    rounding = 'ROUND_DOWN' if outdoor else ROUND_HALF_UP
    return tuple(value.quantize(Decimal('0.001'), rounding=rounding) for value in (width, height))


def mounting_item(quotation, area_sqft):
    """Return an optional mounting line with its price before GST."""
    mount_type = quotation.get('mount_type') or 'none'
    if mount_type == 'none':
        return None
    options = {
        'unipole': ('Uni-pole', 'Supply of Uni-pole.', 175000),
        'structure': ('Mounting structure', 'Supply of mounting structure for the LED video wall.', 800),
    }
    if mount_type not in options:
        raise ValueError('Select None, Uni-pole or Mounting structure.')
    name, description, default_rate = options[mount_type]
    unit_rate = Decimal(str(numeric(quotation.get('mount_rate'), 'Mounting rate', default_rate)))
    price = unit_rate * area_sqft if mount_type == 'structure' else unit_rate
    price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'name': name, 'description': str(quotation.get('mount_description') or description),
        'unit_rate': unit_rate, 'price': price, 'type': mount_type,
    }


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
    unit=data.get('unit','m')
    width,height=quotation_dimensions(data,result)
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
    mount=mounting_item(q,sqft_decimal)
    lines=[('Videowall',description,1,'Nos',q.get('wall_rate')),
      ((controller or {}).get('kind','LED Wall Controller'),controller_desc,numeric(q.get('controller_qty'),'Controller quantity',1,100000),'Nos',(controller or {}).get('rate_inr'))]
    if mount:
        lines.append((mount['name'],mount['description'],1,'Nos',mount['price']))
    lines.append(('Installation',manual_description(q.get('installation_description'),'Installation charges'),1,'Nos',None))
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
    if mount:
        factor="*'Design & Specifications'!B3" if mount['type']=='structure' else ''
        ws.cell(12,6,f"=ROUND('Design & Specifications'!B4{factor},2)")
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
    mount_rate_label = ('Mounting structure rate (INR / sq.ft.)' if mount['type']=='structure' else 'Uni-pole unit rate (INR)') if mount else 'Mounting option: None'
    rows=[('LED rate calculation','Cabinet rate per sq.ft. × screen area'),('LED base rate',numeric(q.get('wall_rate'),'LED base rate')),('Screen area (sq.ft.)',sqft),(mount_rate_label,float(mount['unit_rate']) if mount else None),(f'Installation rate (enter in Quotation!F{last_item_row})',None),('Controller pricing',f"RMB {(controller or {}).get('rmb_rate', 'Not provided')} × 15 × 2 = INR {(controller or {}).get('rate_inr', 'Not provided')}" if controller else 'Select a controller to calculate its price.'),('Selected model',p['name']),('Selected cabinet dimensions (mm)',dimensions),('Technology',p.get('technology','Not specified')),('Cabinet quantity',result['count']),('Columns × rows',f"{result['columns']} × {result['rows']}"),('Buildable dimensions (m)',f'{sw} × {sh}'),('Pricing area (sq.ft.)',sqft),('Video resolution',resolution(result)),('Total pixels',result['total_pixels'] if result['total_pixels'] is not None else 'Not provided'),('Controller','LED Wall Controller' if controller else 'To be selected'),('Controller verification','Supplied model specifications; receiving-card compatibility and port mapping require confirmation' if controller else 'Capacity and compatibility pending'),('Specification notes',p.get('notes',''))]
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
    specs['B4'].number_format='#,##0.00'
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
    unit_rates=[numeric(line[4],line[0]+' rate') for line in lines]
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


def draw_quotation_page(canvas, doc, base):
    """Use the same logo and complete, updated footer for both PDF exports."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph

    page_width, page_height = doc.pagesize
    blue = colors.HexColor('#0878c9')
    canvas.saveState()
    logo_path = Path(base) / 'static' / 'logo.png'
    if logo_path.exists():
        canvas.drawImage(str(logo_path), 18*mm, page_height-28*mm,
                         width=48*mm, height=14*mm, preserveAspectRatio=True, mask='auto')
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, page_width, 38*mm, fill=1, stroke=0)
    canvas.setFillColor(blue)
    canvas.rect(0, 29*mm, page_width, 9*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawCentredString(page_width/2, 32.4*mm, 'PROMARK TECHNOLOGIES PRIVATE LIMITED')

    address_style = ParagraphStyle('FooterAddress', fontName='Helvetica', fontSize=7.2,
                                   leading=8.5, alignment=1)
    column_width = page_width / 3
    for index, (label, key, tax_label, tax_key) in enumerate([
        ('CORPORATE OFFICE', 'corporate', 'CIN', 'cin'),
        ('FACTORY', 'factory', 'GSTIN', 'gstin'),
        ('SALES OFFICE', 'sales', 'PAN', 'pan'),
    ]):
        center = column_width * (index + 0.5)
        canvas.setFillColor(blue)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawCentredString(center, 25.5*mm, label)
        address = Paragraph(escape(COMPANY_FOOTER[key]), address_style)
        width, height = address.wrap(column_width - 12*mm, 16*mm)
        address.drawOn(canvas, center - width/2, 23*mm - height)
        canvas.setFillColor(blue)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawCentredString(center, 8.5*mm, f'{tax_label}: {COMPANY_FOOTER[tax_key]}')
    canvas.setStrokeColor(blue)
    canvas.setLineWidth(1)
    for x in (column_width, 2*column_width):
        canvas.line(x, 14.5*mm, x, 28*mm)
    canvas.setFillColor(colors.HexColor('#111111'))
    canvas.rect(0, 0, page_width, 2*mm, fill=1, stroke=0)
    canvas.restoreState()


def build_single_page_quotation(story, base, title):
    """Shrink the complete quotation body to fit above the fixed company footer."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, Frame, KeepInFrame, PageTemplate

    output = BytesIO()
    doc = BaseDocTemplate(output, pagesize=landscape(A4), leftMargin=12*mm,
                          rightMargin=12*mm, topMargin=24*mm, bottomMargin=40*mm,
                          allowSplitting=0, title=title)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='quotation')

    def page_decor(canvas, document):
        draw_quotation_page(canvas, document, base)

    doc.addPageTemplates([PageTemplate(id='Quotation', frames=[frame], onPage=page_decor)])
    # Keep items, totals and every term together. Content that already fits stays
    # at its original size; longer quotations scale down without losing rows.
    doc.build([KeepInFrame(0, 0, story, mode='shrink', hAlign='CENTER', vAlign='TOP')])
    output.seek(0)
    return output


def build_quotation_pdf(data, base):
    """Build a landscape PROMARK quotation matching the supplied reference layout."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

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

    width, height = quotation_dimensions(data, result)

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

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Small', parent=styles['BodyText'], fontName='Helvetica', fontSize=7, leading=7))
    styles.add(ParagraphStyle(name='SmallBold', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7, leading=8))
    styles.add(ParagraphStyle(name='Center', parent=styles['BodyText'], fontName='Helvetica', fontSize=7, leading=8, alignment=1))

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

    mount = mounting_item(quotation, area_sqft)
    install_rate = numeric(quotation.get('installation_rate'), 'Installation rate', 0)
    install_base = Decimal(str(install_rate))
    optional_rows = []
    if mount:
        optional_rows.append((mount['name'], escape(mount['description']), mount['price']))
    optional_rows.append(('Installation', str(quotation.get('installation_description') or 'Supply of Installation charges.'), install_base))
    for number, (item_name, desc, rate_base) in enumerate(optional_rows, start=len(pdf_rows)):
        rate = rate_base
        gst_amount = (rate * Decimal(str(gst))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        gross = rate + gst_amount
        if rate:
            subtotal += gross
            gst_total += gst_amount
        priced = bool(rate) or (mount is not None and item_name == mount['name'])
        pdf_rows.append([str(number), item_name, desc, '1', 'Nos', indian(rate) if priced else 'As per actual', f'{gst_percent:g}%', indian(gst_amount) if priced else '-', indian(gross) if priced else '-', indian(gross) if priced else '-'])

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

    return build_single_page_quotation(story, base, 'Promark Video Wall Quotation')


def read_excel_quotation(sheet):
    """Read sections by their labels so inserted/deleted Excel rows stay intact."""
    def label(value):
        return re.sub(r'[^a-z0-9]', '', str(value or '').lower())

    def decimal(value):
        if value in (None, ''):
            return None
        try:
            result = Decimal(str(value).replace(',', '').replace('₹', '').strip())
        except InvalidOperation:
            return None
        return result if result.is_finite() else None

    def money(value):
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def display(value):
        return f'{value:,.2f}'

    header_row = next((
        row for row in range(1, sheet.max_row + 1)
        if label(sheet.cell(row, 1).value) in ('srno', 'sr', 'serialno', 'serialnumber')
        and label(sheet.cell(row, 2).value) == 'item'
        and label(sheet.cell(row, 3).value) == 'description'
    ), None)
    if header_row is None:
        raise ValueError('The Quotation worksheet must contain the item table headings.')

    metadata = {}
    for row in sheet.iter_rows(max_row=header_row - 1, max_col=10):
        for cell in row:
            name, separator, value = str(cell.value or '').partition(':')
            if separator:
                metadata[label(name)] = value.strip()
    date_value = metadata.get('date', '')
    try:
        metadata['date'] = date.fromisoformat(date_value).strftime('%d-%m-%Y')
    except ValueError:
        pass

    footer_labels = ('corporateoffice', 'factory', 'salesoffice', 'cin', 'gstin',
                     'pan', 'wehopetheestimate', 'thanksregards', 'promark')
    total_labels = ('totalamount', 'gstamount', 'grandtotal', 'subtotal', 'total')
    terms = []
    terms_found = False
    in_terms = False
    in_items = True
    rows = []
    total_amount = Decimal('0')
    total_gst = Decimal('0')

    for values in sheet.iter_rows(min_row=header_row + 1, max_col=10, values_only=True):
        nonempty = [str(value).strip() for value in values if value not in (None, '')]
        if not nonempty:
            continue
        first_label = label(nonempty[0])
        if first_label.startswith(('termsandconditions', 'termsconditions')):
            in_items = False
            terms_found = in_terms = True
            continue
        if in_terms:
            if first_label.startswith(footer_labels):
                in_terms = False
            else:
                term = ' '.join(nonempty)
                term = re.sub(r'^\d+\s*(?:\.\)|[.)])\s*', '', term)
                terms.append(term)
            continue
        if any(label(value) in total_labels for value in values[:3]) or (
            not values[1] and label(values[8]) in total_labels
        ):
            in_items = False
            continue
        if not in_items:
            continue
        if not values[1] and not values[2]:
            # Merged section titles and footer rows are not quotation items.
            if first_label.startswith(footer_labels):
                in_items = False
            continue
        item = str(values[1] or '').strip()
        if not item:
            continue

        serial = decimal(values[0])
        serial_text = f'{serial:g}' if serial is not None else str(len(rows) + 1)
        qty = decimal(values[3]) if values[3] not in (None, '') else Decimal('1')
        if qty is None or qty < 0:
            raise ValueError(f'Enter a valid quantity for {item}.')
        gst_cell = values[6]
        gst_text = str(gst_cell or '').strip()
        gst = decimal(gst_text.rstrip('%')) if gst_text else Decimal('0')
        if gst is None or gst < 0:
            raise ValueError(f'Enter a valid GST percentage for {item}.')
        if gst_text.endswith('%') or gst > 1:
            gst /= 100
        if gst > 1:
            raise ValueError(f'GST cannot exceed 100% for {item}.')

        rate = decimal(values[5])
        if rate is not None:
            if rate < 0:
                raise ValueError(f'Enter a non-negative rate for {item}.')
            rate = money(rate)
            # Excel stores per-unit GST in H, tax-inclusive rate in I and
            # quantity * inclusive rate in J. Preserve saved Excel edits.
            tax = decimal(values[7])
            tax = money(tax if tax is not None else rate * gst)
            inclusive = decimal(values[8])
            inclusive = money(inclusive if inclusive is not None else rate + tax)
            amount = decimal(values[9])
            amount = money(amount if amount is not None else qty * inclusive)
            total_gst += money(tax * qty)
            total_amount += amount
            pricing = [display(rate), f'{gst * 100:g}%', display(tax),
                       display(inclusive), display(amount)]
        else:
            pricing = [str(values[5] or 'As per actual'), f'{gst * 100:g}%', '-', '-', '-']

        rows.append([serial_text, item, str(values[2] or ''), f'{qty:g}',
                     str(values[4] or 'Nos'), *pricing])

    if not rows:
        raise ValueError('The Quotation worksheet does not contain any quotation items.')
    if not terms_found:
        terms = list(TERMS)
    return metadata, rows, terms, total_amount, total_gst


def build_pdf_from_excel(file_stream, filename='Quotation-edited'):
    """Render edited Excel items, totals and terms in the reference PDF layout."""
    from openpyxl import load_workbook
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    workbook = load_workbook(file_stream, data_only=True)
    try:
        if 'Quotation' not in workbook.sheetnames:
            raise ValueError('The Excel file must contain a Quotation worksheet.')
        metadata, rows, terms, total_amount, total_gst = read_excel_quotation(workbook['Quotation'])
    finally:
        workbook.close()

    small = ParagraphStyle('QuotationSmall', fontName='Helvetica', fontSize=7, leading=7.5)
    bold = ParagraphStyle('QuotationBold', parent=small, fontName='Helvetica-Bold')
    term_style = ParagraphStyle('QuotationTerm', parent=small, leading=8, spaceBefore=3)
    heading_style = ParagraphStyle('QuotationHeading', parent=bold, spaceBefore=6,
                                   spaceAfter=2, keepWithNext=True)

    def paragraph(value, style=small):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    def field(name, key):
        value = escape(metadata.get(key, ''))
        return Paragraph(f'<b>{name}:</b> {value}', small)

    left_rows = [[field(name, key)] for name, key in [
        ('Client Name', 'clientname'), ('Project Detail', 'projectdetail'),
        ('Location', 'location'), ('Sub', 'sub'),
    ]]
    right_rows = [[field(name, key)] for name, key in [
        ('Date', 'date'), ('Sales Person', 'salesperson'), ('Version', 'version'),
    ]]
    if metadata.get('contactdetails'):
        right_rows.append([field('Contact Details', 'contactdetails')])
    info = Table([[Table(left_rows, colWidths=[112*mm]),
                   Table(right_rows, colWidths=[112*mm])]], colWidths=[112*mm, 112*mm],
                 minRowHeights=[24*mm])
    info.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story = [info, Spacer(1, 2*mm)]

    widths = [value*mm for value in (12, 26, 66, 10, 12, 19, 12, 20, 22, 25)]
    headers = ['Sr. No.', 'Item', 'Description', 'Qty', 'Unit', 'Rate', 'GST',
               'GST amount', 'Rate incl.\ntaxes', 'Amount']
    table_rows = [[paragraph(value) for value in headers]]
    table_rows.extend([[paragraph(value) for value in row] for row in rows])
    table = Table(table_rows, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9e9f4')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(table)

    totals = Table([
        [''] * 8 + [paragraph('Total Amount', bold), paragraph(f'{total_amount:,.2f}')],
        [''] * 8 + [paragraph('GST Amount', bold), paragraph(f'{total_gst:,.2f}')],
    ], colWidths=widths)
    totals.setStyle(TableStyle([
        ('GRID', (8, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(totals)
    if terms:
        story.append(paragraph('Terms and conditions:', heading_style))
        story.extend(paragraph(f'{index}) {term}', term_style) for index, term in enumerate(terms, 1))

    return build_single_page_quotation(story, Path(__file__).parent,
                                       filename or 'Edited PROMARK Video Wall Quotation')
