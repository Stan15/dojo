# Dojo documentation

Dojo is a local-first learning app: you capture what you want to learn, it
builds byte-budgeted daily practice packets scheduled by FSRS spaced
repetition, and any AI model (or you, by hand) fulfills the generated tasks
through one validated door. Everything is stored as git-versioned markdown
you can read and edit directly.

## Where to start

| You want to… | Read |
|---|---|
| Install and run dojo | [Installation](installation.md) |
| Understand what dojo is for and why | [North star](product-north-star.md), [Pedagogy foundation](pedagogy-foundation.md) |
| Understand how the system is built | [Blueprint](design/blueprint.md) — the authoritative v1 design |
| See every user journey, end to end | [Use-case audit](design/usecase-audit.md) |
| Call dojo from code or the CLI | [API specification](api-specification.md), then the [API reference](reference/index.md) |
| Change or evaluate an AI prompt | [Prompt craft](design/prompts.md) |
| Know why a decision was made | [Decision records](adr/index.md) |

## How the docs fit together

- **Prose docs** (this section, Design, ADRs) are authored markdown in
  `docs/` — they explain intent, contracts, and trade-offs.
- The **[API reference](reference/index.md)** is generated from docstrings in
  `src/dojo/` at build time. A coverage gate in the test suite keeps every
  public module, class, and function documented, so the reference genuinely
  describes behavior rather than echoing signatures.
- The two are cross-searchable: the site search covers design rationale and
  code reference together.

## Building this site

```bash
pip install -e ".[docs]"
mise run docs-serve   # live-reload at http://127.0.0.1:8000
mise run docs         # static site in site/
```

The site builds with [ProperDocs](https://properdocs.org), the maintained
continuation of MkDocs 1.x, using the `mkdocs.yml` at the repo root.
