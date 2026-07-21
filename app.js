/* Kairos dashboard — live complete + calendar move via Google OAuth (GIS token) */

const TOKEN_KEY = 'kairos_google_token';
const TOKEN_EXP_KEY = 'kairos_google_token_exp';

let state = {
  data: null,
  token: null,
  tokenClient: null,
  gisReady: false,
};

function cfg() {
  const base = window.KAIROS_CONFIG || {};
  const params = new URLSearchParams(location.search);
  const override = params.get('client_id');
  return {
    ...base,
    clientId: override || base.clientId || '',
  };
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtTime(iso) {
  if (!iso || iso.length <= 10) return 'egész nap';
  return new Date(iso).toLocaleTimeString('hu-HU', { hour: '2-digit', minute: '2-digit' });
}

function fmtRange(start, end) {
  if (!start || start.length <= 10) return 'egész nap';
  return `${fmtTime(start)}–${fmtTime(end)}`;
}

function toLocalInputValue(iso) {
  if (!iso || iso.length <= 10) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(value) {
  // Treat as local Europe/Budapest wall time → ISO with offset from browser
  const d = new Date(value);
  return d.toISOString();
}

function shiftIso(iso, minutes) {
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() + minutes);
  return d.toISOString();
}

function durationMs(start, end) {
  return new Date(end) - new Date(start);
}

function toast(msg, kind = 'info') {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = `toast show ${kind}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.classList.remove('show');
  }, 4200);
}

function loadStoredToken() {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const exp = Number(sessionStorage.getItem(TOKEN_EXP_KEY) || 0);
  if (token && exp > Date.now() + 30_000) {
    state.token = token;
    return true;
  }
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXP_KEY);
  state.token = null;
  return false;
}

function storeToken(accessToken, expiresInSec = 3600) {
  state.token = accessToken;
  sessionStorage.setItem(TOKEN_KEY, accessToken);
  sessionStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + expiresInSec * 1000));
}

function clearToken() {
  state.token = null;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXP_KEY);
}

function isAuthed() {
  return Boolean(state.token);
}

function updateAuthUi() {
  const btn = document.getElementById('auth-btn');
  const status = document.getElementById('auth-status');
  const banner = document.getElementById('auth-banner');
  if (!btn || !status) return;

  if (isAuthed()) {
    btn.textContent = 'Kilépés';
    btn.classList.add('btn-primary');
    status.textContent = 'Google: bejelentkezve (personal)';
    banner?.classList.add('hidden');
  } else {
    btn.textContent = 'Google belépés';
    btn.classList.remove('btn-primary');
    status.textContent = 'Google: nincs belépve — kipipálás / mozgatás lockolva';
    banner?.classList.remove('hidden');
  }
}

function initGis() {
  const { clientId, scopes } = cfg();
  if (!clientId) {
    toast('Hiányzik a Google Client ID (config.js).', 'error');
    return;
  }
  if (!window.google?.accounts?.oauth2) {
    // GIS script still loading
    return;
  }
  state.gisReady = true;
  state.tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: clientId,
    scope: scopes,
    callback: (resp) => {
      if (resp.error) {
        console.error(resp);
        toast(
          `OAuth hiba: ${resp.error}. Ellenőrizd a Client ID Authorized JavaScript origins-t (https://hristos0527.github.io).`,
          'error',
        );
        return;
      }
      storeToken(resp.access_token, Number(resp.expires_in || 3600));
      updateAuthUi();
      toast('Bejelentkezve — kipipálás és mozgatás aktív.', 'ok');
      renderAll();
    },
  });
}

function requestAuth(prompt) {
  if (!state.tokenClient) initGis();
  if (!state.tokenClient) {
    toast('Google Identity Services még nem töltődött be — várj 1 mp-et.', 'error');
    return Promise.reject(new Error('GIS not ready'));
  }
  return new Promise((resolve, reject) => {
    const prev = state.tokenClient.callback;
    state.tokenClient.callback = (resp) => {
      state.tokenClient.callback = prev;
      if (resp.error) {
        reject(new Error(resp.error));
        prev?.(resp);
        return;
      }
      storeToken(resp.access_token, Number(resp.expires_in || 3600));
      updateAuthUi();
      resolve(resp.access_token);
      prev?.(resp);
    };
    state.tokenClient.requestAccessToken({ prompt: prompt || '' });
  });
}

async function ensureAuth() {
  if (isAuthed()) return state.token;
  toast('Google belépés szükséges…');
  return requestAuth('consent');
}

async function apiFetch(url, options = {}) {
  const token = await ensureAuth();
  const res = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    clearToken();
    updateAuthUi();
    throw new Error('Token lejárt — lépj be újra.');
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body.slice(0, 220)}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function completeTask(task) {
  const listId = encodeURIComponent(task.task_list_id || cfg().taskListId || '@default');
  const taskId = encodeURIComponent(task.task_id);
  return apiFetch(
    `https://tasks.googleapis.com/tasks/v1/lists/${listId}/tasks/${taskId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ status: 'completed' }),
    },
  );
}

async function patchEvent(event, startIso, endIso) {
  const calId = encodeURIComponent(event.calendar_id || cfg().kairosCalendarId);
  const eventId = encodeURIComponent(event.event_id);
  const tz = cfg().timeZone || 'Europe/Budapest';
  return apiFetch(
    `https://www.googleapis.com/calendar/v3/calendars/${calId}/events/${eventId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        start: { dateTime: startIso, timeZone: tz },
        end: { dateTime: endIso, timeZone: tz },
      }),
    },
  );
}

function findEvent(day, eventId) {
  const list = state.data?.calendar?.[day] || [];
  return list.find((e) => e.event_id === eventId);
}

function findTask(bucket, taskId) {
  const list = state.data?.tasks?.[bucket] || [];
  return list.find((t) => t.task_id === taskId);
}

function renderTimeline(el, events, dayKey) {
  if (!events?.length) {
    el.innerHTML = '<p class="event-loc">Nincs esemény.</p>';
    return;
  }
  el.innerHTML = events
    .map((e) => {
      const editable = e.editable !== false && e.event_id;
      const google = e.google_url
        ? `<a class="mini-link" href="${escapeHtml(e.google_url)}" target="_blank" rel="noopener">Google</a>`
        : '';
      const controls = editable
        ? `<div class="event-controls">
            <button type="button" class="chip" data-action="shift" data-day="${dayKey}" data-id="${escapeHtml(e.event_id)}" data-delta="-15" ${isAuthed() ? '' : 'disabled'} title="15 perccel korábbra">−15p</button>
            <button type="button" class="chip" data-action="shift" data-day="${dayKey}" data-id="${escapeHtml(e.event_id)}" data-delta="15" ${isAuthed() ? '' : 'disabled'} title="15 perccel későbbre">+15p</button>
            <input type="datetime-local" class="time-input" data-day="${dayKey}" data-id="${escapeHtml(e.event_id)}" value="${toLocalInputValue(e.start)}" ${isAuthed() ? '' : 'disabled'} />
            <button type="button" class="chip" data-action="set-time" data-day="${dayKey}" data-id="${escapeHtml(e.event_id)}" ${isAuthed() ? '' : 'disabled'}>Áthelyez</button>
            ${google}
          </div>`
        : `<div class="event-controls">${google}</div>`;
      return `
      <div class="event ${escapeHtml(e.type || '')}" data-event-id="${escapeHtml(e.event_id || '')}">
        <div class="event-time">${fmtRange(e.start, e.end)}</div>
        <div class="event-body">
          <div class="event-title">${escapeHtml(e.title)}</div>
          ${e.location ? `<div class="event-loc">${escapeHtml(e.location)}</div>` : ''}
          ${controls}
        </div>
      </div>`;
    })
    .join('');
}

/** All-day / egésznapos — no shift controls; Google link + source badge */
function renderAllDay(el, events) {
  const section = document.getElementById('section-all-day');
  const hint = document.getElementById('all-day-hint');
  if (!el) return;
  if (!events?.length) {
    if (section) section.hidden = true;
    el.innerHTML = '';
    return;
  }
  if (section) section.hidden = false;
  const tasks = events.filter((e) => e.kind === 'task').length;
  const cal = events.filter((e) => e.kind !== 'task').length;
  if (hint) {
    const parts = [];
    if (tasks) parts.push(`${tasks} task`);
    if (cal) parts.push(`${cal} naptár`);
    const raw = state.data?.stats?.all_day_raw_gluxshop;
    hint.textContent = parts.length
      ? `(${parts.join(' · ')}${raw ? ` · ${raw} nyers` : ''})`
      : '';
  }
  el.innerHTML = events
    .map((e) => {
      const google = e.google_url
        ? `<a class="mini-link" href="${escapeHtml(e.google_url)}" target="_blank" rel="noopener">Google</a>`
        : '';
      const source = e.source
        ? `<span class="source-tag">${escapeHtml(e.source)}</span>`
        : '';
      const kind = e.kind === 'task' ? '<span class="source-tag kind">task</span>' : '';
      return `
      <div class="event all-day ${escapeHtml(e.type || '')}" data-event-id="${escapeHtml(e.event_id || '')}">
        <div class="event-time">egész nap</div>
        <div class="event-body">
          <div class="event-title">${escapeHtml(e.title)} ${source} ${kind}</div>
          ${e.location ? `<div class="event-loc">${escapeHtml(e.location)}</div>` : ''}
          <div class="event-controls">${google}</div>
        </div>
      </div>`;
    })
    .join('');
}

function renderTasks(el, items, bucket) {
  if (!items?.length) {
    el.innerHTML = '<li>Nincs nyitott feladat.</li>';
    return;
  }
  el.innerHTML = items
    .map((t) => {
      const editable = t.editable !== false && t.task_id;
      const done = t._completed;
      const google = t.google_url
        ? `<a class="mini-link" href="${escapeHtml(t.google_url)}" target="_blank" rel="noopener">Google</a>`
        : '';
      const canCheck = editable && isAuthed() && !done;
      const checkbox = editable
        ? `<input type="checkbox" class="task-check" data-bucket="${bucket}" data-id="${escapeHtml(t.task_id)}" ${done ? 'checked' : ''} ${canCheck ? '' : 'disabled'} />`
        : `<span class="task-lock" title="Más fiók — csak Google link">↗</span>`;
      return `
      <li class="${done ? 'done' : ''}" data-task-id="${escapeHtml(t.task_id || '')}">
        <label class="task-main">
          ${checkbox}
          <span class="task-title">${escapeHtml(t.title)}</span>
        </label>
        <span class="task-meta">
          ${google}
          <span class="badge ${escapeHtml(t.priority || 'low')}">${escapeHtml(t.priority || '')}</span>
        </span>
      </li>`;
    })
    .join('');
}

function renderList(el, items, empty = '—') {
  if (!items?.length) {
    el.innerHTML = `<li>${empty}</li>`;
    return;
  }
  el.innerHTML = items
    .map((i) => {
      if (typeof i === 'string') return `<li>${escapeHtml(i)}</li>`;
      const range = i.start ? `${fmtRange(i.start, i.end)} — ${escapeHtml(i.label)}` : escapeHtml(i.label);
      return `<li>${range}</li>`;
    })
    .join('');
}

function renderAll() {
  const data = state.data;
  if (!data) return;
  document.getElementById('updated').textContent =
    `Frissítve: ${new Date(data.generated_at).toLocaleString('hu-HU')}`;
  renderAllDay(document.getElementById('timeline-all-day'), data.calendar?.all_day);
  renderTimeline(document.getElementById('timeline-today'), data.calendar?.today, 'today');
  renderTimeline(document.getElementById('timeline-tomorrow'), data.calendar?.tomorrow, 'tomorrow');
  const thuEl = document.getElementById('timeline-thursday');
  const thuSection = document.getElementById('section-thursday');
  if (thuEl) {
    const thu = data.calendar?.thursday || [];
    if (thuSection) thuSection.hidden = !thu.length;
    if (thu.length) renderTimeline(thuEl, thu, 'thursday');
  }
  renderList(document.getElementById('free-slots'), data.free_slots);
  renderList(document.getElementById('warnings'), data.warnings, 'Minden rendben.');
  renderTasks(document.getElementById('tasks-personal'), data.tasks?.personal, 'personal');
  renderTasks(document.getElementById('tasks-gluxshop'), data.tasks?.gluxshop, 'gluxshop');
  updateAuthUi();
}

async function syncCalendarGone(task) {
  const linked = findLinkedEventForTask(task);
  if (!linked?.event_id) return false;
  await deleteCalendarEvent(linked);
  removeEventFromState(linked.event_id);
  return true;
}

async function onCompleteTask(bucket, taskId, checkbox) {
  const task = findTask(bucket, taskId);
  if (!task) return;
  if (task.editable === false) {
    toast('Gluxshop task: más Google-fiók — nyisd meg Google-ben.', 'error');
    checkbox.checked = false;
    return;
  }
  const li = checkbox.closest('li');
  li?.classList.add('done');
  task._completed = true;
  try {
    await completeTask(task);
    let calNote = '';
    try {
      const removed = await syncCalendarGone(task);
      if (removed) calNote = ' + naptár törölve';
    } catch (calErr) {
      calNote = ` (naptár: ${calErr.message})`;
    }
    toast(`Kész — Tasks kipipálva${calNote}.`, 'ok');
    renderAll();
  } catch (err) {
    task._completed = false;
    li?.classList.remove('done');
    checkbox.checked = false;
    toast(`Nem sikerült: ${err.message}`, 'error');
  }
}

async function onDeleteTask(bucket, taskId) {
  const task = findTask(bucket, taskId);
  if (!task) return;
  if (task.editable === false) {
    toast('Gluxshop task: más Google-fiók — nyisd meg Google-ben.', 'error');
    return;
  }
  if (!window.confirm(`Törlöd?\n${task.title}\n\nGoogle Tasks + kapcsolódó Kairos naptáresemény.`)) {
    return;
  }
  task._deleted = true;
  renderAll();
  try {
    try {
      await deleteTaskApi(task);
    } catch (delErr) {
      // Fallback: complete if delete denied
      await completeTask(task);
    }
    let calNote = '';
    try {
      const removed = await syncCalendarGone(task);
      if (removed) calNote = ' + naptár';
    } catch (calErr) {
      calNote = ` (naptár hiba: ${calErr.message})`;
    }
    removeTaskFromState(bucket, taskId);
    renderAll();
    toast(`Törölve — Tasks${calNote}.`, 'ok');
  } catch (err) {
    task._deleted = false;
    renderAll();
    toast(`Törlés sikertelen: ${err.message}`, 'error');
  }
}

async function onShiftEvent(day, eventId, deltaMin) {
  const event = findEvent(day, eventId);
  if (!event?.event_id) return;
  const prevStart = event.start;
  const prevEnd = event.end;
  const nextStart = shiftIso(prevStart, deltaMin);
  const nextEnd = shiftIso(prevEnd, deltaMin);
  event.start = nextStart;
  event.end = nextEnd;
  renderAll();
  try {
    await patchEvent(event, nextStart, nextEnd);
    toast(`Áthelyezve ${deltaMin > 0 ? '+' : ''}${deltaMin} perc.`, 'ok');
  } catch (err) {
    event.start = prevStart;
    event.end = prevEnd;
    renderAll();
    toast(`Mozgatás sikertelen: ${err.message}`, 'error');
  }
}

async function onSetEventTime(day, eventId) {
  const event = findEvent(day, eventId);
  if (!event?.event_id) return;
  const input = document.querySelector(
    `input.time-input[data-day="${day}"][data-id="${CSS.escape(eventId)}"]`,
  );
  if (!input?.value) {
    toast('Válassz időpontot.', 'error');
    return;
  }
  const prevStart = event.start;
  const prevEnd = event.end;
  const dur = durationMs(prevStart, prevEnd) || 30 * 60 * 1000;
  const nextStart = fromLocalInputValue(input.value);
  const nextEnd = new Date(new Date(nextStart).getTime() + dur).toISOString();
  event.start = nextStart;
  event.end = nextEnd;
  renderAll();
  try {
    await patchEvent(event, nextStart, nextEnd);
    toast('Esemény áthelyezve.', 'ok');
  } catch (err) {
    event.start = prevStart;
    event.end = prevEnd;
    renderAll();
    toast(`Áthelyezés sikertelen: ${err.message}`, 'error');
  }
}

function bindUi() {
  document.getElementById('auth-btn')?.addEventListener('click', async () => {
    if (isAuthed()) {
      clearToken();
      if (window.google?.accounts?.oauth2 && state.token) {
        // already cleared
      }
      updateAuthUi();
      renderAll();
      toast('Kiléptél.');
      return;
    }
    try {
      await requestAuth('consent');
      renderAll();
    } catch (err) {
      toast(`Belépés sikertelen: ${err.message}`, 'error');
    }
  });

  document.body.addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.classList?.contains('task-check')) {
      onCompleteTask(t.dataset.bucket, t.dataset.id, t);
    }
  });

  document.body.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-action]');
    if (!btn) return;
    const { action, day, id, delta, bucket } = btn.dataset;
    if (action === 'shift') onShiftEvent(day, id, Number(delta));
    if (action === 'set-time') onSetEventTime(day, id);
    if (action === 'delete-task') onDeleteTask(bucket, id);
  });
}

async function load() {
  loadStoredToken();
  const res = await fetch('data/latest.json');
  state.data = await res.json();
  bindUi();
  renderAll();

  window.onGoogleLibraryLoad = () => {
    initGis();
  };
  // If GIS already present
  if (window.google?.accounts?.oauth2) initGis();
  else {
    // Poll briefly — script has async defer
    let n = 0;
    const iv = setInterval(() => {
      n += 1;
      if (window.google?.accounts?.oauth2) {
        clearInterval(iv);
        initGis();
      } else if (n > 40) clearInterval(iv);
    }, 100);
  }
}

load().catch((err) => {
  document.body.innerHTML = `<p style="padding:2rem;color:#ff6b6b">Nem sikerült betölteni az adatot: ${escapeHtml(err.message)}</p>`;
});
