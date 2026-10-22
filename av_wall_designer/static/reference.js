'use strict';
// Keep the original geometry engine, quotation state and saved projects.
const referenceOriginalRender = render;
render = function () { referenceOriginalRender(); updateReferencePanels(); };
const referenceOriginalProducts = renderProducts;
renderProducts = function () { referenceOriginalProducts(); if (product?.width_mm === 600 && product?.height_mm === 337.5) { $('product-image').src = '/static/showroom-cabinet.png'; $('product-image').alt = product.name + ' · representative cabinet illustration'; $('product-figure').title = 'Representative cabinet illustration. Supplied model photos remain in the catalogue and Excel quotation.'; } syncReferenceControls(); };
const referenceOriginalUnits = changeUnits;
changeUnits = function (next) { referenceOriginalUnits(next); syncReferenceControls(); };
const referenceOriginalRestore = restore;
restore = function (data) { referenceOriginalRestore(data); resetRoomPosition(); syncReferenceControls(); };
const referenceOriginalDraw = draw;
const roomPhotoPosition = { x: 0, y: 0, scale: 1 };
draw = function (r = result) {
    if (!r) return;
    const exact = $('preview_mode').value === 'exact', d = exact ? r.design : r;
    const W = r.wall_width_m, H = r.wall_height_m, sw = d.width_m, sh = d.height_m;
    const scale = Math.min(880 / W, 500 / H), ww = W * scale, hh = H * scale, x = (1030 - ww) / 2, y = 534 - hh;
    const sx = x + d.margins_m.left * scale, sy = y + d.margins_m.top * scale, sww = sw * scale, shh = sh * scale;
    const svg = $('wall-svg'); svg.setAttribute('viewBox', '0 0 1030 720'); svg.style.width = `${zoom * 100}%`;
    $('zoom-value').textContent = `${Math.round(zoom * 100)}%`;
    const requested = $('mode').value === 'dimensions';
    const width = exact && requested ? dimensionFormat($('screen_width').value) : dimensionFormat(display(sw));
    const height = exact && requested ? heightFormat($('screen_height').value) : heightFormat(display(sh));
    $('preview-width-label').textContent = width + ' ' + unit; $('preview-height-label').textContent = height + ' ' + unit;
    const finish = $('finish').value, colour = $('wall_colour').value;
    const lightWall = ['white', 'plain'].includes(finish);
    const wallInk = lightWall ? '#000' : '#fff';
    const img = (url, a, b, c, e, aspect = 'xMidYMid slice') => `<image href="${esc(url)}" x="${a}" y="${b}" width="${c}" height="${e}" preserveAspectRatio="${aspect}"/>`;
    const roomWidth = 1030 * roomPhotoPosition.scale, roomHeight = 720 * roomPhotoPosition.scale;
    const roomX = (1030 - roomWidth) / 2 + roomPhotoPosition.x, roomY = (720 - roomHeight) / 2 + roomPhotoPosition.y;
    let wall = `<rect width="1030" height="720" fill="#17232c"/>`;
    wall += `<g data-room-background><image href="${esc(wallPhoto || '/static/showroom-room.png')}" x="${roomX}" y="${roomY}" width="${roomWidth}" height="${roomHeight}" preserveAspectRatio="${wallPhoto ? 'xMidYMid slice' : 'none'}"/></g>`;
    if (finish === 'white' || finish === 'plain') wall += `<rect x="0" y="0" width="1030" height="534" fill="${finish === 'white' ? '#f0f1f3' : esc(colour)}"/>`;
    if (finish === 'wood' || finish === 'dark' || finish === 'brick') wall += `<rect x="0" y="0" width="1030" height="534" fill="url(#finish-pattern)"/>`;
    const patterns = {
        wood: '<pattern id="finish-pattern" width="40" height="200" patternUnits="userSpaceOnUse"><rect width="40" height="200" fill="#8d6c4b"/><path d="M0 0V200M39 0V200" stroke="#4b3624" stroke-width="2"/><path d="M7 0Q20 50 8 100T12 200M27 0Q18 80 29 140T22 200" stroke="#b4916b" fill="none" stroke-opacity=".45"/></pattern>',
        dark: '<pattern id="finish-pattern" width="20" height="100" patternUnits="userSpaceOnUse"><rect width="20" height="100" fill="#18222b"/><path d="M0 0V100M3 0V100" stroke="#091017" stroke-width="3"/><path d="M18 0V100" stroke="#3a4752"/></pattern>',
        brick: '<pattern id="finish-pattern" width="70" height="40" patternUnits="userSpaceOnUse"><rect width="70" height="40" fill="#8d7363"/><path d="M0 0H70M0 20H70M0 40H70M0 0V20M35 20V40M70 0V20" stroke="#c3b3a5" stroke-width="2" fill="none"/></pattern>'
    };
    let screen = `<rect x="${sx}" y="${sy}" width="${sww}" height="${shh}" fill="#07101a"/>`;
    if ($('content').value === 'sample') screen += img('/static/showroom-sunset.png', sx, sy, sww, shh);
    else if ($('content').value === 'image' && screenPhoto) screen += img(screenPhoto, sx, sy, sww, shh);
    else if ($('content').value === 'gradient') screen += `<rect x="${sx}" y="${sy}" width="${sww}" height="${shh}" fill="url(#screen-gradient)"/><text x="${sx + sww * .08}" y="${sy + shh * .55}" fill="#fff" font-size="${Math.min(40, shh * .12)}">Your vision. At any scale.</text>`;
    if ($('show-grid').checked) {
        // Fit the calculated cabinet count evenly to the exact-size illustration.
        // Physical whole-cabinet dimensions remain in the buildable layout notes.
        const cw = sww / r.columns, ch = shh / r.rows;
        let path = '';
        if (r.columns <= 200) for (let n = 1; n < r.columns; n++)path += `M${sx + n * cw} ${sy}V${sy + shh}`;
        if (r.rows <= 200) for (let n = 1; n < r.rows; n++)path += `M${sx} ${sy + n * ch}H${sx + sww}`;
        screen += `<path data-grid data-columns="${r.columns}" data-rows="${r.rows}" d="${path}" stroke="#08131d" stroke-opacity=".85" stroke-width="1.2" fill="none"/>`;
    }
    const line = (a, b, c, e, extra = '') => `<path d="M${a} ${b}L${c} ${e}" stroke="${wallInk}" stroke-width="1.3" ${extra}/>`;
    const text = (a, b, value, anchor = 'middle', inside = false) => `<text class="${inside ? 'dimension-inside' : 'dimension-outside'}" x="${a}" y="${b}" text-anchor="${anchor}" style="fill:${inside ? wallInk : '#fff'};stroke:none" font-size="12" font-family="Segoe UI, sans-serif">${esc(value)}</text>`;
    const topGuide = Math.max(58, sy - 24), rightGuide = Math.min(956, sx + sww + 24);
    let guides = line(sx, topGuide, sx + sww, topGuide) + line(sx, topGuide - 6, sx, topGuide + 6) + line(sx + sww, topGuide - 6, sx + sww, topGuide + 6) + line(rightGuide, sy, rightGuide, sy + shh) + line(rightGuide - 6, sy, rightGuide + 6, sy) + line(rightGuide - 6, sy + shh, rightGuide + 6, sy + shh);
    if ($('show-spaces').checked) {
        const dot = (a, b, c, e) => line(a, b, c, e, 'stroke-dasharray="2 5" stroke-linecap="round"');
        const fd = n => dimensionFormat(display(n)) + ' ' + unit;
        const gap = Math.min(36, shh * .12), midY = sy + gap;
        if (d.margins_m.left > .001) { guides += dot(x, midY, sx, midY); if (sx - x > 36) guides += text((x + sx) / 2, midY - 6, fd(d.margins_m.left), 'middle', true); }
        if (d.margins_m.right > .001) { guides += dot(sx + sww, midY, x + ww, midY); if (x + ww - sx - sww > 36) guides += text((sx + sww + x + ww) / 2, midY - 6, fd(d.margins_m.right), 'middle', true); }
        if (d.margins_m.top > .001) { guides += dot(sx + sww * .25, y, sx + sww * .25, sy); if (sy - y > 28) guides += text(sx + sww * .25 + 6, (y + sy) / 2, fd(d.margins_m.top), 'start', true); }
        if (d.margins_m.bottom > .001) { guides += dot(sx + sww * .75, sy + shh, sx + sww * .75, 534); if (534 - sy - shh > 28) guides += text(sx + sww * .75 + 6, (sy + shh + 534) / 2, fd(d.margins_m.bottom), 'start', true); }
    }
    svg.innerHTML = `<defs><linearGradient id="screen-gradient"><stop stop-color="#153546"/><stop offset="1" stop-color="#148496"/></linearGradient><clipPath id="screen-clip"><rect x="${sx}" y="${sy}" width="${sww}" height="${shh}"/></clipPath><filter id="screen-shadow" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#000" flood-opacity=".8"/></filter>${patterns[finish] || ''}</defs>${wall}<g filter="url(#screen-shadow)">${screen}<rect x="${sx}" y="${sy}" width="${sww}" height="${shh}" fill="none" stroke="#020811" stroke-width="3"/></g>${guides}${text(24, 694, `Wall ${dimensionFormat(display(W))} × ${heightFormat(display(H))} ${unit}`, 'start')}`;
    updatePreviewButtons();
};
function updatePreviewButtons() {
    document.querySelectorAll('[data-preview-axis]').forEach(b => {
        const axis = b.dataset.previewAxis, id = 'screen_' + axis;
        b.disabled = !product || (Number(b.dataset.direction) < 0 && Number($(id).value) - dimensionStep(id) < modelDefaults()[axis] - 1e-3);
        b.title = `${Number(b.dataset.direction) > 0 ? 'Increase' : 'Decrease'} ${axis} by ${inputFormat(id, dimensionStep(id))} ${unit}`;
    });
}
function updateReferencePanels() {
    syncReferenceControls();
    const c = controllers.find(c => c.id === $('controller').value);
    $('controller-model-name').textContent = c?.name || 'Select a controller'; $('controller-kind').textContent = c?.kind || 'LED video wall equipment';
    let specs = [];
    if (c?.specifications) {
        const labels = { 'Loading capacity': 'Capacity', 'Maximum width': 'Max width', 'Inputs': 'Input', 'Outputs': 'Output', 'Communication': 'Control', 'Features': 'Features' };
        specs = ['Inputs', 'Outputs', 'Loading capacity', 'Maximum width', 'Communication', 'Features'].filter(key => c.specifications[key]).map(key => [labels[key] || key, c.specifications[key]]);
    } else if (c) {
        specs = [['Capacity', c.max_pixels != null ? Number(c.max_pixels).toLocaleString('en-IN') + ' pixels' : 'Not provided'], ['Max width', c.max_width != null ? Number(c.max_width).toLocaleString('en-IN') + ' pixels' : 'Not provided'], ['Max height', c.max_height != null ? Number(c.max_height).toLocaleString('en-IN') + ' pixels' : 'Not provided'], ['Output', c.ethernet_outputs != null ? c.ethernet_outputs + ' Ethernet ports' : 'Not provided']];
    }
    $('controller-specs').innerHTML = specs.map(([k, v]) => `<div class="${k === 'Features' ? 'spec-features' : ''}"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
    for (const opt of $('controller').options) { const item = controllers.find(c => c.id === opt.value); if (item) opt.textContent = item.name; }
    const compactName = p => (p?.name || 'Select cabinet').split(' · ')[0];
    $('studio-summary-items').innerHTML = `<div class="summary-item"><div class="summary-thumb">${product?.width_mm === 600 && product?.height_mm === 337.5 ? '<img src="/static/showroom-cabinet.png" alt="Representative LED cabinet illustration">' : product ? modelImage(product, '') : ''}</div><div><strong>${esc(compactName(product))}</strong><small>LED Cabinet</small></div><div class="summary-quantity">${result ? result.count : '—'}<span>pcs</span></div></div><div class="summary-item summary-controller"><div><strong>${esc(c?.name || 'Select controller')}</strong><small>${esc(c?.kind || 'LED wall controller')}</small></div><div class="summary-quantity">${esc($('q_controller_qty').value || '0')}<span>pcs</span></div></div>`;
    // Main cards match the reference; the exact and cabinet sizes remain available in results.
    if (result) {
        const exact = $('preview_mode').value === 'exact', d = exact ? result.design : result;
        const size = exact && $('mode').value === 'dimensions' ? `${dimensionFormat($('screen_width').value)} × ${heightFormat($('screen_height').value)} ${unit}` : `${dimensionFormat(display(d.width_m))} × ${heightFormat(display(d.height_m))} ${unit}`;
        $('metrics').innerHTML = `<div class="metric"><span>Screen Size</span><strong>${esc(size)}</strong><small>${d.width_m.toFixed(3)} × ${d.height_m.toFixed(3)} m</small></div><div class="metric"><span>Video Resolution</span><strong>${esc(resolutionText(result))}</strong><small id="total-video-pixels">${esc(totalPixelsText(result))}</small></div><div class="metric"><span>Cabinet Count</span><strong>${result.count} cabinets</strong><small>${result.columns} (W) × ${result.rows} (H)</small></div><div class="metric"><span>Screen Area</span><strong id="screen-area-sqft">${quotationAreaSqft().toFixed(3)} sq.ft.</strong><small>${(quotationAreaSqft() * 0.09290304).toFixed(3)} m²</small></div>`;
    }
}
function syncReferenceControls() {
    document.querySelectorAll('[data-environment]').forEach(b => { b.classList.toggle('active', b.dataset.environment === environment); b.setAttribute('aria-pressed', String(b.dataset.environment === environment)); });
    document.querySelectorAll('[data-finish]').forEach(b => { b.classList.toggle('active', b.dataset.finish === $('finish').value); b.setAttribute('aria-pressed', String(b.dataset.finish === $('finish').value)); });
    const cabinetLabel = $('product-summary').querySelector('.cabinet-stat>span'); if (cabinetLabel) cabinetLabel.textContent = 'Cabinet size';
    const select = $('product'); for (const o of select.options) o.textContent = (catalogue.find(p => p.id === o.value)?.name || o.textContent).replace(' (original cabinet)', '').split(' · ')[0];
    updatePreviewButtons();
}
const refFullPrices = updateFullPrices;
updateFullPrices = function () { refFullPrices(); if ($('controller-specs')) updateReferencePanels(); };
$('header-catalogue').onclick = () => $('catalogue-btn').click(); $('header-projects').onclick = () => $('projects-btn').click();
$('summary-download').onclick = () => $('download-quotation').click();
document.querySelectorAll('[data-environment]').forEach(b => b.onclick = () => { selectEnvironment(b.dataset.environment); syncReferenceControls(); });
document.querySelectorAll('[data-finish]').forEach(b => b.onclick = () => {
    const v = b.dataset.finish; $('finish').value = v;
    if (v === 'custom') { $('wall-photo').closest('details').open = true; $('wall-photo').click(); }
    else { wallPhoto = ''; $('wall-photo').value = ''; if (v === 'white') $('wall_colour').value = '#f0f1f3'; }
    draw(); syncReferenceControls(); if (result) renderResults();
});
document.querySelectorAll('[data-rate-step]').forEach(b => b.onclick = () => { const input = $('q_controller_rate'); input.value = Math.max(0, Number(input.value || 0) + Number(b.dataset.rateStep)); input.dispatchEvent(new Event('input', { bubbles: true })); });
$('preview-fullscreen').onclick = async () => { const panel = document.querySelector('.preview-panel'); try { if (document.fullscreenElement) await document.exitFullscreen(); else await panel.requestFullscreen(); } catch { message('Fullscreen is unavailable in this browser.', true); } };
document.querySelectorAll('[data-workspace]').forEach(b => b.onclick = () => {
    document.querySelectorAll('[data-workspace]').forEach(el => el.classList.toggle('active', el === b));
    const page = b.dataset.workspace;
    if (page === 'screens') { $('catalogue-btn').click(); return; }
    if (page === 'quotation') { showTab('results'); window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
    showTab('designer');
    let target = document.querySelector('.screen-settings');
    if (page === 'content') { target = document.querySelector('.studio-background'); target.open = true; }
    if (page === 'layouts' || page === 'settings') { target = $('advanced-layout'); target.open = true; }
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});
$('finish').addEventListener('change', syncReferenceControls);
// File uploads still use the original validation and readers.
$('wall-photo').addEventListener('change', () => { $('finish').value = 'custom'; syncReferenceControls(); });
syncReferenceControls();


const railIcons = { design: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>', screens: '<rect x="2" y="3" width="20" height="16"/><path d="M7 23h10M12 19v4"/>', content: '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="m3 17 6-6 4 4 4-5 5 7"/><circle cx="7" cy="7" r="1"/>', layouts: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>', quotation: '<path d="M5 2h10l4 4v16H5zM15 2v5h4M8 11h8M8 15h8M8 19h5"/>', settings: '<path d="m9 3 1-2h4l1 2 3 2 3 1v4l-2 2 1 4-3 3-4-1-2 2H7l-1-3-3-2v-4l2-2V6z"/><circle cx="12" cy="11" r="4"/>' };
document.querySelectorAll('[data-workspace]').forEach(b => b.querySelector('span').innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${railIcons[b.dataset.workspace]}</svg>`);
$('preview-fullscreen').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6"/></svg>';
const drawing = $('drawing'); let pan = null;
$('pan-preview').onclick = () => { const enabled = $('pan-preview').getAttribute('aria-pressed') !== 'true'; $('pan-preview').setAttribute('aria-pressed', String(enabled)); drawing.classList.toggle('pan-enabled', enabled); };
drawing.addEventListener('pointerdown', e => { if (!drawing.classList.contains('pan-enabled')) return; pan = { x: e.clientX, y: e.clientY, left: drawing.scrollLeft, top: drawing.scrollTop }; drawing.setPointerCapture(e.pointerId); drawing.classList.add('panning'); });
drawing.addEventListener('pointermove', e => { if (!pan) return; drawing.scrollLeft = pan.left - (e.clientX - pan.x); drawing.scrollTop = pan.top - (e.clientY - pan.y); });
const endPan = () => { pan = null; drawing.classList.remove('panning'); }; drawing.addEventListener('pointerup', endPan); drawing.addEventListener('pointercancel', endPan);

let roomDrag = null;
function roomPoint(event) {
    const svg = $('wall-svg'), point = svg.createSVGPoint();
    point.x = event.clientX; point.y = event.clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
}
function resetRoomPosition() {
    roomPhotoPosition.x = 0; roomPhotoPosition.y = 0; roomPhotoPosition.scale = 1;
    $('room-photo-scale').value = '100'; $('room-photo-scale-value').textContent = '100%';
    draw(); if (result) renderResults();
}
$('room-photo-scale').addEventListener('input', () => {
    roomPhotoPosition.scale = Number($('room-photo-scale').value) / 100;
    $('room-photo-scale-value').textContent = $('room-photo-scale').value + '%';
    draw(); if (result) renderResults();
});
$('reset-room-photo').onclick = resetRoomPosition;
$('wall-photo').addEventListener('change', resetRoomPosition);
$('clear-photo').addEventListener('click', resetRoomPosition);
drawing.addEventListener('pointerdown', event => {
    if (drawing.classList.contains('pan-enabled') || event.button !== 0 || !event.target.closest('#wall-svg')) return;
    if (!['concrete', 'custom'].includes($('finish').value)) return;
    const point = roomPoint(event);
    roomDrag = { pointerId: event.pointerId, startX: point.x, startY: point.y, x: roomPhotoPosition.x, y: roomPhotoPosition.y };
    drawing.setPointerCapture(event.pointerId); drawing.classList.add('dragging-room'); event.preventDefault();
});
drawing.addEventListener('pointermove', event => {
    if (!roomDrag || event.pointerId !== roomDrag.pointerId) return;
    const point = roomPoint(event);
    roomPhotoPosition.x = roomDrag.x + point.x - roomDrag.startX;
    roomPhotoPosition.y = roomDrag.y + point.y - roomDrag.startY;
    draw();
});
function endRoomDrag(event) {
    if (!roomDrag || event.pointerId !== roomDrag.pointerId) return;
    roomDrag = null; drawing.classList.remove('dragging-room');
    if (result) renderResults();
}
drawing.addEventListener('pointerup', endRoomDrag);
drawing.addEventListener('pointercancel', endRoomDrag);
