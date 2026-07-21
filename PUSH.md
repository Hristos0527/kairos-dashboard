# Push checklist (user)

1. Unblock github.com (Little Snitch / firewall) — currently Connection refused on :443
2. Re-auth: `gh auth login -h github.com -p https -w`
3. Create + push:

```bash
cd /Users/hristos/Projects/kairos-dashboard
gh repo create kairos-dashboard --public --source=. --remote=origin --push
gh api -X POST repos/Hristos0527/kairos-dashboard/pages -f build_type=legacy -F source[branch]=main -F source[path]=/
```

Expected URL: https://hristos0527.github.io/kairos-dashboard/
