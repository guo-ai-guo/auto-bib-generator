# Auto Bibliography Generator

Generate a finished bibliography for a Word document from your **Zotero** library.
Upload a `.docx` that has in-text citations and/or footnotes but an empty
bibliography; the tool reads every citation, matches it against Zotero, adds the
references it can confidently identify, and flags the rest with Word comments.

Everything runs locally — your document never leaves your computer.

## How it works

1. **Upload & options** — pick the `.docx`, a citation style (APA, Chicago, …),
   and optionally a Zotero collection to search within.
2. **Review matches** — citations with exactly one confident match are
   auto-included; anything ambiguous you resolve by picking a candidate; no-match
   citations are flagged.
3. **Done** — download the new `.docx` with a `Bibliography` section appended and
   Word comments on every problem citation.

## Requirements

- Python 3.10+
- The **Zotero 7 desktop app** running (the tool reads its local API on
  `localhost:23119`). No API key, no cloud sync needed.
  - *No Zotero?* Export your library to CSL-JSON and upload it under the
    “Zotero not running?” option.

## Run

```bash
pip install -r requirements.txt
python run.py
```

Your browser opens at http://127.0.0.1:8000.

For full citation-style fidelity, add `.csl` files under `styles/` (see
`styles/README.md`) or `pip install citeproc-py-styles`. Without them the app
uses a built-in author-date fallback formatter.

## Architecture

```
frontend/         single-page UI (upload → review → download)
app/
  main.py         FastAPI: REST endpoints + static frontend
  zotero.py       local Zotero API client (CSL-JSON)
  docx_parser.py  body (python-docx) + footnotes/endnotes (raw OOXML)
  extractor.py    find/classify/parse citations
  shortforms.py   resolve ibid./supra/op. cit.
  matcher.py      score candidates -> confident / ambiguous / none
  renderer.py     citeproc-py + CSL (fallback formatter)
  docx_writer.py  append bibliography + Word comments
  pipeline.py     orchestration
  models.py       domain dataclasses
  store.py        in-memory job store
tests/            unit + integration tests
```

### Scope (v1)

Generates the bibliography and flags problems; it does **not** rewrite in-text
citations or renumber `2020a/2020b`. Author-date and footnote citations are
matchable; numbered `[1]` markers are detected but flagged (no author/year to
match on).

### Planned

- LaTeX input (`.tex`) alongside `.docx`.
- Typo detection / “did you mean” suggestions when there is no match.
