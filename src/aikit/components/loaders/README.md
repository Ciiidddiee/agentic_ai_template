# components/loaders

Document loaders. They implement `Loader`: `load() -> list[Document]`. Each takes `path` (a file or directory), `glob`, and `metadata`, which is merged into every document (for example `acl: [hr]`).

| Type | File | Notes |
|---|---|---|
| `markdown` | `markdown.py` | YAML front matter (`title`, `acl`, `tags`, ...) becomes metadata |
| `text` | `text.py` | Plain text files |
| `pdf` | `pdf.py` | One document per page; needs the `loaders` extra (pypdf) |
| `docx` | `docx.py` | Word headings become Markdown headings; needs the `loaders` extra |

`_base.py` provides `find_files` and `make_document`. Document ids are stable hashes of the source path (plus the page, for PDFs).

The `markdown` and `text` loaders skip `README.md`, `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` by default (`exclude`), so folder docs and AI instruction files placed next to data never get indexed. Set `exclude: []` to load them.
