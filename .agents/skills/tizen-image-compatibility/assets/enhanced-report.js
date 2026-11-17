'use strict';
// All image-controlled data is rendered as text, never as markup.
const app = document.getElementById('app');
const statuses = ['', 'UNKNOWN', 'INCOMPATIBLE', 'COMPATIBLE', 'IDENTICAL', 'NOT_APPLICABLE'];
let generation = 0;
function node(tag, text, parent, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text === null ? 'UNKNOWN' : String(text);
  if (className) el.className = className;
  if (parent) parent.append(el);
  return el;
}
function link(parent, label, route) { const a = node('a', label, parent); a.href = '#/' + route; return a; }
function enc(value) { return encodeURIComponent(value); }
function pretty(parent, value, title = 'Details') {
  const d = node('details', undefined, parent); node('summary', title, d);
  node('pre', JSON.stringify(value, null, 2), d); return d;
}
function evidence(parent, refs) {
  if (!refs || !refs.length) { node('p', 'Evidence references: UNKNOWN / not recorded', parent); return; }
  const d = node('details', undefined, parent); node('summary', 'Evidence references (' + refs.length + ')', d);
  const ul = node('ul', undefined, d);
  for (const ref of refs) {
    const li = node('li', undefined, ul), a = node('a', ref, li);
    a.href = '/evidence?ref=' + enc(ref); a.target = '_blank'; a.rel = 'noopener';
  }
}
async function api(route, params = {}) {
  const response = await fetch('/api/' + route + '?' + new URLSearchParams(params));
  if (!response.ok) throw new Error('Query failed: HTTP ' + response.status);
  return response.json();
}
function table(parent, columns, rows) {
  const div = node('div', undefined, parent, 'scroll'), t = node('table', undefined, div);
  const head = node('tr', undefined, node('thead', undefined, t));
  for (const [label] of columns) node('th', label, head);
  const body = node('tbody', undefined, t);
  for (const row of rows) {
    const tr = node('tr', undefined, body);
    for (const [, getter] of columns) {
      const td = node('td', undefined, tr), value = getter(row, td);
      if (value !== undefined) {
        td.textContent = value === null ? 'UNKNOWN' : typeof value === 'object' ? JSON.stringify(value) : String(value);
        if (statuses.includes(value) && value) td.className = 'status-' + value;
      }
    }
  }
}
async function listing(parent, route, params, columns, filters = []) {
  const token = generation, form = node('form', undefined, parent), controls = {};
  for (const [key, label, values] of filters) {
    const lab = node('label', label, form), el = node(values ? 'select' : 'input', undefined, lab);
    el.name = key;
    if (values) for (const value of values) { const o = node('option', value || 'All', el); o.value = value; }
    el.value = params[key] || ''; controls[key] = el;
  }
  node('button', 'Search / Apply', form).type = 'submit';
  const results = node('div', undefined, parent);
  let serial = 0;
  async function load(offset = 0) {
    const current = ++serial;
    for (const [key, el] of Object.entries(controls)) params[key] = el.value;
    results.replaceChildren(); node('p', 'Loading…', results);
    try {
      const started = performance.now(), data = await api(route, {...params, offset, limit: 50});
      if (token !== generation || current !== serial) return;
      results.replaceChildren();
      node('p', 'Showing ' + (data.rows.length ? offset + 1 : 0) + '–' + (offset + data.rows.length) + ' of ' + data.total +
        ' · ' + Math.max(0, data.total - data.rows.length) + ' rows outside this page · query ' + Math.round(performance.now() - started) + ' ms. Full CSVs are not truncated.', results);
      table(results, columns, data.rows);
      const pager = node('div', undefined, results, 'pager');
      const prev = node('button', 'Previous', pager); prev.disabled = offset === 0; prev.onclick = () => load(Math.max(0, offset - 50));
      const next = node('button', 'Next', pager); next.disabled = offset + 50 >= data.total; next.onclick = () => load(offset + 50);
    } catch (error) { if (current === serial) { results.replaceChildren(); node('p', error.message, results, 'error'); } }
  }
  form.onsubmit = event => { event.preventDefault(); load(); };
  await load();
}
const findingColumns = [
  ['Finding ID', (r, td) => { link(td, r.id, 'finding/' + enc(r.id)); }],
  ['Status', r => r.status], ['Dimension', r => r.dimension], ['Interface', r => r.interface],
  ['Direct consumer', r => (r.consumer_image || '?') + ':' + r.consumer_path],
  ['Root consumer', r => r.root_path === null ? null : (r.root_image || '?') + ':' + r.root_path], ['Provider', r => r.provider_path]
];
async function findings(parent, params = {}) {
  await listing(parent, 'findings', params, findingColumns, [['id', 'Exact original finding ID'], ['status', 'Status', statuses], ['dimension', 'Dimension'], ['consumer', 'Exact direct consumer path'], ['root', 'Exact root consumer path'], ['provider', 'Exact provider path']]);
}
const elfColumns = [
  ['ELF', (r, td) => { link(td, r.gcc_path || r.llvm_path, 'elf/' + enc(r.pair_id)); }],
  ['Match', r => r.match_status], ['GCC observed FUNC', r => r.gcc_observed_counts?.func ?? null], ['LLVM observed FUNC', r => r.llvm_observed_counts?.func ?? null],
  ['Missing', r => r.differences.missing], ['Added', r => r.differences.added], ['Changed', r => r.differences.changed], ['ABI', r => r.abi_status]
];
async function render() {
  const token = ++generation; app.replaceChildren();
  const parts = (location.hash || '#/overview').slice(2).split('/').map(decodeURIComponent);
  const [route, id, detail] = parts;
  try {
    if (route === 'overview') {
      const data = await api('overview'); if (token !== generation) return;
      node('h2', 'Overview', app); node('p', data.notice, app);
      node('p', 'Original result: ' + (data.original_overall ?? 'UNKNOWN') + ' · Verification: ' + (data.original_verification ?? 'UNKNOWN'), app);
      const cards = node('div', undefined, app, 'cards');
      for (const [key, count] of Object.entries(data.status_counts)) { const c = node('div', key, cards, 'card'); node('strong', count.toLocaleString(), c); }
      table(app, [['Image', r => r[0]], ['Installed RPM', r => r[1].inventory?.installed_count ?? null], ['Collected ELF rows', r => r[1].collected_elf_rows], ['Canonical ELFs', r => r[1].canonical_elf_count], ['Observed FUNC', r => r[1].observed_unique_export_counts.func], ['Incomplete ELFs', r => r[1].incomplete_canonical_elf_count]], Object.entries(data.images));
      node('h2', 'Linking: recorded reasons', app);
      node('p', data.linking.raw_findings + ' original findings → ' + data.linking.groups + ' navigation groups; ' + data.linking.distinct_interfaces + ' distinct recorded interfaces. Groups are not merged compatibility conclusions.', app);
      table(app, [['Reason', (r, td) => { link(td, r.reason_category, 'groups/' + enc(r.reason_category)); }], ['Status', r => r.status], ['Findings', r => r.raw_finding_count], ['Groups', r => r.group_count], ['Interfaces', r => r.distinct_recorded_interface_count]], data.linking.reason_status_distribution);
      pretty(app, data.original_coverage, 'Original coverage (not compatibility proof)'); pretty(app, data.symbol_difference_rows, 'Symbol difference observations'); pretty(app, data.dimension_status_counts, 'Findings by dimension / status');
    } else if (route === 'packages') {
      node('h2', 'All package inventories', app);
      await listing(app, 'packages', {}, [
        ['Package', (r, td) => { link(td, r.name, 'package/' + enc(r.side) + '/' + enc(r.package_id)); }], ['Image', r => r.side], ['Match', r => r.match_status],
        ['Observed ELFs', r => r.observed_owned_elf_count], ['Observed FUNC', r => r.observed_counts.func], ['Complete FUNC', r => r.counts.func], ['Observed missing', r => r.observed_differences.missing], ['Complete missing', r => r.differences.missing], ['ABI', r => r.abi], ['API', r => r.api], ['Linking', r => r.linking], ['Findings', r => r.finding_count], ['UNKNOWN', r => r.unknown_count]
      ], [['q', 'Package name'], ['side', 'Image', ['', 'baseline', 'candidate']], ['abi', 'ABI', statuses], ['api', 'API', statuses], ['linking', 'Linking', statuses], ['sort', 'Sort (FUNC / missing use observed counts)', ['name', 'func', 'missing', 'findings', 'unknown']]]);
    } else if (route === 'package') {
      const data = await api('package', {side: id, id: detail}); if (token !== generation) return;
      node('h2', data.summary.name + ' · ' + id, app);
      pretty(app, data.summary, 'Package statistics and original outcomes'); pretty(app, data.original_assessment, 'Original assessment fields');
      node('h2', 'Owned canonical ELF pairs', app); await listing(app, 'elfs', {side: id, package: detail}, elfColumns);
      if (token !== generation) return;
      node('h2', 'Original package findings', app); await findings(app, {side: id, package: detail});
    } else if (route === 'elf') {
      const data = await api('elf', {id}); if (token !== generation) return;
      node('h2', data.gcc_path || data.llvm_path, app);
      pretty(app, data, 'ELF counts, aliases, owners, SONAME, DT_NEEDED and recorded ABI'); evidence(app, data.evidence);
      node('h2', 'Dynamic exports and difference observations', app);
      await listing(app, 'symbols', {pair: id}, [['Symbol', r => r.symbol_name], ['Version', r => r.symbol_version], ['Type', r => r.symbol_type], ['Difference', r => r.difference_type], ['Original compatibility', r => r.compatibility_status], ['GCC attributes', r => r.gcc_symbol_attributes], ['LLVM attributes', r => r.llvm_symbol_attributes], ['Findings / evidence', (r, td) => { for (const fid of r.finding_ids) { link(td, fid, 'finding/' + enc(fid)); node('br', undefined, td); } evidence(td, r.evidence); }]],
        [['q', 'Symbol name'], ['type', 'Difference type', ['', 'MISSING', 'ADDED', 'TYPE_CHANGED', 'SIZE_CHANGED', 'VISIBILITY_CHANGED', 'BINDING_CHANGED', 'VERSION_CHANGED', 'MATCHED', 'UNKNOWN']]]);
      if (token !== generation) return;
      node('h2', 'Original ELF findings', app); await findings(app, {elf: id});
    } else if (route === 'groups') {
      node('h2', 'Linking navigation groups', app);
      await listing(app, 'groups', {reason: id || ''}, [['Group', (r, td) => { link(td, r.group_id, 'group/' + enc(r.group_id)); }], ['Reason', r => r.reason_category], ['Status', r => r.status], ['Interface / dependency', r => r.interface_or_dependency], ['Raw findings', r => r.raw_finding_count], ['Packages', r => r.affected_package_count], ['Direct ELFs', r => r.affected_elf_count], ['Root consumers', r => r.affected_root_consumer_count]], [['q', 'Interface contains'], ['reason', 'Recorded resolution'], ['status', 'Status', statuses]]);
    } else if (route === 'group') {
      const data = await api('group', {id}); if (token !== generation) return;
      node('h2', data.reason_category + ' · ' + data.interface_or_dependency, app);
      node('p', data.interpretation, app); pretty(app, data, 'Group key and exact counts'); evidence(app, data.evidence_references);
      await findings(app, {group: id});
    } else if (route === 'finding') {
      const data = await api('finding', {id}); if (token !== generation) return;
      node('h2', data.id + ' · ' + data.status, app); node('pre', JSON.stringify(data, null, 2), app); evidence(app, data.evidence);
      const ownership = data.package_ownership || {};
      for (const [role, side] of [['consumer', ownership.consumer_image || data.consumer_image || 'baseline'], ['candidate_provider', 'candidate'], ['root_consumer', data.root_consumer_image || 'baseline']]) {
        for (const owner of ownership[role]?.owners || []) { const p = node('p', role + ': ', app); link(p, owner, 'package/' + enc(side) + '/' + enc(owner)); }
      }
    } else if (route === 'findings') { node('h2', 'All original findings', app); await findings(app); }
    else throw new Error('Unknown report view');
  } catch (error) { if (token === generation) node('p', error.message, app, 'error'); }
}
if (location.protocol !== 'file:') {
  document.getElementById('offline').hidden = true; document.getElementById('static').hidden = true;
  window.addEventListener('hashchange', render); render();
}
