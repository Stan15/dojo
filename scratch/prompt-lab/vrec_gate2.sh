#!/bin/bash
# VERB-RECALL gate 2: judged x2 on verbatim_poetry_recall (codex, stdin closed).
# Each sample logged separately; report jsonls land in evals/reports/.
set -uo pipefail
cd /Users/stans/projects/dojo
export DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only"
for i in 1 2; do
  echo "=== VREC GATE2 SAMPLE $i START $(date) ==="
  python -m pytest -m eval -q -k "verbatim_poetry_recall" </dev/null 2>&1
  echo "=== VREC GATE2 SAMPLE $i EXIT $? $(date) ==="
done
echo "VREC-GATE2-ALL-DONE"
