'use strict';

const main = document.getElementById('impact');
let projection;
let requestNumber = 0;

function element(parent, tag, text) {
  const child = parent.appendChild(document.createElement(tag));
  if (text !== undefined) child.textContent = String(text);
  return child;
}

function link(parent, label, path) {
  element(parent, 'a', label).href = path;
}

async function api(route, params = {}) {
  const search = new URLSearchParams(params);
  const response = await fetch('/api/impact/' + route + '?' + search);
  if (!response.ok) throw new Error('Impact query failed (HTTP ' + response.status + ')');
  const result = await response.json();
  if (projection && projection !== result.projection_id) throw new Error('Impact projection changed. Reload to continue.');
  projection = result.projection_id;
  return result;
}

function table(parent, columns, rows) {
  const body = element(parent, 'table');
  const head = element(element(body, 'thead'), 'tr');
  columns.forEach(([title]) => element(head, 'th', title));
  const data = element(body, 'tbody');
  for (const row of rows) {
    const line = element(data, 'tr');
    for (const [, display] of columns) {
      const cell = element(line, 'td');
      if (typeof display === 'function') display(cell, row);
      else cell.textContent = row[display] ?? 'Not recorded';
    }
  }
}

async function page(parent, route, parameters, columns, cursor = '') {
  const params = {...parameters};
  if (cursor) Object.assign(params, {after: cursor, projection});
  const result = await api(route, params);
  parent.replaceChildren();
  if (!result.items.length) element(parent, 'p', 'No observations on this page.');
  else table(parent, columns, result.items);
  if (cursor) {
    const first = element(parent, 'button', 'First page');
    first.onclick = () => page(parent, route, parameters, columns).catch(error => element(parent, 'p', error.message));
  }
  if (result.next_cursor) {
    const next = element(parent, 'button', 'Next page');
    next.onclick = () => page(parent, route, parameters, columns, result.next_cursor)
      .catch(error => element(parent, 'p', error.message));
  }
}

const enc = encodeURIComponent;
const groupColumns = [
  ['Check', (cell, row) => link(cell, row.subject, '#/group/' + enc(row.id))],
  ['Grouping', 'kind'], ['Scope', 'scope'], ['Original members', 'member_count'],
  ['Impact', (cell, row) => { cell.textContent = ['Unassessed / no observed break', 'Contains potential impact', 'Contains confirmed direct impact'][row.rank]; }]
];
const memberColumns = [
  ['Finding', (cell, row) => link(cell, row.id, '#/finding/' + enc(row.id))],
  ['Original status', 'status'], ['Scope of impact', 'assessment'], ['Association', 'strength'],
  ['Consumer', (cell, row) => { cell.textContent = row.consumer_path ? row.consumer_image + ' ' + row.consumer_path : 'Not recorded'; }],
  ['Root', (cell, row) => { cell.textContent = row.root_path ? row.root_image + ' ' + row.root_path : 'Not recorded'; }],
  ['Observed provider', 'observed_provider'], ['Reason', 'reason']
];

async function showGroups(panel, route, filter = {}) {
  const form = element(panel, 'form');
  const scope = element(element(form, 'label', 'Interface scope '), 'select');
  for (const value of ['', 'PUBLIC', 'INTERNAL', 'UNDETERMINED']) {
    const opt = element(scope, 'option', value || 'All');
    opt.value = value;
  }
  const rank = element(element(form, 'label', ' Impact '), 'select');
  for (const [value, label] of [['', 'All'], ['2', 'Confirmed'], ['1', 'Potential'], ['0', 'Unassessed or no observed break']]) {
    const opt = element(rank, 'option', label);
    opt.value = value;
  }
  element(form, 'button', 'Filter');
  const rows = element(panel, 'section');
  form.onsubmit = event => {
    event.preventDefault();
    page(rows, route, {...filter, scope: scope.value, rank: rank.value}, groupColumns)
      .catch(error => { rows.replaceChildren(); element(rows, 'p', error.message); });
  };
  await page(rows, route, filter, groupColumns);
}

async function showFinding(panel, id) {
  const params = {finding: id};
  const data = await api('finding', params);
  element(panel, 'h2', data.interface);
  link(panel, 'Open original Finding ' + id, '/#/finding/' + enc(id));
  element(panel, 'p', data.status + ' · ' + data.strength + ' · ' + data.assessment + ' · ' + data.reason);
  if (data.proof) {
    element(panel, 'h3', 'Dual resolver observation');
    element(panel, 'pre', JSON.stringify(data.proof, null, 2));
  }
  element(panel, 'h3', 'Original Evidence');
  const refs = element(panel, 'section');
  async function showEvidence(start = '') {
    const detail = start ? await api('finding', {...params, after: start, projection}) : data;
    refs.replaceChildren();
    for (const entry of detail.evidence) {
      const row = element(refs, 'p');
      if (entry.available) link(row, entry.reference, '/evidence?ref=' + enc(entry.reference));
      else row.textContent = entry.reference + ' · unavailable';
    }
    if (!detail.evidence.length) element(refs, 'p', 'No Evidence reference recorded.');
    if (detail.next_cursor) {
      element(refs, 'button', 'More Evidence').onclick = () => showEvidence(detail.next_cursor)
        .catch(error => element(refs, 'p', error.message));
    }
  }
  await showEvidence();
  element(panel, 'h3', 'Impact groups for this Finding');
  await page(element(panel, 'section'), 'finding-groups', params, groupColumns);
}

async function showGroup(panel, id) {
  const params = {group: id};
  const group = await api('group', params);
  element(panel, 'h2', group.subject);
  element(panel, 'p', group.kind + ' · ' + group.reason + ' · ' + group.scope);
  if (group.authority) element(panel, 'p', 'Scope authority: ' + group.authority);
  element(panel, 'p', 'Recommended validation: ' + group.recommendation);
  element(panel, 'h3', 'Original Findings');
  await page(element(panel, 'section'), 'members', params, memberColumns);
  element(panel, 'h3', 'Consumers with recorded dependency checks');
  await page(element(panel, 'section'), 'consumers', params, memberColumns);
  element(panel, 'h3', 'Package roles and affected components');
  await page(element(panel, 'section'), 'packages', params, [
    ['Package', (cell, row) => link(cell, row.name, '#/package/' + enc(row.side) + '/' + enc(row.package_id))],
    ['Image', 'side'], ['Role', 'role'], ['Scope', 'scope'],
    ['Ownership', (cell, row) => { cell.textContent = row.complete ? 'Recorded' : 'Uncertain'; }],
    ['Confirmed affected component', (cell, row) => { cell.textContent = row.confirmed ? 'Present' : 'Unconfirmed'; }]
  ]);
}

async function render() {
  const sequence = ++requestNumber;
  const panel = document.createElement('section');
  main.replaceChildren(panel);
  try {
    const [route, id, extra] = location.hash.slice(2).split('/').map(decodeURIComponent);
    if (route === 'group') await showGroup(panel, id);
    else if (route === 'finding') await showFinding(panel, id);
    else if (route === 'package') {
      element(panel, 'h2', 'Package impact groups');
      await showGroups(panel, 'package-groups', {side: id, package: extra});
    } else {
      const overview = await api('overview');
      element(panel, 'p', overview.engine + ' · ' + overview.mode + ' · ' + overview.state);
      element(panel, 'p', 'Original findings: ' + overview.summary.source_findings + ' · Impact groups: ' + overview.summary.groups);
      element(panel, 'p', Object.entries(overview.summary.assessments).map(([k, n]) => k + ': ' + n).join(' · '));
      if (overview.replay_limits.length) element(panel, 'p', 'Replay limits reached for ' + overview.replay_limits.length + ' roots.');
      await showGroups(panel, 'groups');
    }
  } catch (error) {
    if (sequence === requestNumber) {
      panel.replaceChildren();
      element(panel, 'p', error.message);
    }
  }
}

window.addEventListener('hashchange', render);
render();
