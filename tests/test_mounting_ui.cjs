// Run with: node tests/test_mounting_ui.cjs
// Exercise the real event handlers with form elements; no browser or database required.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const base = path.join(__dirname, '..', 'av_wall_designer');
const html = fs.readFileSync(path.join(base, 'templates/index.html'), 'utf8');
const elements = new Map();
for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    const listeners = {};
    let value = match[0].match(/\bvalue="([^"]*)"/)?.[1] ?? '';
    elements.set(match[1], {
        get value() { return value; }, set value(v) { value = String(v); },
        hidden: /\bhidden\b/.test(match[0]), disabled: false, textContent: '', innerHTML: '',
        checked: false, style: {}, classList: { toggle() {} },
        addEventListener(type, listener) { (listeners[type] ??= []).push(listener); },
        dispatch(type) { for (const listener of listeners[type] ?? []) listener({ target: this }); },
        setCustomValidity() {}, removeAttribute() {}, querySelector() { return { disabled: false }; },
    });
}
const get = id => { assert.ok(elements.has(id), `Unknown element: ${id}`); return elements.get(id); };
const context = vm.createContext({
    document: { getElementById: get, querySelectorAll: () => [] },
    localStorage: { getItem: () => null }, window: {}, console,
    fetch: () => new Promise(() => {}), setTimeout: () => 0, clearTimeout: () => {},
});
const run = source => vm.runInContext(source, context);
run(fs.readFileSync(path.join(base, 'static/app.js'), 'utf8'));
get('q_mount_type').value = 'none';
get('preview_mode').value = 'exact';
get('mode').value = 'dimensions';
get('screen_width').value = '10';
get('screen_height').value = '10';
get('q_wall_rate').value = '';
// Geometry/API behavior is covered by the Python tests; keep this check on quotation controls.
run(`result = {design:{width_m:3.048,height_m:3.048},width_m:3,height_m:2};
     updateVisibility=()=>{}; selectScene=()=>{}; selectEnvironment=()=>{};
     showTab=()=>{}; schedule=()=>{};`);
run(fs.readFileSync(path.join(base, 'static/studio.js'), 'utf8'));
function select(type) { get('q_mount_type').value = type; get('q_mount_type').dispatch('change'); }

assert.equal(get('q_mount_rate_field').hidden, true);
assert.doesNotMatch(get('studio-cost-lines').innerHTML, /Uni-pole|Mounting structure/);
select('unipole');
assert.equal(get('q_mount_rate').value, '175000');
assert.equal(get('q_mount_rate_field').hidden, false);
assert.equal(run('selectedMounting().price'), 175000);
assert.match(get('studio-total').textContent, /2,06,500/);
get('screen_width').value = '20';
run('updateFullPrices()');
assert.equal(run('selectedMounting().price'), 175000);

select('structure');
assert.equal(get('q_mount_rate').value, '800');
assert.equal(run('selectedMounting().price'), 160000);
assert.match(get('studio-total').textContent, /1,88,800/);
get('q_mount_rate').value = '900';
get('q_mount_rate').dispatch('input');
assert.equal(run('selectedMounting().price'), 180000);
assert.match(get('studio-total').textContent, /2,12,400/);
get('q_mount_description').value = 'Custom structure';
run('savedMountingProject = state()');
assert.equal(run('savedMountingProject.quotation.mount_type'), 'structure');

select('none');
assert.equal(get('q_mount_rate').value, '');
assert.equal(get('q_mount_rate').disabled, true);
assert.doesNotMatch(get('studio-cost-lines').innerHTML, /Uni-pole|Mounting structure/);
run('restore(savedMountingProject)');
assert.equal(get('q_mount_type').value, 'structure');
assert.equal(get('q_mount_rate').value, '900');
assert.equal(get('q_mount_description').value, 'Custom structure');
assert.equal(get('q_mount_rate_field').hidden, false);
run('restore({unit:"ft"})');
assert.equal(get('q_mount_type').value, 'none');
assert.equal(get('q_mount_rate_field').hidden, true);
assert.doesNotMatch(get('studio-cost-lines').innerHTML, /Uni-pole|Mounting structure/);

select('structure');
run('unit="m"');
get('screen_width').value = '3';
get('screen_height').value = '2';
run('updateFullPrices()');
assert.equal(run('selectedMounting().price'), 51666.77);
console.log('PASS: mounting selection, defaults, area changes, edited rates, live GST totals, saved selections, legacy projects, and metre conversion.');
