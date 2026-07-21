# Kairos Dashboard

Személyi asszisztens naptár + teendők dashboard (statikus).

## Live

_GitHub Pages URL pending — push után:_

`https://hristos0527.github.io/kairos-dashboard/`

## Fájlok

- `index.html`, `style.css`, `app.js`
- `data/latest.json` — utolsó sync (Cursor „kairos sync”)

## Helyi

```bash
python3 -m http.server 8080
```

## Frissítés

Másold át a `hristos-private/kairos/dashboard/` publikus fájljait ide, majd:

```bash
git add -A && git commit -m "Update dashboard data" && git push
```

Nincs secret, nincs MCP token, nincs teljes email tartalom.
