#!/bin/bash
# DIAGVOICE gate 2 (judged): codex ×2 on reflect_diagnostic_voice, stdin closed.
# Bars (pre-reg): c1+c3 pass BOTH samples AND total >=0.75 both. Run ONLY after
# gate 1 passes (both 4B models flat) and full pytest green with the compiler edit.
set -uo pipefail
cd /Users/stans/projects/dojo
export DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only"
for i in 1 2; do
  echo "=== DIAGVOICE GATE2 SAMPLE $i START $(date) ==="
  python -m pytest -m eval -q -k "reflect_diagnostic_voice" </dev/null 2>&1
  echo "=== DIAGVOICE GATE2 SAMPLE $i EXIT $? $(date) ==="
done
echo "DIAGVOICE-GATE2-ALL-DONE"
