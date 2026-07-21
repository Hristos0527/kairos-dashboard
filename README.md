# Kairos Dashboard — GitHub Pages

Statikus dashboard + **live szerkesztés** (Google OAuth → Tasks kipipálás, naptár mozgatás).

**Pages URL:** https://hristos0527.github.io/kairos-dashboard/

## Mit tudsz csinálni

1. **Google belépés** (header gomb) — personal fiók: `hristos.lcdfix@gmail.com`
2. **Személyes taskek** — checkbox → Google Tasks `completed`
3. **Naptár** — eseményenként **−15p / +15p**, vagy időválasztó + **Áthelyez** → Calendar `events.patch`
4. **Gluxshop taskek** — más fiók (`info@gluxshop.eu`) → csak **Google** link (v1)

## Egyszeri OAuth setup (kötelező az első belépéshez)

A `config.js`-ben lévő Client ID Web kliens. A Google Cloud Console-ban add hozzá:

**APIs & Services → Credentials → OAuth 2.0 Client IDs**  
(projekt, ahol a client ID prefix: `889345739957-…`)

**Authorized JavaScript origins:**

- `https://hristos0527.github.io`
- `http://localhost:8080` (helyi teszt)

**APIs engedélyezve** legyen:

- Google Tasks API
- Google Calendar API

OAuth consent screen: tesztelőként add hozzá a personal Gmail címet, ha az app „Testing” módban van.

Saját Client ID: írd a `config.js` → `clientId` mezőbe, vagy `?client_id=....apps.googleusercontent.com`.

> A Client ID **nem secret**. Ne commitolj `client_secret`-et.

## Fájlok

| Fájl | Szerep |
|------|--------|
| `index.html` / `style.css` / `app.js` | UI + API hívások |
| `config.js` | Client ID, calendar ID, scope |
| `data/latest.json` | Snapshot (`event_id`, `task_id` mezőkkel) |

Forrás sync: `/Users/hristos/Projects/hristos-private/kairos/dashboard/`

## Helyi előnézet

```bash
cd /Users/hristos/Projects/kairos-dashboard
python3 -m http.server 8080
# http://localhost:8080
```

## Frissítés / push

```bash
cd /Users/hristos/Projects/kairos-dashboard
# sync from private if needed, then:
git add -A && git commit -m "…" && git push
```

Cursor: **kairos sync** → friss `data/latest.json` (ID-kkal) → push a publikus repóba.
