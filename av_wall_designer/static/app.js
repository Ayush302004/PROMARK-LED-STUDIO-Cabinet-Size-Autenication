'use strict';
const $ = id => document.getElementById(id);
const fields = ['controller', 'technology', 'q_client', 'q_project', 'q_location', 'q_contact', 'q_date', 'q_salesperson', 'q_version', 'q_subject', 'q_wall_rate', 'q_controller_qty', 'q_mount_type', 'q_mount_rate', 'q_mount_qty', 'q_installation_rate', 'q_gst', 'q_controller_description', 'q_mount_description', 'q_installation_description', 'q_cin', 'q_company_gst', 'q_pan', 'dimension_step', 'preview_mode', 'size_preset', 'wall_width', 'wall_height', 'screen_width', 'screen_height', 'columns', 'rows', 'target_pixels_w', 'target_pixels_h', 'mode', 'policy', 'position', 'left', 'bottom', 'installation', 'finish', 'wall_colour', 'human_height', 'content'];
const MOUNTING_OPTIONS = {
    unipole: { name: 'Uni-pole', rate: 175000, description: 'Supply of Uni-pole.' },
    structure: { name: 'Mounting structure', rate: 800, description: 'Supply of mounting structure for the LED video wall.' },
};
let controllers = [], catalogue = [], product = null, result = null, lastGoodResult = null, unit = 'ft', environment = 'indoor', scene = 'Video wall', zoom = 1, wallPhoto = '', screenPhoto = '', revision = 0, timer = null;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const resolutionText = p => p && p.pixels_w != null && p.pixels_h != null ? `${Number(p.pixels_w).toLocaleString('en-IN')} × ${Number(p.pixels_h).toLocaleString('en-IN')} px` : 'Not provided';
const totalPixelsText = r => r?.pixels_w != null && r?.pixels_h != null ? `${fmt(r.pixels_w * r.pixels_h)} pixels · ${(r.pixels_w * r.pixels_h / 1000000).toFixed(3)} million` : 'Total pixels: not provided';
function controllerDescription(c, description) { let text = description || c?.description || ''; for (const name of c?.legacy_names || []) text = text.split(name).join(c.name); return text; }
function updateControllerRecommendation() {
    if (!result) return;
    const c = recommendVideoController(controllers, result.pixels_w, result.pixels_h);
    const selected = controllers.find(item => item.id === $('controller').value);
    const known = result.pixels_w != null && result.pixels_h != null;
    let text = !known ? 'Recommendation unavailable: cabinet pixel resolution is not provided.' : !c ? 'No supplied video controller has spare capacity within the required width and height limits. Review the controller configuration.' : `Recommended: ${c.name} · ${(c.max_pixels / 1000000).toFixed(3)} million pixels capacity for ${(result.pixels_w * result.pixels_h / 1000000).toFixed(3)} million pixels. Width and height limits checked.`;
    if ($('controller-auto').checked) {
        if ($('controller').value !== (c?.id || '')) {
            $('controller').value = c?.id || ''; applyControllerSelection();
        }
    } else if (selected && known && (selected.max_pixels == null || selected.max_pixels < result.pixels_w * result.pixels_h || selected.max_width == null || selected.max_width < result.pixels_w || selected.max_height == null || selected.max_height < result.pixels_h)) {
        text += ' Selected controller capacity or dimensions are insufficient or unconfirmed.';
    }
    $('controller-recommendation').textContent = text;
}
const cabinetDimensions = p => `${fmt(p.width_mm)} × ${fmt(p.height_mm)}${p.depth_mm != null ? ' × ' + fmt(p.depth_mm) : ''} mm`;
function exactArea(width, height) {
    const parts = value => { const s = String(value).trim(); if (!/^\d+(\.\d*)?$/.test(s)) return null; const [whole, frac = ''] = s.split('.'); return [BigInt(whole + frac), frac.length]; };
    const a = parts(width), b = parts(height); if (!a || !b) return '—';
    const scale = a[1] + b[1]; let digits = String(a[0] * b[0]).padStart(scale + 1, '0');
    if (scale) digits = digits.slice(0, -scale) + '.' + digits.slice(-scale);
    return scale ? digits.replace(/0+$/, '').replace(/\.$/, '') : digits;
}
const fmt = n => Number(n).toLocaleString('en-IN', { maximumFractionDigits: 3 });
const money = n => Number(n).toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
function outdoorPrecision() { return environment === 'outdoor' || Number(product?.pitch_mm) === 4; }
function dimensionFormat(value, places = 3) {
    let text = String(value);
    if (/e/i.test(text) && Number.isFinite(Number(text))) text = exactDecimalStep(text, '0', 1);
    const point = text.indexOf('.'); if (outdoorPrecision() && point >= 0) return text.slice(0, point + places + 1); if (point < 0 || text.length - point - 1 <= places) return text; const n = Number(text); return Number.isFinite(n) ? n.toFixed(places) : text.slice(0, point + places + 1);
}
const heightFormat = v => dimensionFormat(v, 3);
const isHeightId = id => id === 'screen_height' || id === 'wall_height' || id === 'bottom';
const inputFormat = (id, v) => isHeightId(id) ? heightFormat(v) : dimensionFormat(v);
const dimensionInput = dimensionFormat;
function formatDimensionInputs() { ['wall_width', 'wall_height', 'screen_width', 'screen_height', 'left', 'bottom', 'human_height'].forEach(id => { const input = $(id); if (input.value.trim() !== '' && Number.isFinite(Number(input.value))) input.value = inputFormat(id, input.value); }); }
function decimalParts(value) {
    const match = String(value).match(/^([+-]?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
    if (!match || (!match[2] && !match[3])) throw Error('Invalid decimal');
    const fraction = match[3] || '', exponent = Number(match[4] || 0); let scale = fraction.length - exponent;
    let coefficient = BigInt((match[2] || '0') + fraction) * (match[1] === '-' ? -1n : 1n);
    if (scale < 0) { coefficient *= 10n ** BigInt(-scale); scale = 0; }
    return { coefficient, scale };
}
function exactDecimalStep(value, step, direction) {
    const a = decimalParts(value), b = decimalParts(step), scale = Math.max(a.scale, b.scale);
    const total = a.coefficient * 10n ** BigInt(scale - a.scale) + BigInt(direction) * b.coefficient * 10n ** BigInt(scale - b.scale);
    const negative = total < 0n, digits = (negative ? -total : total).toString().padStart(scale + 1, '0');
    return (negative ? '-' : '') + (scale ? digits.slice(0, -scale) + '.' + digits.slice(-scale) : digits);
}

const display = m => m / (unit === 'ft' ? 0.3048 : 1);
function message(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
async function api(url, body) {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add authentication token if available
    const token = localStorage.getItem('access_token');
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(url, body === undefined ? { headers } : { 
        method: 'POST', 
        headers, 
        body: JSON.stringify(body),
        credentials: 'include'
    });
    
    const data = await response.json();
    
    // If unauthorized, redirect to login
    if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        throw Error('Authentication required');
    }
    
    if (!response.ok) throw Error(data.error || 'Request failed');
    return data;
}
function state() { const data = { unit, environment, scene, product }; fields.forEach(id => data[id] = $(id).value); data.controller_price_mode = 'base_x130_x2'; data.auto_controller = $('controller-auto').checked; data.quotation = Object.fromEntries(fields.filter(id => id.startsWith('q_')).map(id => [id.slice(2), $(id).value])); return data; }
function updateVisibility() { updateDimensionSteps(); const known = product && product.pixels_w != null && product.pixels_h != null; $('mode').querySelector('option[value="resolution"]').disabled = !known; if (!known && $('mode').value === 'resolution') $('mode').value = 'dimensions';['dimensions', 'grid', 'resolution'].forEach((v, i) => $(['dimension-fields', 'grid-fields', 'resolution-fields'][i]).hidden = $('mode').value !== v); $('position-fields').hidden = $('position').value === 'centre'; const custom = $('resolution').value === 'custom'; $('target_pixels_w').disabled = !custom; $('target_pixels_h').disabled = !custom; }
function familyFor(p) {
    if (!p) return null;
    return catalogue.find(item => item.id === p.family_id || item.id === p.id || item.cabinet_options?.some(option => option.id === p.id)) || null;
}
function familyId(p) { return familyFor(p)?.id || p?.id; }
function resolveCabinet(family, optionId) {
    if (!family) return null;
    if (!family.cabinet_options?.length) return { ...family };
    const option = family.cabinet_options.find(item => item.id === (optionId || family.default_cabinet_id)) || family.cabinet_options[0];
    return { ...option, name: family.name, technology: family.technology || option.technology, family_id: family.id, cabinet_option_id: option.id };
}
function renderCabinetSizes() {
    const family = familyFor(product), options = family?.cabinet_options || [product].filter(Boolean);
    $('cabinet_size').replaceChildren(...options.map(p => new Option(cabinetDimensions(p), p.id)));
    if (product) $('cabinet_size').value = product.id;
    $('cabinet_size').disabled = options.length < 2;
}
function filteredProducts(value = environment) { return catalogue.filter(p => p.environment === value && ($('technology').value === 'all' || p.technology === $('technology').value)); }
function renderTechnology() { document.querySelectorAll('#technology-buttons button').forEach(b => { b.classList.toggle('active', b.dataset.value === $('technology').value); b.setAttribute('aria-pressed', String(b.dataset.value === $('technology').value)); b.disabled = b.dataset.value !== 'all' && !catalogue.some(p => p.environment === environment && p.technology === b.dataset.value); }); $('technology-hint').textContent = environment === 'outdoor' ? 'Outdoor · SMD available' : 'Filter by SMD or COB, or browse all models.'; }
function selectEnvironment(value, retain = false) { environment = value; $('environment').value = value; if (!filteredProducts(value).length) $('technology').value = 'all'; const options = filteredProducts(value); if (!retain || !product || !options.some(p => p.id === familyId(product))) product = resolveCabinet(options[0]); if (!retain) resetScreenDefaults(); renderProducts(); schedule(); }
function renderProducts() { $("q_wall_rate").value = product?.base_rate_sqft ?? ""; renderTechnology(); const options = filteredProducts(); $('product').replaceChildren(...options.map(p => new Option(p.name, p.id))); if (product) $('product').value = familyId(product); renderCabinetSizes(); $('product-summary').innerHTML = product ? [["Cabinet", cabinetDimensions(product)], ["Pitch", `P${product.pitch_mm}`], ["Brightness", `${product.brightness_nits ?? '—'} nits`], ["Refresh", `${product.refresh_hz ?? '—'} Hz`], ["Service", product.maintenance || '—']].map(([label, value]) => `<span class="cabinet-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></span>`).join('') : 'No models available'; const fig = $('product-figure'), src = product && modelImage(product, 'x'); if (src) { $('product-image').src = '/static/' + product.image; $('product-image').alt = product.name; $('product-caption').textContent = (product.image_caption || '').split(' · ')[0]; fig.hidden = false; } else fig.hidden = true; renderCatalogue(); updateVisibility(); }
function selectScene(name) { scene = 'Video wall'; }
function modelDefaults(which = unit) {
    if (product && product.design_defaults && product.design_defaults[which]) return product.design_defaults[which];
    const factor = which === 'ft' ? 1 / .3048 : 1;
    return { width: (product?.width_mm || 640) / 1000 * factor, height: (product?.height_mm || 480) / 1000 * factor, width_step: (product?.width_mm || 640) / 1000 * factor, height_step: (product?.height_mm || 480) / 1000 * factor };
}
const wallDefaults = { m: { width: 5, height: 3 }, ft: { width: 16.4, height: 9.84 } };
function resetScreenDefaults() {
    const d = modelDefaults(); $('screen_width').value = dimensionInput(d.width); $('screen_height').value = heightFormat(d.height);
    $('columns').value = 1; $('rows').value = 1; $('dimension_step').value = 'cabinet'; $('mode').value = 'dimensions'; $('policy').value = 'nearest'; $('size_preset').value = 'model';
}
function changeUnits(next) {
    if (next === unit) return;
    const before = unit, from = modelDefaults(before), to = modelDefaults(next), factor = next === 'ft' ? 1 / .3048 : .3048;
    ['wall_width', 'wall_height', 'screen_width', 'screen_height', 'left', 'bottom', 'human_height'].forEach(id => {
        const input = $(id); if (input.value.trim() === '') return; const value = Number(input.value); if (!Number.isFinite(value)) return;
        let converted = value * factor;
        if (id.startsWith('screen_')) {
            const axis = id.endsWith('width') ? 'width' : 'height', n = (value - from[axis]) / from[axis + '_step'];
            if (n >= 0 && Math.abs(n - Math.round(n)) < 1e-7) converted = to[axis] + Math.round(n) * to[axis + '_step'];
        } else if (id.startsWith('wall_')) {
            const axis = id.endsWith('width') ? 'width' : 'height'; if (Math.abs(value - wallDefaults[before][axis]) < 1e-8) converted = wallDefaults[next][axis];
        }
        input.value = inputFormat(id, converted);
    });
    unit = next; document.querySelectorAll('#units button').forEach(b => b.classList.toggle('active', b.dataset.value === next)); document.querySelectorAll('.unit').forEach(el => el.textContent = unit); $('human_height').max = unit === 'ft' ? 10 : 3; updateDimensionSteps(); schedule();
}

function autoExpandWallForScreen(screenWidth, screenHeight) {
    const wallWInput = $('wall_width'), wallHInput = $('wall_height');
    const wallW = Number(wallWInput.value), wallH = Number(wallHInput.value);
    if (!Number.isFinite(screenWidth) || !Number.isFinite(screenHeight) || screenWidth <= 0 || screenHeight <= 0) return false;

    // Keep a clearly visible wall border around an auto-fitted screen instead of
    // expanding the wall to exactly the same dimensions as the LED display.
    // 1 ft (or roughly 0.30 m) on every side gives a practical visual clearance.
    const clearance = unit === 'ft' ? 1 : 0.30;
    const custom = $('position').value === 'custom';
    const left = custom ? Math.max(0, Number($('left').value) || 0) : clearance;
    const bottom = custom ? Math.max(0, Number($('bottom').value) || 0) : clearance;
    const rightClearance = clearance;
    const topClearance = clearance;
    const requiredW = screenWidth + left + rightClearance;
    const requiredH = screenHeight + bottom + topClearance;

    // Wall inputs are displayed at 4 decimals for width and 3 for height. Always round
    // outward when auto-expanding so formatting can never make the wall microscopically
    // smaller than the calculated screen and trigger an endless Updating… loop.
    const outward = (value, places) => Math.ceil((value - 1e-12) * 10 ** places) / 10 ** places;
    const targetW = outward(requiredW, 4), targetH = outward(requiredH, 3);
    const nextW = dimensionInput(targetW), nextH = heightFormat(targetH);
    let changed = false;
    if ((!Number.isFinite(wallW) || wallW + 1e-9 < requiredW) && wallWInput.value !== nextW) { wallWInput.value = nextW; changed = true; }
    if ((!Number.isFinite(wallH) || wallH + 1e-9 < requiredH) && wallHInput.value !== nextH) { wallHInput.value = nextH; changed = true; }
    return changed;
}
function autoExpandWallFromResult(r) {
    if (!r) return false;
    const exact = r.design || {};
    const screenWidthM = Math.max(Number(r.width_m) || 0, Number(exact.width_m) || 0);
    const screenHeightM = Math.max(Number(r.height_m) || 0, Number(exact.height_m) || 0);
    return autoExpandWallForScreen(display(screenWidthM), display(screenHeightM));
}
function schedule() {
    formatDimensionInputs();
    if ($('mode').value === 'dimensions') autoExpandWallForScreen(Number($('screen_width').value), Number($('screen_height').value));
    document.querySelectorAll('[data-pixel-axis]').forEach(button => button.disabled = true); clearTimeout(timer); revision++; result = null; $('results-btn').disabled = true; $('fit-status').textContent = 'Updating design…'; $('drawing').setAttribute('aria-busy', 'true'); $('size-feedback').hidden = true; liveExactPreview(); timer = setTimeout(() => recalculate(revision), 80);
}
async function recalculate(version) { try { const data = await api('/api/calculate', state()); if (version !== revision) return; if (autoExpandWallFromResult(data)) { schedule(); return; } result = data; lastGoodResult = data; $('metrics').setAttribute('aria-busy', 'false'); $('drawing').setAttribute('aria-busy', 'false'); message(''); $('results-btn').disabled = false; render(); } catch (e) { if (version !== revision) return; result = null; $('drawing').setAttribute('aria-busy', 'false'); $('size-feedback').hidden = true; message(e.message, true); $('wall-svg').replaceChildren(); $('metrics').replaceChildren(); $('fit-status').textContent = 'Invalid design'; $('warnings').textContent = 'Correct the input values to calculate this design.'; $('materials').replaceChildren(); updatePixelControls(null); $('result-summary').textContent = 'No valid calculated design.'; $('result-drawing').replaceChildren(); } }
function render() { updateControllerRecommendation(); updateFullPrices(); updatePixelControls(result); draw(); const r = result, d = $('preview_mode').value === 'exact' ? r.design : r; const exact = $('preview_mode').value === 'exact'; const metric = (title, value, note) => `<div class="metric"><span>${title}</span><strong>${value}</strong><small>${note}</small></div>`; $('metrics').innerHTML = metric(exact ? 'Exact design size' : 'Buildable screen size', `${exact && $('mode').value === 'dimensions' ? esc(dimensionFormat($('screen_width').value)) : dimensionFormat(display(d.width_m))} × ${exact && $('mode').value === 'dimensions' ? esc(heightFormat($('screen_height').value)) : heightFormat(display(d.height_m))}`, unit) + metric('Video resolution', resolutionText(r), totalPixelsText(r)) + metric('Cabinet option', `${r.columns} × ${r.rows}`, `${fmt(r.count)} cabinets`) + metric(exact ? 'Design area' : 'Cabinet area', exactArea(exact && $('mode').value === 'dimensions' ? $('screen_width').value : dimensionFormat(display(d.width_m)), exact && $('mode').value === 'dimensions' ? $('screen_height').value : heightFormat(display(d.height_m))), unit === 'ft' ? 'ft²' : 'm²'); $('warnings').replaceChildren(...r.warnings.map(w => { const p = document.createElement('p'); p.textContent = w; return p; })); $('fit-status').textContent = d.fits ? '✓ Fits within wall' : '⚠ Exceeds wall'; $('fit-status').style.color = d.fits ? '#087d79' : '#a43b34'; renderSizeFeedback(); renderResults(); }
function draw(r = result) {
    if (!r) return; const exact = $('preview_mode').value === 'exact', d = exact ? r.design : r; const W = r.wall_width_m, H = r.wall_height_m, sw = d.width_m, sh = d.height_m, l = d.margins_m.left, b = d.margins_m.bottom, t = H - sh - b; $('show-grid').disabled = false; const req = !exact && r.requested && r.requested.width_m !== undefined ? r.requested : null, rw = req ? req.width_m : sw, rh = req ? req.height_m : sh, rl = $('position').value === 'centre' ? (W - rw) / 2 : l, rt = $('position').value === 'centre' ? (H - rh) / 2 : H - b - rh; const minX = Math.min(0, l, rl), maxX = Math.max(W, l + sw, rl + rw), minY = Math.min(0, t, rt), maxY = Math.max(H, t + sh, rt + rh); const scale = Math.min(730 / (maxX - minX), 350 / (maxY - minY)), x = 145 - minX * scale, y = 80 - minY * scale, ww = W * scale, hh = H * scale, sx = x + l * scale, sy = y + t * scale, sww = sw * scale, shh = sh * scale; const svg = $('wall-svg'); svg.setAttribute('viewBox', '0 0 1030 530'); svg.style.width = `${zoom * 100}%`; $('zoom-value').textContent = `${Math.round(zoom * 100)}%`; const colour = /^#[a-f0-9]{6}$/i.test($('wall_colour').value) ? $('wall_colour').value : '#dce3e4'; let texture = ''; switch ($('finish').value) { case 'brick': texture = '<pattern id="finish-pattern" width="60" height="30" patternUnits="userSpaceOnUse"><path d="M0 0H60M0 15H60M0 30H60M0 0V15M30 15V30M60 0V15" fill="none" stroke="#647571" stroke-opacity=".22"/></pattern>'; break; case 'wood': texture = '<pattern id="finish-pattern" width="34" height="100" patternUnits="userSpaceOnUse"><path d="M0 0V100M6 0Q17 30 8 65T8 100" fill="none" stroke="#705d45" stroke-opacity=".25"/></pattern>'; break; case 'concrete': texture = '<pattern id="finish-pattern" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="3" cy="4" r="1" fill="#677976" opacity=".18"/><circle cx="9" cy="10" r=".6" fill="#677976" opacity=".2"/></pattern>'; break; }
    const image = (url, px, py, pw, ph) => `<image href="${esc(url)}" x="${px}" y="${py}" width="${pw}" height="${ph}" preserveAspectRatio="xMidYMid slice"/>`;
    let wall = `<rect x="${x}" y="${y}" width="${ww}" height="${hh}" fill="${colour}"/>`; if (texture) wall += `<rect x="${x}" y="${y}" width="${ww}" height="${hh}" fill="url(#finish-pattern)"/>`; if (wallPhoto) wall += image(wallPhoto, x, y, ww, hh);
    let screen = `<rect x="${sx}" y="${sy}" width="${sww}" height="${shh}" fill="${$('content').value === 'black' ? '#101c22' : 'url(#screen-gradient)'}"/>`; if ($('content').value === 'sample') screen += image('/static/default-led-screen.jpg', sx, sy, sww, shh); else if ($('content').value === 'image' && screenPhoto) screen += image(screenPhoto, sx, sy, sww, shh); else if ($('content').value === 'gradient') { screen += `<g clip-path="url(#screen-clip)"><circle cx="${sx + sww * .7}" cy="${sy + shh * .5}" r="${shh * .65}" fill="none" stroke="#8ae5c4" stroke-opacity=".25" stroke-width="${shh * .12}"/><path d="M${sx - sww * .2} ${sy + shh * .9}Q${sx + sww * .5} ${sy - shh * .3} ${sx + sww * 1.2} ${sy + shh * .8}" stroke="#7bd1cb" stroke-width="${shh * .1}" fill="none" opacity=".2"/></g>`; if (sww > 130 && shh > 60) screen += `<text x="${sx + sww * .08}" y="${sy + shh * .52}" fill="white" font-size="${Math.min(35, shh * .14)}" font-weight="600">Your vision.</text><text x="${sx + sww * .08}" y="${sy + shh * .7}" fill="#b4e5d9" font-size="${Math.min(22, shh * .09)}">At any scale.</text>`; }
    if ($('show-grid').checked) { const xs = [], ys = []; if (!exact) { if (r.columns <= 100 && r.rows <= 100) { for (let c = 1; c < r.columns; c++)xs.push(c * sww / r.columns); for (let row = 1; row < r.rows; row++)ys.push(row * shh / r.rows); } } else if (product && product.width_mm > 0 && product.height_mm > 0) { const cw = product.width_mm / 1000 * scale, ch = product.height_mm / 1000 * scale; if (sww / cw <= 200 && shh / ch <= 200) { for (let k = 1; k * cw < sww - .5; k++)xs.push(k * cw); for (let k = 1; k * ch < shh - .5; k++)ys.push(shh - k * ch); } } let gd = ''; xs.forEach(v => gd += `M${sx + v} ${sy}V${sy + shh}`); ys.forEach(v => gd += `M${sx} ${sy + v}H${sx + sww}`); if (gd) screen += `<g data-grid fill="none"><path d="${gd}" stroke="#000" stroke-opacity=".35" stroke-width="2"/><path d="${gd}" stroke="#fff" stroke-opacity=".85" stroke-width=".9"/></g>`; }
    const text = (tx, ty, label, anchor = 'middle') => `<text class="${tx >= x && tx <= x + ww && ty >= y && ty <= y + hh ? 'dimension-inside' : 'dimension-outside'}" x="${tx}" y="${ty}" fill="#52666b" font-size="12" text-anchor="${anchor}">${esc(label)}</text>`;
    const line = (x1, y1, x2, y2) => `<path d="M${x1} ${y1}L${x2} ${y2}" stroke="#82958f" stroke-width="1"/>`;
    let labels = line(x, y - 22, x + ww, y - 22) + line(x, y - 27, x, y - 17) + line(x + ww, y - 27, x + ww, y - 17) + text(x + ww / 2, y - 34, `Wall ${dimensionFormat($('wall_width').value)} ${unit}`) + line(x + ww + 35, y, x + ww + 35, y + hh) + text(x + ww + 42, $('show-spaces').checked ? y + hh + 16 : y + hh / 2, `${$('show-spaces').checked ? 'Wall ' : ''}${heightFormat($('wall_height').value)} ${unit}`, 'start') + text(sx + sww / 2, sy - 9, `${exact ? 'Design' : 'Cabinets'} ${exact && $('mode').value === 'dimensions' ? dimensionFormat($('screen_width').value) : dimensionFormat(display(sw))} × ${exact && $('mode').value === 'dimensions' ? heightFormat($('screen_height').value) : heightFormat(display(sh))} ${unit}`) + text(x + ww / 2, y + hh + 26, `Bottom ${heightFormat(display(b))} ${unit} · Top ${heightFormat(display(d.margins_m.top))} ${unit}`) + text(x + ww / 2, y + hh + 46, `Left ${dimensionFormat(display(l))} ${unit} · Right ${dimensionFormat(display(d.margins_m.right))} ${unit}`);
    if ($('show-spaces').checked) {
        const sx2 = sx + sww, sy2 = sy + shh, fd = v => `${dimensionFormat(display(v))} ${unit}`, fh = v => `${heightFormat(display(v))} ${unit}`, dot = (a, c, e, f) => `<path d="M${a} ${c}L${e} ${f}" stroke="#4f6f68" stroke-width="1.2" stroke-dasharray="1.5 4" stroke-linecap="round" fill="none"/>`, tick = (a, c, e, f) => `<path d="M${a} ${c}L${e} ${f}" stroke="#82958f" stroke-width="1"/>`;
        const pxW = r.pixels_w != null && (!exact || Math.abs(sw - r.width_m) < 1e-6) ? r.pixels_w : null, pxH = r.pixels_h != null && (!exact || Math.abs(sh - r.height_m) < 1e-6) ? r.pixels_h : null;
        const small = (tx, ty, label, anchor = 'middle') => `<text class="${tx >= x && tx <= x + ww && ty >= y && ty <= y + hh ? 'dimension-inside' : 'dimension-outside'}" x="${tx}" y="${ty}" fill="#3d5750" font-size="11.5" text-anchor="${anchor}">${esc(label)}</text>`;
        let g = dot(sx, y - 22, sx, sy) + dot(sx2, y - 22, sx2, sy) + dot(x, y - 22, x, y) + dot(x + ww, y - 22, x + ww, y) + tick(sx, y - 27, sx, y - 17) + tick(sx2, y - 27, sx2, y - 17);
        g += dot(sx2, sy, x + ww + 35, sy) + dot(sx2, sy2, x + ww + 35, sy2) + dot(x + ww, y, x + ww + 35, y) + dot(x + ww, y + hh, x + ww + 35, y + hh) + tick(x + ww + 30, sy, x + ww + 40, sy) + tick(x + ww + 30, sy2, x + ww + 40, sy2);
        const row = (a, c, label) => Math.abs(c - a) > label.length * 6 + 6 ? small((a + c) / 2, y - 8, label) : '', col = (a, c, label) => Math.abs(c - a) > 16 ? small(x + ww + 42, (a + c) / 2 + 4, label, 'start') : '';
        g += row(x, sx, fd(l)) + row(sx, sx2, `${fd(sw)}${pxW ? ` (${fmt(pxW)} px)` : ''}`) + row(sx2, x + ww, fd(d.margins_m.right));
        g += col(y, sy, fh(t)) + col(sy, sy2, `${fh(sh)}${pxH ? ` (${fmt(pxH)} px)` : ''}`) + col(sy2, y + hh, fh(b));
        labels += g;
    }
    let viewing = '';
    if ($('show-spaces').checked && product && Number(product.pitch_mm) > 0) {
        // Rule of thumb: minimum comfortable viewing distance in metres ≈ pixel pitch in millimetres.
        const vm = Number(product.pitch_mm), vx1 = 100, vy1 = y + hh + 7, vx2 = x, vy2 = y + hh, ang = Math.atan2(vy2 - vy1, vx2 - vx1) * 180 / Math.PI, vlabel = `${(Math.round(display(vm) * 10) / 10).toLocaleString('en-IN')} ${unit}`;
        viewing = `<path d="M${vx1} ${vy1}L${vx2} ${vy2}" stroke="#4f6f68" stroke-width="1.2" stroke-dasharray="1.5 4" stroke-linecap="round" fill="none"/><path d="M${vx1} ${vy1 - 4}V${vy1 + 4}M${vx2} ${vy2 - 4}V${vy2 + 4}" stroke="#82958f"/><text transform="translate(${(vx1 + vx2) / 2} ${(vy1 + vy2) / 2 - 5}) rotate(${ang})" fill="#3d5750" font-size="11.5" text-anchor="middle">${esc(vlabel)}</text>${text(78, y + hh + 43, 'Best viewing distance')}`;
    }
    const human = Number($('human_height').value) * (unit === 'ft' ? 0.3048 : 1), humanH = Number.isFinite(human) && human > 0 ? Math.min(human * scale, 470) : 0;
    const person = `<g transform="translate(90 ${y + hh - humanH}) scale(${humanH / 175})" fill="#789b94"><circle cx="0" cy="14" r="12"/><path d="M-14 32Q0 25 14 32L23 83L14 86L8 56L10 96L9 172H-1L-5 110L-9 172H-19L-18 96L-17 57L-24 85L-32 81L-22 38Z"/></g>`;
    svg.innerHTML = `<defs><linearGradient id="screen-gradient" x1="0" y1="1" x2="1" y2="0"><stop stop-color="#142b36"/><stop offset=".55" stop-color="#125c66"/><stop offset="1" stop-color="#489587"/></linearGradient><clipPath id="screen-clip"><rect x="${sx}" y="${sy}" width="${sww}" height="${shh}"/></clipPath>${texture}</defs>${wall}<path d="M${x - 30} ${y + hh}H${x + ww + 15}" stroke="#849891"/>${screen}<rect x="${sx}" y="${sy}" width="${sww}" height="${shh}" fill="none" stroke="${d.fits ? '#142b36' : '#b94a40'}" stroke-width="2"/>${req && (Math.abs(rw - sw) > 1e-8 || Math.abs(rh - sh) > 1e-8) ? `<rect data-requested-outline x="${x + rl * scale}" y="${y + rt * scale}" width="${rw * scale}" height="${rh * scale}" fill="none" stroke="#bd7621" stroke-width="2" stroke-dasharray="7 5"/>` : ''}${labels}${person}${text(78, y + hh + 25, `${dimensionFormat(display(human))} ${unit} reference`)}${viewing}${text(520, 515, exact ? 'Exact design preview · grid lines show cabinet size from the bottom-left · cabinet option is listed separately' : 'Whole-cabinet layout · mounting structure not included')}`;
}
const sizePresets = { showroom: [16.667, 9.843, 14.698, 7.874], standard: [16, 10, 12, 7], compact: [12, 8, 8, 4.5], large: [24, 14, 20, 11.25] };
function applyPreset() {
    if ($('size_preset').value === 'model') {
        resetScreenDefaults(); const wall = wallDefaults[unit]; $('wall_width').value = dimensionInput(wall.width); $('wall_height').value = heightFormat(wall.height);
    } else {
        const preset = sizePresets[$('size_preset').value] || sizePresets.standard; const factor = unit === 'ft' ? 1 : .3048;
        ['wall_width', 'wall_height', 'screen_width', 'screen_height'].forEach((id, i) => $(id).value = inputFormat(id, preset[i] * factor));
        $('mode').value = 'dimensions'; $('policy').value = 'nearest';
    }
    $('position').value = 'centre'; $('preview_mode').value = 'exact'; $('left').value = 0; $('bottom').value = 0; updateVisibility(); schedule();
}

function liveExactPreview() {
    $('metrics').setAttribute('aria-busy', 'true');
    if (!lastGoodResult || $('preview_mode').value !== 'exact' || $('mode').value !== 'dimensions') return;
    const scale = unit === 'ft' ? .3048 : 1;
    const W = Number($('wall_width').value) * scale, H = Number($('wall_height').value) * scale, w = Number($('screen_width').value) * scale, h = Number($('screen_height').value) * scale;
    if (![W, H, w, h].every(v => Number.isFinite(v) && v > 0)) { $('wall-svg').replaceChildren(); return; }
    const centre = $('position').value === 'centre', left = centre ? (W - w) / 2 : Number($('left').value) * scale, bottom = centre ? (H - h) / 2 : Number($('bottom').value) * scale;
    if (![left, bottom].every(Number.isFinite)) return;
    const margins = { left, right: W - w - left, bottom, top: H - h - bottom }; const fits = Object.values(margins).every(v => v >= 0);
    draw({ ...lastGoodResult, wall_width_m: W, wall_height_m: H, design: { width_m: w, height_m: h, area_m2: w * h, margins_m: margins, fits } });
    $('metrics').innerHTML = `<div class="metric"><span>Exact design size</span><strong>${esc(dimensionFormat($('screen_width').value))} × ${esc(heightFormat($('screen_height').value))}</strong><small>${unit}</small></div><div class="metric"><span>Cabinet option resolution</span><strong>Updating…</strong></div><div class="metric"><span>Cabinet option</span><strong>Updating…</strong></div><div class="metric"><span>Design area</span><strong>${exactArea($('screen_width').value, $('screen_height').value)}</strong><small>${unit === 'ft' ? 'ft²' : 'm²'}</small></div>`;
}
function renderSizeFeedback() {
    const r = result, req = r.requested, box = $('size-feedback');
    box.hidden = !req || req.width_m === undefined; if (box.hidden) return;
    const precision = (unit === 'ft' ? .3048 : 1) * .00005; const different = Math.abs(req.width_m - r.width_m) > precision || Math.abs(req.height_m - r.height_m) > precision;
    $('size-comparison').innerHTML = `<div><span>Exact design dimensions</span><strong>${esc(dimensionFormat($('screen_width').value))} × ${esc(heightFormat($('screen_height').value))} ${unit}</strong></div><div><span>Cabinet option · whole cabinets</span><strong>${dimensionFormat(display(r.width_m))} × ${heightFormat(display(r.height_m))} ${unit}</strong></div>`;
    const difference = (value, axis) => `${axis}: ${(axis === 'Width' ? dimensionFormat : heightFormat)(Math.abs(display(value)))} ${unit} ${value >= 0 ? 'smaller' : 'larger'} than requested`;
    $('size-explanation').textContent = different ? `The main exact-design preview uses your entered dimensions. This cabinet option uses whole cabinets. ${difference(r.size_difference_m.width, 'Width')}; ${difference(r.size_difference_m.height, 'height')}. To meet both requested dimensions, use ${dimensionFormat(display(r.cover_size_m.width))} × ${heightFormat(display(r.cover_size_m.height))} ${unit}.` : 'The requested size and cabinet layout match at the displayed precision.';
    $('snap-size').hidden = !different; $('cover-size').hidden = !different || $('policy').value === 'cover';
}
function specValue(v, suffix = '') { return v === null || v === undefined || v === '' ? 'Not provided' : `${esc(v)}${suffix}`; }
function renderResults() {
    if (!result) return; const r = result, p = product; const totals = r.totals; const sizeNote = r.requested && r.requested.width_m !== undefined ? `<p>Exact design: ${esc(dimensionFormat($('screen_width').value))} × ${esc(heightFormat($('screen_height').value))} ${unit}. Cabinet option: ${dimensionFormat(display(r.width_m))} × ${heightFormat(display(r.height_m))} ${unit}. Cabinet quantities and configured pixel resolution refer to this cabinet option.</p>` : ''; let summary = sizeNote + `<h2>${esc(scene)} · ${esc(environment)} LED wall</h2><p>${dimensionFormat(display(r.width_m))} × ${heightFormat(display(r.height_m))} ${unit} · Video resolution: ${resolutionText(r)} · ${totalPixelsText(r)} · ${r.count} cabinets · ${esc($('installation').value)}</p><p>Cabinet weight: ${specValue(totals.weight_kg, ' kg')} · Typical power: ${specValue(totals.typical_w, ' W')} · Maximum power: ${specValue(totals.maximum_w, ' W')}</p><p class="hint">${r.fits ? 'Fits the entered wall.' : 'SCREEN EXCEEDS THE WALL.'} ${p.demo ? 'Fictional sample product.' : 'User-supplied product data; suitability not independently verified.'} Controller and mounting validation pending.</p>`; $('result-summary').innerHTML = summary; const cloned = $('wall-svg').cloneNode(true); cloned.removeAttribute('id'); for (const id of ['screen-gradient', 'screen-clip', 'finish-pattern', 'room-floor', 'screen-shadow', 'reflection-mask']) cloned.innerHTML = cloned.innerHTML.replaceAll(id, id + '-report'); cloned.style.width = '100%'; $('result-drawing').replaceChildren(cloned);
    const specs = productSpecifications(p);

    const row = (type, model, q, u, s) => `<article class="material-card"><dl class="material-meta"><div><dt>Product type</dt><dd>${esc(type)}</dd></div><div><dt>Model</dt><dd>${esc(model)}</dd></div><div><dt>Quantity</dt><dd>${esc(q)}</dd></div><div><dt>Unit</dt><dd>${esc(u)}</dd></div></dl><h3 class="material-spec-heading">Technical specifications</h3><div class="material-spec-content">${s}</div></article>`;
    $('materials').innerHTML = row('LED display', p.name, r.count, 'PCS', specs) + row('LED wall controller', controllers.find(c => c.id === $('controller').value)?.name || $('controller').value || 'To be selected', $('q_controller_qty').value, 'Nos', esc($('q_controller_description').value || 'Capacity and compatibility to be confirmed.')) + row('Mounting structure', $('installation').value, 'To be confirmed', 'Set', 'Structure and load capacity require installation data.') + row('Power / signal cables', 'Pending design', 'To be confirmed', 'PCS / m', 'Cable routing, distance, ratings and connector limits pending.');
}
function showTab(tab) { $('designer').hidden = tab !== 'designer'; $('results').hidden = tab !== 'results'; document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab)); if (tab === 'results' && result) renderResults(); }
function download(name, data) { const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
function configuredProductSpecifications(p) { return `<strong>${esc(p.brand || '')} ${esc(p.name)}</strong><br>Dimensions (W × H${p.depth_mm != null ? ' × D' : ''}): ${esc(cabinetDimensions(p))}<br>Cabinet pixel setting: ${esc(resolutionText(p))}<br>Pixel source: ${esc(p.pixel_source || 'Provided catalogue')}<br>Pixel pitch: ${specValue(p.pitch_mm, ' mm')}<br>Brightness: ${specValue(p.brightness_nits, ' nits')}<br>Refresh rate: ${specValue(p.refresh_hz, ' Hz')}<br>Maintenance: ${specValue(p.maintenance)}<br>IP rating: ${specValue(p.ip_rating)}<br>Weight per cabinet: ${specValue(p.weight_kg, ' kg')}<br>Typical / max power per cabinet: ${specValue(p.typical_w, ' W')} / ${specValue(p.maximum_w, ' W')}<br>Certification (catalogue listing): ${specValue(p.certification)}<br>Region (catalogue listing): ${specValue(p.region)}<br>Curve range (catalogue listing): ${specValue(p.curve_range_deg)}<br>Source: ${esc(p.source || 'Not provided')}<br><span class="hint">${esc(p.notes || '')}</span>${p.demo ? '<br><strong>FICTIONAL SAMPLE</strong>' : ''}`; }
function orderedSpecificationEntries(values, order = []) {
    const specs = values || {};
    const keys = [...new Set([...order.filter(key => Object.prototype.hasOwnProperty.call(specs, key)), ...Object.keys(specs)])];
    return keys.map(key => [key, specs[key]]);
}
function specificationTable(values, order = []) { return `<table class="spec-table"><thead><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr></thead><tbody>${orderedSpecificationEntries(values, order).map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`; }
function selectedSpecificationSheets(p) {
    const technology = (p.technology || familyFor(p)?.technology || String(p.name || '').match(/COB|SMD/i)?.[0] || '').toUpperCase();
    const sheets = Array.isArray(p.supplied_specifications) ? p.supplied_specifications : [];
    return sheets.filter(sheet => {
        const specs = sheet.specs || {};
        const label = [sheet.technology, sheet.model, specs['LAMP Type'], specs['LED Type'], specs.Technology].filter(Boolean).join(' ');
        const kind = label.match(/COB|SMD/i)?.[0]?.toUpperCase();
        return !technology || !kind || kind === technology;
    });
}
function matchingIndoorCobPixelDensity(p) {
    if (p.environment !== 'indoor' || String(p.technology || '').toUpperCase() !== 'SMD' || p.pitch_mm == null) return null;
    const candidates = catalogue.filter(item => item.environment === 'indoor' && item.technology === 'COB')
        .flatMap(item => [item, ...(item.cabinet_options || [])])
        .map(item => ({
            distance: Math.abs(Number(item.pitch_mm) - Number(p.pitch_mm)),
            sheets: item.supplied_specifications || [],
        }))
        .filter(item => item.distance <= 0.05)
        .sort((a, b) => a.distance - b.distance);
    for (const candidate of candidates) {
        for (const sheet of candidate.sheets) {
            const density = Object.entries(sheet.specs || {}).find(([key]) => /pixel\s+density/i.test(key));
            if (density) return density[1];
        }
    }
    return null;
}
function cabinetOptionSpecifications(sheet, p) {
    const specs = { ...(sheet.specs || {}) };
    const dimensions = cabinetDimensions(p).replace(/ mm$/, '');
    const dimensionEntries = Object.entries(specs).filter(([key]) => /^Cabinet\s+(?:—\s*)?Dimensions?\b/i.test(key));
    const sameCabinet = dimensionEntries.some(([, value]) => String(value).replace(/\s*mm$/i, '').replace(/\s/g, '') === dimensions.replace(/\s/g, ''));
    dimensionEntries.forEach(([key]) => delete specs[key]);
    if (!sameCabinet) {
        ['Cabinet — Modules (W×H)', 'Cabinet — Resolution (W×H)', 'Cabinet — Dimensions (mm)', 'Weight (kg)', 'Pixel density (dot/m²)', 'Peak power consumption (W/m²)', 'Average power consumption (W/m²)', 'Cabinet Input voltage', 'IP protection level'].forEach(key => delete specs[key]);
    }
    const values = {
        'Pixel Pitch (mm)': p.pitch_mm == null ? null : fmt(p.pitch_mm),
        'Cabinet — Resolution (W×H)': p.pixels_w == null || p.pixels_h == null ? null : `${fmt(p.pixels_w)} × ${fmt(p.pixels_h)}`,
        'Cabinet — Dimensions (mm)': dimensions,
        'Maintenance access': p.maintenance,
        'White balance brightness (nit)': p.brightness_nits == null ? null : fmt(p.brightness_nits),
        'Refresh rate (Hz)': p.refresh_hz == null ? null : fmt(p.refresh_hz),
        'Weight (kg)': p.weight_kg == null ? null : fmt(p.weight_kg),
        'IP protection level': p.ip_rating,
    };
    for (const [key, value] of Object.entries(values)) {
        if (value != null) specs[key] = value;
        else if (!sameCabinet) delete specs[key];
    }
    const matchingDensity = matchingIndoorCobPixelDensity(p);
    if (matchingDensity != null) {
        specs['Pixel density (dot/m²)'] = matchingDensity;
    } else if (p.pixels_w != null && p.pixels_h != null && p.width_mm && p.height_mm) {
        specs['Pixel density (dot/m²)'] = fmt(p.pixels_w * p.pixels_h * 1_000_000 / (p.width_mm * p.height_mm));
    }
    return { specs, sameCabinet };
}
function suppliedSpecifications(p) {
    const sheets = selectedSpecificationSheets(p);
    if (!sheets.length) return '';
    const family = familyFor(p); const canonical = (family?.cabinet_options?.find(item => item.id === p.id) || family)?.supplied_specifications || [];
    const tables = sheets.map(sheet => {
        const reference = canonical.find(item => item.model === sheet.model) || {};
        const order = sheet.specification_order || reference.specification_order || [];
        const featureOrder = sheet.feature_specification_order || reference.feature_specification_order || [];
        const selected = cabinetOptionSpecifications(sheet, p);
        return `<article class="spec-sheet"><h4>${esc(sheet.model)}</h4>${specificationTable(selected.specs, order)}${sheet.feature_specs && selected.sameCabinet ? `<h4>Product features — supplied feature page</h4>${specificationTable(sheet.feature_specs, featureOrder)}` : ''}${sheet.note ? `<p class="spec-note">${esc(sheet.note)}</p>` : ''}</article>`;
    }).join('');
    return `<section class="supplied-specs"><h3>Pro Mark cabinet specifications</h3><p class="hint">${p.technology ? 'Technical table for the selected PM variant.' : 'Transcribed PM references; configured original-model values are listed separately below.'}</p>${tables}</section>`;
}
function productSpecifications(p) { return `<p class="selected-cabinet"><strong>Selected cabinet: ${esc(cabinetDimensions(p))}</strong></p>` + suppliedSpecifications(p) + `<details class="configured-specs"><summary>Configured model values used for calculations — ${esc(p.name)}</summary>${configuredProductSpecifications(p)}</details>`; }
function showProductDetails(p) { $('detail-title').textContent = p.name; $('detail-specs').innerHTML = productSpecifications(p); $('detail-dialog').showModal(); }
const modelImage = (p, cls) => p && typeof p.image === 'string' && /^models\/[\w.-]+\.(?:svg|png|jpe?g|webp)$/i.test(p.image) ? `<img class="${cls}" src="/static/${esc(p.image)}" alt="${esc(p.name)} · ${esc(p.image_caption || 'representative illustration')}" loading="lazy">` : '';
function renderCatalogue() {
    $('catalogue-cards').replaceChildren(...catalogue.map(p => {
        const card = document.createElement('div'); card.className = 'catalogue-card';
        const options = p.cabinet_options || [p], selected = familyId(product) === p.id ? product.id : p.default_cabinet_id;
        card.innerHTML = `${modelImage(p, 'model-thumb')}<div class="card-text"><h3>${esc(p.name)}</h3><p>${esc(p.environment)} · P${esc(p.pitch_mm)}</p><p>${specValue(p.brightness_nits, ' nits')} · ${specValue(p.refresh_hz, ' Hz')} · ${specValue(p.maintenance)}</p></div>`;
        const text = card.querySelector('.card-text'), label = document.createElement('label'); label.textContent = 'Cabinet size'; const size = document.createElement('select'); size.setAttribute('aria-label', p.name + ' cabinet size');
        size.replaceChildren(...options.map(option => new Option(cabinetDimensions(option), option.id))); if (selected) size.value = selected; size.disabled = options.length < 2; label.append(size); text.append(label);
        const current = () => resolveCabinet(p, size.value);
        const actions = document.createElement('div'); actions.className = 'model-actions';
        const details = document.createElement('button'); details.textContent = 'See specifications'; details.onclick = () => showProductDetails(current());
        const choose = document.createElement('button'); choose.className = 'primary'; choose.textContent = 'Choose model'; choose.onclick = () => { $('technology').value = p.technology || 'all'; product = current(); resetScreenDefaults(); selectEnvironment(p.environment, true); $('catalogue-dialog').close(); };
        actions.append(details, choose); card.append(actions); return card;
    }));
}

function restore(data) {
    const mountType = data.q_mount_type ?? data.quotation?.mount_type ?? 'none';
    const mountOption = MOUNTING_OPTIONS[mountType];
    data = { ...data, q_mount_type: mountOption ? mountType : 'none',
        q_mount_rate: mountOption ? (data.q_mount_rate ?? data.quotation?.mount_rate ?? mountOption.rate) : '',
        q_mount_description: mountOption ? (data.q_mount_description ?? data.quotation?.mount_description ?? mountOption.description) : '' };
    $('controller-auto').checked = data.auto_controller === true; if (['pm-1-5-smd', 'umate-sf4', 'pm-2-5-smd'].includes(data.product?.id)) { data = { ...data, product: catalogue.find(p => p.environment === (data.environment || 'indoor')), technology: 'all' }; message('This saved model has been removed. Review the replacement model before continuing.'); } $('controller').value = data.controller || ''; fields.forEach(id => { if (data[id] !== undefined) $(id).value = data[id]; }); const restoredController = controllers.find(c => c.id === $('controller').value); if (restoredController) { $('q_controller_description').value = controllerDescription(restoredController, $('q_controller_description').value); } else { $('controller-auto').checked = true; $('q_controller_description').value = ''; } unit = data.unit || 'ft'; $('dimension_step').value = data.dimension_step || 'unit'; $('preview_mode').value = data.preview_mode || 'exact'; environment = data.environment || 'indoor'; if (data.product) { product = { ...data.product }; const current = familyFor(product); if (current) { product = resolveCabinet(current, product.cabinet_option_id || product.id); } else { catalogue.push(product); } } wallPhoto = ''; screenPhoto = ''; document.querySelectorAll('.unit').forEach(el => el.textContent = unit); document.querySelectorAll('#units button').forEach(b => b.classList.toggle('active', b.dataset.value === unit)); $('resolution').value = 'custom'; $('human_height').max = unit === 'ft' ? 10 : 3; formatDimensionInputs(); selectScene(data.scene || 'Conference'); selectEnvironment(environment, true); updateVisibility(); updateFullPrices(); showTab('designer'); }
async function initialise() {
    controllers = await api('/api/controllers');
    for (const c of controllers) { const option = document.createElement('option'); option.value = c.id; option.textContent = c.name + (c.kind === 'LED Wall Controller' ? '' : ' · ' + c.kind); $('controller').append(option); }
    catalogue = await api('/api/catalogue'); formatDimensionInputs(); $('technology').value = 'COB'; product = resolveCabinet(catalogue.find(p => p.id === 'pm-1-2-cob') || catalogue[0]); selectEnvironment('indoor', true); $('size_preset').value = product.width_mm === 600 && product.height_mm === 337.5 ? 'model' : 'showroom'; applyPreset();
}
fields.forEach(id => $(id).addEventListener('input', () => { updateVisibility(); schedule(); }));
$('environment').onchange = () => selectEnvironment($('environment').value); document.querySelectorAll('#units button').forEach(b => b.onclick = () => changeUnits(b.dataset.value)); document.querySelectorAll('nav button[data-tab]').forEach(b => b.onclick = () => showTab(b.dataset.tab)); document.querySelectorAll('[data-close]').forEach(b => b.onclick = () => $(b.dataset.close).close());
$('product').onchange = () => { product = resolveCabinet(catalogue.find(p => p.id === $('product').value)); resetScreenDefaults(); renderProducts(); schedule(); }; $('resolution').onchange = () => { if ($('resolution').value !== 'custom') { const [w, h] = $('resolution').value.split(','); $('target_pixels_w').value = w; $('target_pixels_h').value = h; } updateVisibility(); schedule(); }; $('show-grid').onchange = () => { draw(); if (result) renderResults(); }; $('results-btn').onclick = () => { showTab('results'); window.scrollTo({ top: 0, behavior: 'smooth' }); }; $('print-btn').onclick = () => { if (!result) { message('Enter a valid design before printing.', true); return; } showTab('results'); renderResults(); window.print(); }; $('export-json').onclick = () => { if (!result) return message('Correct the design before exporting.', true); download('PROMARK-LED-STUDIO-Design.json', { ...state(), calculated: result }); }; $('catalogue-btn').onclick = () => $('catalogue-dialog').showModal(); $('product-details').onclick = () => { if (product) showProductDetails(product); }; $('download-catalogue').onclick = () => download('catalogue-template.json', catalogue);
for (const [id, kind] of [['wall-photo', 'wall'], ['screen-photo', 'screen']]) $(id).onchange = () => { const f = $(id).files[0]; if (!f) return; if (!['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > 5 * 1024 * 1024) return message('Use a PNG, JPEG or WebP image smaller than 5 MB.', true); const reader = new FileReader(); reader.onload = () => { if (kind === 'wall') wallPhoto = reader.result; else { screenPhoto = reader.result; $('content').value = 'image'; } draw(); if (result) renderResults(); }; reader.readAsDataURL(f); }; $('clear-photo').onclick = () => { wallPhoto = ''; $('wall-photo').value = ''; draw(); if (result) renderResults(); }; $('zoom-in').onclick = () => { zoom = Math.min(2.5, zoom + .25); draw(); }; $('zoom-out').onclick = () => { zoom = Math.max(.5, zoom - .25); draw(); }; $('zoom-reset').onclick = () => { zoom = 1; draw(); };
$('save-btn').onclick = async () => { if (!result) return message('Correct the design before saving.', true); const name = prompt('Project name', `${scene} LED wall`); if (name === null) return; try { await api('/api/projects', { ...state(), name }); message(`Saved “${name || 'Untitled project'}”. Preview photos are not stored.`); } catch (e) { message(e.message, true); } };
$('projects-btn').onclick = async () => { try { const data = await api('/api/projects'); const records = data.projects || data; $('project-list').replaceChildren(...records.map(rec => { const btn = document.createElement('button'); btn.className = 'project-item'; const label = document.createElement('strong'); label.textContent = rec.name; const date = document.createElement('small'); date.textContent = rec.created_at || rec.created; btn.append(label, date); btn.onclick = async () => { try { restore(await api(`/api/projects/${rec.id || rec._id}`)); $('projects-dialog').close(); message('Project loaded. Re-upload any preview photos.'); } catch (e) { message(e.message, true); } }; return btn; })); if (!records.length) $('project-list').textContent = 'No saved projects yet.'; $('projects-dialog').showModal(); } catch (e) { message(e.message, true); } };
$('import-catalogue').onchange = async () => { const f = $('import-catalogue').files[0]; if (!f) return; try { if (f.size > 1024 * 1024) throw Error('Catalogue must be smaller than 1 MB'); const incoming = JSON.parse(await f.text()); if (!Array.isArray(incoming) || !incoming.length || incoming.length > 200) throw Error('Catalogue must contain 1–200 product objects'); const ids = new Set(); for (const p of incoming) { if (!p || typeof p !== 'object' || typeof p.id !== 'string' || typeof p.name !== 'string' || !['indoor', 'outdoor'].includes(p.environment) || ids.has(p.id)) throw Error('Each product needs a unique string id, name and indoor/outdoor environment'); ids.add(p.id); await api('/api/calculate', { ...state(), product: p, mode: 'grid', columns: 1, rows: 1 }); } catalogue = incoming; product = null; selectEnvironment(incoming[0].environment); message('Catalogue imported for this session. Save a project to preserve its selected product.'); } catch (e) { message(`Import failed: ${e.message}`, true); } };
$('snap-size').onclick = () => { if (!result) return; const r = result; $('screen_width').value = dimensionInput(display(r.width_m)); $('screen_height').value = heightFormat(display(r.height_m)); $('columns').value = r.columns; $('rows').value = r.rows; $('mode').value = 'grid'; updateVisibility(); schedule(); }; $('cover-size').onclick = () => { $('policy').value = 'cover'; schedule(); };
$('reset-dimensions').onclick = applyPreset;
initialise().catch(e => message(e.message, true));

function dimensionStep(id) {
    if ($('dimension_step').value === 'cabinet' && id.startsWith('screen_') && product) {
        return modelDefaults()[id.endsWith('width') ? 'width_step' : 'height_step'];
    }
    return 1;
}
function updateDimensionSteps() {
    $('dimension_step').querySelector('option[value="unit"]').textContent = `1 ${unit} per click`;
    $('step-hint').textContent = $('dimension_step').value === 'cabinet' && product
        ? `Screen step: ${dimensionFormat(dimensionStep('screen_width'))} ${unit} wide / ${heightFormat(dimensionStep('screen_height'))} ${unit} high. Wall step: 1 ${unit}. Type any exact dimension.`
        : `Buttons change dimensions by 1 ${unit}. Type any exact dimension.`;
    document.querySelectorAll('[data-step-target]').forEach(button => {
        const input = $(button.dataset.stepTarget), id = button.dataset.stepTarget, min = id.startsWith('screen_') ? modelDefaults()[id.endsWith('width') ? 'width' : 'height'] : Number(input.min); button.disabled = Number(button.dataset.direction) < 0 && Number(input.value) - dimensionStep(id) < min - 1e-3; button.title = `${Number(button.dataset.direction) > 0 ? 'Increase' : 'Decrease'} by ${inputFormat(button.dataset.stepTarget, dimensionStep(button.dataset.stepTarget))} ${unit}`;
    });
}
function stepDimension(id, direction) {
    const input = $(id), current = Number(input.value);
    if (input.value.trim() === '' || !Number.isFinite(current)) return;
    let next = exactDecimalStep(input.value, dimensionStep(id), direction);
    // Cabinet stepping: land on exact whole-cabinet multiples so rounded values never drift.
    if ($('dimension_step').value === 'cabinet' && id.startsWith('screen_') && product) { const cab = Number(dimensionStep(id)), n = Math.round(current / cab); if (cab > 0 && n >= 1 && Math.abs(current - n * cab) <= Math.max(1e-3, cab * 1e-3)) next = String(+((n + direction) * cab).toFixed(9)); }
    const min = id.startsWith('screen_') ? modelDefaults()[id.endsWith('width') ? 'width' : 'height'] : Number(input.min); if (Number(next) < min - 1e-3) return;
    input.value = inputFormat(id, next);
    input.dispatchEvent(new Event('input', { bubbles: true }));
}
document.querySelectorAll('[data-step-target]').forEach(button => button.onclick = () => stepDimension(button.dataset.stepTarget, Number(button.dataset.direction)));
['wall_width', 'wall_height', 'screen_width', 'screen_height'].forEach(id => $(id).addEventListener('keydown', event => {
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault(); stepDimension(id, event.key === 'ArrowUp' ? 1 : -1);
    }
}));


['wall_width', 'wall_height', 'screen_width', 'screen_height', 'left', 'bottom', 'human_height'].forEach(id => $(id).addEventListener('blur', () => {
    const input = $(id); if (input.value.trim() === '' || !Number.isFinite(Number(input.value))) return;
    const formatted = inputFormat(id, input.value);
    if (formatted !== input.value) { input.value = formatted; updateVisibility(); schedule(); }
}));

function updatePixelControls(r) {
    const known = product && product.pixels_w != null && product.pixels_h != null;
    $('screen_pixels_w').value = known && r ? r.pixels_w : ''; $('screen_pixels_h').value = known && r ? r.pixels_h : '';
    $('pixel-hint').textContent = known ? `Width step: ±${product.pixels_w} px · Height step: ±${product.pixels_h} px. Each click adds or removes one cabinet.` : 'Cabinet pixel counts are not provided for this model.';
    document.querySelectorAll('[data-pixel-axis]').forEach(button => {
        const axis = button.dataset.pixelAxis, count = r ? (axis === 'width' ? r.columns : r.rows) : 0;
        button.disabled = !known || !r || (Number(button.dataset.direction) < 0 && count <= 1);
        button.title = `${Number(button.dataset.direction) > 0 ? 'Increase' : 'Decrease'} by ${known ? (axis === 'width' ? product.pixels_w : product.pixels_h) : 'unknown'} px`;
    });
}
function stepPixels(axis, direction) {
    if (!result || !product) return;
    const r = result, col = r.columns + (axis === 'width' ? direction : 0), row = r.rows + (axis === 'height' ? direction : 0);
    if (col < 1 || row < 1 || col > 2000 || row > 2000 || col * row > 100000) return;
    const defaults = modelDefaults();
    $('columns').value = col; $('rows').value = row;
    $('screen_width').value = dimensionInput(String(+(col * defaults.width_step).toFixed(9)));
    $('screen_height').value = heightFormat(String(+(row * defaults.height_step).toFixed(9)));
    // Keep physical dimensions visible and choose the corresponding cabinet count.
    $('mode').value = 'dimensions'; $('policy').value = 'nearest'; $('dimension_step').value = 'cabinet'; updateVisibility(); schedule();
}
document.querySelectorAll('[data-pixel-axis]').forEach(button => button.onclick = () => stepPixels(button.dataset.pixelAxis, Number(button.dataset.direction)));

$('show-spaces').onchange = () => draw();

// Technology and editable Excel quotation controls.
document.querySelectorAll('#technology-buttons button').forEach(button => button.onclick = () => { $('technology').value = button.dataset.value; selectEnvironment(environment); });
$('q_date').value = new Date().toLocaleDateString('en-CA');
const requiredQuotationDetails = [['q_client', 'Client name'], ['q_salesperson', 'Sales person'], ['q_contact', 'Contact information']];
for (const [id] of requiredQuotationDetails) $(id).addEventListener('input', () => { $(id).setCustomValidity(''); $(id).removeAttribute('aria-invalid'); });
function validateQuotationDetails() {
    const missing = requiredQuotationDetails.filter(([id]) => !$(id).value.trim());
    for (const [id, label] of requiredQuotationDetails) {
        const empty = !$(id).value.trim();
        $(id).setCustomValidity(empty ? `Enter ${label.toLowerCase()} before downloading the quotation.` : '');
        if (empty) $(id).setAttribute('aria-invalid', 'true'); else { $(id).removeAttribute('aria-invalid'); $(id).value = $(id).value.trim(); }
    }
    if (!missing.length) return true;
    showTab('results');
    message(`Enter ${missing.map(([, label]) => label.toLowerCase()).join(', ')} before downloading the quotation.`, true);
    const first = $(missing[0][0]); first.scrollIntoView({ block: 'center' }); first.focus(); first.reportValidity();
    return false;
}
async function downloadQuotation(format = 'xlsx') {
    if (!validateQuotationDetails()) return;
    const button = $(format === 'pdf' ? 'download-quotation-pdf' : 'download-quotation');
    if (!product) return message('Select a cabinet model first.', true);
    if (!button) return;
    button.disabled = true;
    button.textContent = format === 'pdf' ? 'Preparing PDF…' : 'Preparing Excel…';

    try {
        const payload = state();
        let token = localStorage.getItem('access_token');
        const makeHeaders = () => {
            const headers = { 'Content-Type': 'application/json' };
            headers['Authorization'] = `Bearer ${token}`;
            return headers;
        };

        let response = await fetch(`/api/quotation?format=${format}`, {
            method: 'POST', headers: makeHeaders(), body: JSON.stringify(payload), credentials: 'include'
        });

        if (response.status === 401 && window.AUTH?.refreshToken) {
            const refreshed = await window.AUTH.refreshToken();
            if (refreshed) {
                token = localStorage.getItem('access_token');
                response = await fetch(`/api/quotation?format=${format}`, {
                    method: 'POST', headers: makeHeaders(), body: JSON.stringify(payload), credentials: 'include'
                });
            }
        }

        if (!response.ok) {
            let errorText = 'Quotation could not be created';
            const contentType = response.headers.get('Content-Type') || '';
            if (contentType.includes('application/json')) {
                const error = await response.json();
                errorText = error.error || errorText;
            }
            throw Error(errorText);
        }

        const blob = await response.blob();
        if (!blob.size) throw Error('The server returned an empty quotation file.');

        const disposition = response.headers.get('Content-Disposition') || '';
        const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
        const normalName = disposition.match(/filename="([^"]+)"/i)?.[1];
        let downloadName = utf8Name ? decodeURIComponent(utf8Name) : normalName;
        if (!downloadName) {
            const cleanSalesperson = $('q_salesperson').value.trim().replace(/[\\/:*?"<>|]+/g, '-');
            let widthValue, heightValue;
            if ($('mode').value === 'dimensions') {
                widthValue = Number($('screen_width').value);
                heightValue = Number($('screen_height').value);
            } else if (result) {
                const design = $('preview_mode').value === 'exact' ? result.design : result;
                const widthMeters = Number(design?.width_m ?? result.width_m ?? 0);
                const heightMeters = Number(design?.height_m ?? result.height_m ?? 0);
                widthValue = unit === 'ft' ? widthMeters / 0.3048 : widthMeters;
                heightValue = unit === 'ft' ? heightMeters / 0.3048 : heightMeters;
            }
            const pitch = product?.pitch_mm != null ? `${Number(product.pitch_mm)}mm` : 'LED';
            const technology = String(product?.technology || 'SMD').toUpperCase();
            const environment = String(product?.environment || 'indoor');
            if (!widthValue && result?.width_m != null) widthValue = unit === 'ft' ? Number(result.width_m) / 0.3048 : Number(result.width_m);
            if (!heightValue && result?.height_m != null) heightValue = unit === 'ft' ? Number(result.height_m) / 0.3048 : Number(result.height_m);
            const formatSize = value => Number.isFinite(Number(value)) ? Number(value).toFixed(3) : '0.000';
            const sizeText = `${formatSize(widthValue)}W x ${formatSize(heightValue)}H ${unit}`;
            const date = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date()).replaceAll('/', '-');
            downloadName = `Quotation of ${pitch} ${technology} ${environment.charAt(0).toUpperCase() + environment.slice(1)} (${sizeText}) ${date} (${cleanSalesperson}).${format}`;
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = downloadName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        message(`Quotation downloaded: ${downloadName}`);
    } catch (error) {
        message(error.message, true);
    } finally {
        button.disabled = false;
        button.textContent = format === 'pdf' ? 'Download PDF quotation' : 'Download Excel quotation';
    }
}

$('download-quotation').onclick = () => downloadQuotation('xlsx');
$('download-quotation-pdf').onclick = () => downloadQuotation('pdf');
$('convert-edited-pdf').onclick = async () => {
    const file = $('edited-quotation-file').files?.[0];
    if (!file) return message('Select the edited Excel quotation first.', true);
    const button = $('convert-edited-pdf');
    button.disabled = true;
    button.textContent = 'Converting…';
    try {
        const form = new FormData();
        form.append('quotation', file);
        const token = localStorage.getItem('access_token');
        const headers = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        let response = await fetch('/api/quotation/from-excel', { method: 'POST', headers, body: form, credentials: 'include' });
        if (response.status === 401 && window.AUTH?.refreshToken) {
            const refreshed = await window.AUTH.refreshToken();
            if (refreshed) {
                headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`;
                response = await fetch('/api/quotation/from-excel', { method: 'POST', headers, body: form, credentials: 'include' });
            }
        }
        if (!response.ok) {
            const contentType = response.headers.get('Content-Type') || '';
            if (contentType.includes('application/json')) throw Error((await response.json()).error || 'PDF conversion failed');
            throw Error('PDF conversion failed');
        }
        const blob = await response.blob();
        if (!blob.size) throw Error('The converted PDF is empty.');
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename="([^"]+)"/i);
        const downloadName = match?.[1] || file.name.replace(/\.xlsx$/i, '-edited.pdf');
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url; link.download = downloadName; link.style.display = 'none';
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        message(`Edited PDF downloaded: ${downloadName}`);
    } catch (error) {
        message(error.message, true);
    } finally {
        button.disabled = false;
        button.textContent = 'Convert edited Excel to PDF';
    }
};

function selectedArea() {
    const exact = $('preview_mode').value === 'exact', d = exact ? result.design : result;
    const w = exact && $('mode').value === 'dimensions' ? $('screen_width').value : dimensionFormat(display(d.width_m));
    const h = exact && $('mode').value === 'dimensions' ? $('screen_height').value : heightFormat(display(d.height_m));
    return exactArea(w, h);
}
function quotationAreaSqft() { const area = Number(selectedArea()); return unit === 'ft' ? area : area / 0.09290304; }
function selectedMounting() {
    const type = $('q_mount_type').value, option = MOUNTING_OPTIONS[type];
    if (!option) return null;
    const raw = $('q_mount_rate').value;
    const rate = raw === '' ? option.rate : Number(raw);
    const quantity = type === 'structure' ? (result ? quotationAreaSqft() : null) : 1;
    const price = Number.isFinite(rate) && rate >= 0 && quantity !== null ? Math.round((rate * quantity + Number.EPSILON) * 100) / 100 : null;
    return { ...option, type, rate, price };
}
function updateMountingSelection(reset = false) {
    const type = $('q_mount_type').value, option = MOUNTING_OPTIONS[type];
    for (const id of ['q_mount_rate_field', 'q_mount_total_field', 'q_mount_description_field']) $(id).hidden = !option;
    $('q_mount_rate').disabled = !option;
    $('q_mount_description').disabled = !option;
    if (reset) {
        $('q_mount_rate').value = option ? option.rate : '';
        $('q_mount_description').value = option ? option.description : '';
    }
    $('q_mount_rate_label').textContent = type === 'structure' ? 'Structure rate · INR / sq.ft.' : 'Uni-pole unit price · INR';
    const mount = selectedMounting();
    $('q_structure_total').value = !mount ? '' : mount.price === null ? 'Enter a valid rate and screen size' : money(mount.price);
}
function updateFullPrices() {
    const area = result ? quotationAreaSqft() : null;
    $('q_install_total').value = 'Company actual price';
    $('q_mount_qty').value = area === null ? '' : String(area);
    updateMountingSelection();
    const controller = controllers.find(c => c.id === $('controller').value);
    const quantity = Number($('q_controller_qty').value || 1);
    const gst = Number($('q_gst').value || 0) / 100;
    if (controller?.rate_inr != null && Number.isFinite(quantity) && quantity >= 0) {
        const beforeGst = controller.rate_inr * quantity;
        const controllerGst = beforeGst * gst;
        $('q_controller_gst').value = money(controllerGst);
        $('q_controller_total').value = money(beforeGst + controllerGst);
    } else {
        $('q_controller_gst').value = controller ? 'Rate unavailable' : 'Select a controller';
        $('q_controller_total').value = controller ? 'Rate unavailable' : 'Select a controller';
    }
    if (result) {
        for (const [input, output, factor] of [['q_wall_rate', 'q_led_total', 1]]) {
            const raw = $(input).value; $(output).value = raw === '' ? 'Rate required' : (Number(raw) * factor * area).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }
}
for (const id of ['q_wall_rate', 'q_installation_rate', 'q_mount_rate', 'q_mount_qty', 'q_controller_qty', 'q_gst']) $(id).addEventListener('input', () => updateFullPrices());
$('q_mount_type').addEventListener('change', () => { updateMountingSelection(true); updateFullPrices(); });

// Use model-specific paragraph wording; switching models clears the previous price.
function applyControllerSelection() {
    const c = controllers.find(c => c.id === $('controller').value);
    $('q_controller_description').value = 'Supply of LED wall controller. Capacity and compatibility to be confirmed.';
    $('q_controller_gst').value = c?.rate_inr != null ? money(c.rate_inr * Number($('q_controller_qty').value || 1) * (Number($('q_gst').value || 0) / 100)) : c ? 'Rate unavailable' : 'Select a controller';
    $('q_controller_total').value = c?.rate_inr != null ? money(c.rate_inr * Number($('q_controller_qty').value || 1) * (1 + Number($('q_gst').value || 0) / 100)) : c ? 'Rate unavailable' : 'Select a controller';
    $('controller-source').textContent = c ? `Source: ${c.source} · RMB ${Number(c.rmb_rate).toLocaleString('en-IN')} · Final rate: ${money(c.rate_inr)} each before GST.` : 'Controller pricing is unavailable until a controller is selected.';
}
$('controller').addEventListener('change', () => { $('controller-auto').checked = false; applyControllerSelection(); updateControllerRecommendation(); updateFullPrices(); schedule(); });
$('controller-auto').onchange = () => { updateControllerRecommendation(); updateFullPrices(); if (result) renderResults(); };

// Preview buttons share the dimension controls and their selected step.
function stepPreviewDimension(axis, direction) {
    if (!product) return;
    if ($('mode').value !== 'dimensions') {
        const current = result || lastGoodResult; if (!current) return;
        $('screen_width').value = dimensionInput(display(current.width_m));
        $('screen_height').value = heightFormat(display(current.height_m));
        $('mode').value = 'dimensions'; updateVisibility();
    }
    stepDimension('screen_' + axis, direction);
}
document.querySelectorAll('[data-preview-axis]').forEach(button => button.onclick = () => stepPreviewDimension(button.dataset.previewAxis, Number(button.dataset.direction)));

$('cabinet_size').onchange = () => { const family = familyFor(product); product = resolveCabinet(family, $('cabinet_size').value); resetScreenDefaults(); renderProducts(); updateVisibility(); schedule(); };
