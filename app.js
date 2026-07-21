function fmtTime(iso) {
  if (!iso || iso.length <= 10) return 'egész nap';
  const d = new Date(iso);
  return d.toLocaleTimeString('hu-HU', { hour: '2-digit', minute: '2-digit' });
}

function fmtRange(start, end) {
  if (!start || start.length <= 10) return 'egész nap';
  return `${fmtTime(start)}–${fmtTime(end)}`;
}

function renderTimeline(el, events) {
  if (!events?.length) {
    el.innerHTML = '<p class="event-loc">Nincs esemény.</p>';
    return;
  }
  el.innerHTML = events.map(e => `
    <div class="event ${e.type || ''}">
      <div class="event-time">${fmtRange(e.start, e.end)}</div>
      <div>
        <div class="event-title">${e.title}</div>
        ${e.location ? `<div class="event-loc">📍 ${e.location}</div>` : ''}
      </div>
    </div>
  `).join('');
}

function renderTasks(el, items) {
  if (!items?.length) {
    el.innerHTML = '<li>Nincs nyitott feladat.</li>';
    return;
  }
  el.innerHTML = items.map(t => `
    <li>
      <span>${t.title}</span>
      <span class="badge ${t.priority}">${t.priority}</span>
    </li>
  `).join('');
}

function renderList(el, items, empty = '—') {
  if (!items?.length) {
    el.innerHTML = `<li>${empty}</li>`;
    return;
  }
  el.innerHTML = items.map(i => {
    if (typeof i === 'string') return `<li>${i}</li>`;
    const range = i.start ? `${fmtRange(i.start, i.end)} — ${i.label}` : i.label;
    return `<li>${range}</li>`;
  }).join('');
}

async function load() {
  const res = await fetch('data/latest.json');
  const data = await res.json();

  document.getElementById('updated').textContent =
    `Frissítve: ${new Date(data.generated_at).toLocaleString('hu-HU')}`;

  renderTimeline(document.getElementById('timeline-today'), data.calendar?.today);
  renderTimeline(document.getElementById('timeline-tomorrow'), data.calendar?.tomorrow);
  renderList(document.getElementById('free-slots'), data.free_slots);
  renderList(document.getElementById('warnings'), data.warnings, 'Minden rendben.');
  renderTasks(document.getElementById('tasks-personal'), data.tasks?.personal);
  renderTasks(document.getElementById('tasks-gluxshop'), data.tasks?.gluxshop);
}

load().catch(err => {
  document.body.innerHTML = `<p style="padding:2rem;color:#ff6b6b">Nem sikerült betölteni az adatot: ${err.message}</p>`;
});
