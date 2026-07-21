# Push checklist

Lokális commit kész: interaktív OAuth kipipálás + naptár mozgatás.

Ha `github.com:443` Connection refused (Little Snitch / firewall):

1. Engedélyezd a kimenő 443-at github.com / api.github.com felé
2. `gh auth login -h github.com -p https -w` (ha token invalid)
3. Push:

```bash
cd /Users/hristos/Projects/kairos-dashboard
TOKEN=$(gh auth token)
git -c credential.helper= \
  -c http.extraHeader="Authorization: Bearer $TOKEN" \
  push -u origin main
```

Pages: Settings → Pages → Deploy from branch → `main` / `/ (root)`  
URL: https://hristos0527.github.io/kairos-dashboard/
