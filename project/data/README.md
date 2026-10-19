# project/data

Documents for `aikit ingest`. The loaders configured under `ingest:` in `profiles/base.yaml` read from here (`markdown` loader, `path: project/data`).

- Only `samples/` and this README are committed. Anything else you put here is git-ignored, so real company documents don't end up in the repo.
- `README.md` and `AGENTS.md` files are skipped by the loaders, so this file is never indexed.
- Markdown front matter becomes chunk metadata. Use `acl:` to restrict a document to groups:

  ```markdown
  ---
  title: Internal escalation guide
  acl: [support_leads]
  ---
  ```

  Documents without `acl` are visible to everyone. Documents with `acl` are only returned to callers whose `RunContext.groups` include one of the listed groups.

| Path | Contents |
|---|---|
| [`samples/`](samples/README.md) | Four Acme policy documents used by the example, the tests, and the eval datasets |

Re-run `aikit ingest` after changing documents. Unchanged chunks are skipped, and stale chunks are replaced.
