'use strict';

const elements = Object.fromEntries(['scope', 'summary', 'coverage', 'change', 'observations', 'next', 'error']
  .map(id => [id, document.getElementById(id)]));
let cursor = null;
let generation = 0;

async function request(route, parameters = {}) {
  const reply = await fetch('/api/history/' + route + '?' + new URLSearchParams(parameters));
  if (!reply.ok) throw new Error('Report request failed (' + reply.status + ')');
  return reply.json();
}

async function showPage(after) {
  const current = ++generation;
  elements.next.disabled = true;
  elements.error.textContent = '';
  try {
    const page = await request('entries', {after, change: elements.change.value});
    if (current !== generation) return;
    elements.observations.replaceChildren();
    for (const finding of page.items) {
      const row = document.createElement('tr');
      for (const value of [finding.dimension, finding.component + ' · ' + finding.interface,
        [finding.before_id, finding.before_status].filter(Boolean).join(' · '),
        [finding.after_id, finding.after_status].filter(Boolean).join(' · '),
        finding.change, finding.match + ' · ' + finding.evidence_change]) {
        const cell = document.createElement('td');
        cell.textContent = value || '—';
        row.append(cell);
      }
      elements.observations.append(row);
    }
    cursor = page.next_cursor;
    elements.next.disabled = cursor === null;
  } catch (error) {
    if (current === generation) elements.error.textContent = error.message;
  }
}

async function initialize() {
  const overview = await request('overview');
  elements.scope.textContent = overview.scope + ' · ' + overview.direction;
  elements.summary.textContent = Object.entries(overview.summary.change)
    .map(([name, count]) => name + ': ' + count.toLocaleString()).join(' · ');
  for (const value of Object.keys(overview.summary.change)) elements.change.add(new Option(value, value));
  elements.coverage.textContent = JSON.stringify({before: overview.before_coverage, after: overview.after_coverage}, null, 2);
  await showPage(0);
}

elements.change.addEventListener('change', () => showPage(0));
elements.next.addEventListener('click', () => { if (cursor !== null) showPage(cursor); });
initialize().catch(error => { elements.error.textContent = error.message; });
