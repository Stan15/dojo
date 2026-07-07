# OPEN PROBLEMS

Every known gap, with evidence and a disposition. Dispositions: `fixed` /
`deferred(<reason>)` / `rejected(<reason>)` / `accepted-risk(<reason>)`.

| # | Problem | Evidence | Disposition |
|---|---------|----------|-------------|
| 1 | `pydantic` missing from `pyproject.toml` dependencies though imported everywhere | `pyproject.toml` deps = PyYAML, rich, fpdf2; `schemas.py` imports pydantic | fixed (da4ae17) |
| 2 | Duplicate ADR number 003 (`agent-delegated-scheduling` and `dynamic-jit-replenishment`) | `docs/adr/` listing | fixed (da4ae17, renamed 003b) |
| 3 | Version mismatch: README badge 1.0.0 vs pyproject 0.1.0 | both files | fixed (e3319bf) |
| 4 | `docs/api-specification.md` documents SQLite-era API (`db_path`, sqlite3 default) that no longer exists | file §1 vs `src/dojo/store/` | fixed (e3319bf: banner + init section; full rewrite lands with M1–M3 surfaces) |
| 5 | Domain entities leak storage paths: `Attempt.session` / `Attempt.exercise` are "root-relative paths" | `schemas.py:260-262` | open — M1 (Store protocol requires ID-based refs) |
| 6 | `DojoStore` facade duplicates every repository method (~150 lines of pass-through) | `store/__init__.py` | open — M1 collapses it |
| 7 | `api.py` is a 1,810-line monolith mixing ingestion, practice, reflection, planning | `api.py` | open — M2/M3 split into services |
| 8 | Store `list_*` methods read+parse every matching file even when only frontmatter is needed (index already holds frontmatter) | `store/campaigns.py` list methods call `get_*` per hit | open — M1 |
| 9 | Auto `git commit` per save is one commit per entity write — session-level noise, and `commit_git` swallows all errors silently | `store/engine.py:commit_git` | open — M1 (batch per CLI command; surface failures in doctor) |
| 10 | `build/`, `dist/`, `.egg-info`, `.pytest_cache` committed to repo | git ls-files | rejected(mis-diagnosed 2026-07-07: files exist on disk but were never tracked; original evidence was a `find` listing, not `git ls-files`. Gitignore already covers them) |
| 11 | Prototype `thinking` fields in LLM schemas invite unbounded generation from weak models | `schemas.py:61-63` | open — superseded by prompt redesign (design/prompts.md) in M2 |
| 12 | PDF export (`pdf_generator.py`, fpdf2 dep) is off the critical path for harness-first v1 | user vision: harness-first | deferred(backlog; da4ae17 moved fpdf2 behind `dojo[pdf]` extra with honest ImportError) |
| 13 | No conformance/round-trip test suite for the markdown store format despite it being a public contract | tests/test_dojo.py has 3 store tests, no round-trip property coverage | open — M1 |
