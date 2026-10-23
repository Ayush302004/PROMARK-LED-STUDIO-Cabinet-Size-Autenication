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
    controller_desc=' '.join(str(q.get('controller_description') or (controller or {}).get('description') or f"Supply of video wall controller: {data.get('controller') or 'To be selected'}. Capacity and compatibility to be confirmed.").split())
    if controller:
        for old_name in controller.get('legacy_names', ['Huidu '+controller['id'], controller['id']]):
            controller_desc=controller_desc.replace(old_name,controller['name'])
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
      ((controller or {}).get('kind','LED Wall Controller'),controller_desc,numeric(q.get('controller_qty'),'Controller quantity',1,100000),'Nos',None),
      ('Mounting Structure',manual_description(q.get('mount_description'),'Mounting structure'),1,'Nos',None),
      ('Installation',manual_description(q.get('installation_description'),'Installation charges'),1,'Nos',None),
      ('UPS',manual_description(None,'UPS'),1,'Nos',None),
      ('Cabling',manual_description(None,'Cabling'),1,'Nos',None)]
    last_item_row=9+len(lines)
    total_row=last_item_row+1
    for rn,(item,desc,qty,unit,rate) in enumerate(lines,10):
        for col,value in enumerate([rn-9,item,desc,qty,unit,numeric(rate,item+' rate'),gst],1):ws.cell(rn,col,text(value) if isinstance(value,str) else value)
        ws.cell(rn,8,f'=IF(F{rn}="","",ROUND(F{rn}*G{rn},2))')
        ws.cell(rn,9,f'=IF(F{rn}="","",ROUND(F{rn}+H{rn},2))')
        ws.cell(rn,10,f'=IF(F{rn}="","",ROUND(D{rn}*I{rn},2))')
        ws.row_dimensions[rn].height=max(180, 15 * (len(desc) // 75 + desc.count('\n') + 2)) if rn==10 else (max(100, 15 * (math.ceil(len(desc) / 70) + 2)) if rn==11 else 35)
        for col in [4,6,7]:ws.cell(rn,col).fill=PatternFill('solid',fgColor='FFF2CC')
        ws.cell(rn,7).number_format='0%'
        for col in [6,8,9,10]:ws.cell(rn,col).number_format='#,##0.00'
    for row, source in ((10,2),):
        factor=''
        ws.cell(row,6,f'=IF(\'Design & Specifications\'!B{source}="","",ROUND(\'Design & Specifications\'!B{source}{factor}*\'Design & Specifications\'!B3,2))')
        ws.cell(row,4).number_format='0'
    merged(total_row,1,9,'Total Amount',True)
    ws.cell(total_row,10,f'=IF(COUNT(F10:F{last_item_row})<{len(lines)},"Rates pending",ROUND(SUM(J10:J{last_item_row}),2))')
    ws.cell(total_row,10).number_format='#,##0.00'
    merged(18,1,10,'Terms and conditions:',True)
    for row,term in enumerate(TERMS,19):merged(row,1,10,f'{row-18}.) {term}');ws.row_dimensions[row].height=22
    merged(29,1,10,'You may kindly raise the Purchase Order & Cheque / DD for advance amount in favour of:')
    merged(30,1,10,'Promark Techsolutions Pvt. Ltd.',True)
    merged(31,1,10,'CIN: '+str(q.get('cin','U36109PB2010PTC034337'))+'    GST: '+str(q.get('company_gst','03AAFCP7669C1ZF'))+'    PAN: '+str(q.get('pan','AAFCP7669C')) ,True)
    merged(33,1,10,'We hope the estimate is in line with your requirements. For any clarifications, please get back to us.')
    merged(34,1,10,'Thanks & Regards')
    merged(36,1,10,'Editable yellow cells: quantities, rates and GST. LED total = cabinet rate × screen sq.ft. Controller rates are pending revision and are not calculated. Mounting structure, installation, UPS and cabling are not priced automatically. Enter the company actual prices directly in Rate cells F12:F15. Enter 0 for an included / no-charge item. Blank rates keep the final total pending.')
    ws.row_dimensions[36].height=44
    thin=Side(style='thin',color='000000')
    for row in ws.iter_rows(min_row=8,max_row=total_row,max_col=10):
        for cell in row:
            cell.border=Border(left=thin,right=thin,top=thin,bottom=thin)
            cell.font=Font(name='Calibri',size=11,bold=cell.row in (8,9,total_row))
            cell.alignment=Alignment(wrap_text=True,vertical='center',horizontal='left' if cell.column==3 else 'center')
    ws.row_dimensions[8].height=34
    for cells,maxval in [(f'F10:F{last_item_row}',1e12),(f'D10:D{last_item_row}',100000),(f'G10:G{last_item_row}',1)]:
        dv=DataValidation(type='decimal',operator='between',formula1=0,formula2=maxval,allow_blank=True);dv.showErrorMessage=True;dv.error='Enter a non-negative number within the allowed range.';ws.add_data_validation(dv);dv.add(cells)
    ws.freeze_panes='D10';ws.print_options.horizontalCentered=True;ws.print_area='A1:J36'
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.sheet_properties.pageSetUpPr.fitToPage=True
    specs=wb.create_sheet('Design & Specifications');specs.column_dimensions['A'].width=42;specs.column_dimensions['B'].width=100
    rows=[('LED rate calculation','Cabinet rate per sq.ft. × screen area'),('LED base rate',numeric(q.get('wall_rate'),'LED base rate')),('Screen area (sq.ft.)',sqft),('Mounting structure rate (enter in Quotation!F12)',None),('Installation rate (enter in Quotation!F13)',None),('Controller pricing','Pending revised controller rates; not calculated.'),('Selected model',p['name']),('Selected cabinet dimensions (mm)',dimensions),('Technology',p.get('technology','Not specified')),('Cabinet quantity',result['count']),('Columns × rows',f"{result['columns']} × {result['rows']}"),('Buildable dimensions (m)',f'{sw} × {sh}'),('Pricing area (sq.ft.)',sqft),('Video resolution',resolution(result)),('Total pixels',result['total_pixels'] if result['total_pixels'] is not None else 'Not provided'),('Controller',((controller or {}).get('name') or data.get('controller') or 'To be selected')),('Controller verification','Supplied model specifications; receiving-card compatibility and port mapping require confirmation' if controller else 'Capacity and compatibility pending'),('Specification notes',p.get('notes',''))]
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
    for cell in ('B2','B3'):specs[cell].fill=PatternFill('solid',fgColor='FFF2CC')
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
    unit_rates=[numeric(q.get('wall_rate'),'LED rate')]+[None]*5
    for row,rate in zip(range(10,last_item_row+1),unit_rates):
        if rate is None:
            for col in ('F','H','I','J'):
                if ws[f'{col}{row}'].data_type=='f':cached[f'{col}{row}']=''
            continue
        full=money(Decimal(str(rate))*sqft_decimal) if row!=11 else money(rate*130*2)
        cached[f'F{row}']=full
        tax=money(full*gst);gross=money(full+tax)
        cached[f'H{row}']=tax;cached[f'I{row}']=gross;cached[f'J{row}']=money(float(ws.cell(row,4).value)*gross)
    cached[f'J{total_row}']='Rates pending' if any(v is None for v in unit_rates) else money(sum(cached[f'J{r}'] for r in range(10,last_item_row+1)))
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
