# scripts/

Maintenance scripts, run from the repository root.

| File | Purpose |
|---|---|
| `rename_package.py` | Renames the kernel package (`src/aikit` → `src/<name>`) |

`rename_package.py` also rewrites imports, entry-point groups, the CLI command, `AIKIT_*` environment variables, the distribution name, and, if given, `app.name`. Copier runs it automatically after `copier copy`. To run it by hand:

```bash
python scripts/rename_package.py acme_ai --dist acme-ai --app-name acme-support
```

It skips itself, `.copier-answers.yml`, and cache or virtualenv folders. Reinstall the package afterwards (`uv pip install -e ".[dev]"`).
