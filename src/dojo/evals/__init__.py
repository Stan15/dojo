"""Model benchmarking (ADR 016): how well does a given (driver, judge) pair of
models run dojo's pedagogy?

The corpus ships with the package so any user can run `dojo benchmark` against
their own models. Three measurement tiers:

- Tier 1 (CI, no models): golden payload/template pins — lives in tests/.
- Tier 2 (compliance): does the driver produce contract-valid output the
  production submit path accepts?
- Tier 3 (quality): an evaluator model judges pedagogical strength against
  hand-crafted binary rubrics, guarded by a calibration gate (planted good/bad
  references) and verbatim-evidence verdict checks.

`runner.run_benchmark()` is the one orchestration both `dojo benchmark` and the
dev eval suites (`pytest -m eval`) build on.
"""
