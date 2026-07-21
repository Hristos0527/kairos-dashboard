# Kairos Dashboard — GitHub Pages

Statikus dashboard a naptár + teendők + javasolt időblokkok megjelenítéséhez.

## Publikus repo

Külön repo (csak dashboard fájlok): `/Users/hristos/Projects/kairos-dashboard`

**Várható Pages URL** (push + Pages enable után):

`https://hristos0527.github.io/kairos-dashboard/`

> 2026-07-21: a gépről `github.com` / `api.github.com` Connection refused + `gh` token invalid.
> Push előtt: hálózati unblock (firewall/Little Snitch) + `gh auth login -h github.com`.

### Push parancsok (ha auth + network OK)

```bash
cd /Users/hristos/Projects/kairos-dashboard
# sync latest from private workspace
cp /Users/hristos/Projects/hristos-private/kairos/dashboard/{index.html,style.css,app.js} .
cp /Users/hristos/Projects/hristos-private/kairos/dashboard/data/latest.json data/
gh repo create kairos-dashboard --public --source=. --remote=origin --push
gh api -X POST "repos/Hristos0527/kairos-dashboard/pages" \
  -f build_type=workflow \
  -F 'source[branch]=main' -F 'source[path]=/' 2>/dev/null || \
gh api -X PUT "repos/Hristos0527/kairos-dashboard/pages" \
  -F 'source[branch]=main' -F 'source[path]=/'
```

Alternatív Pages UI: Settings → Pages → Deploy from branch → `main` / `/ (root)`.

## Fájlok (publikus)

- `index.html` — főoldal
- `style.css`, `app.js` — megjelenés és adatbetöltés
- `data/latest.json` — utolsó sync adat (agent generálja)

**Ne pusholj:** secrets, MCP token, teljes privát emailek.

## Helyi előnézet

```bash
cd kairos/dashboard
python3 -m http.server 8080
# böngésző: http://localhost:8080
```

## Frissítés

Cursor chatben: **kairos sync** → másold a `data/latest.json`-t a publikus repóba → push.
