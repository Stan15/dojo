#!/bin/bash
# DIAGVOICE gate 1 (local shape): reflect minis both 4B models, chained serial
# (ONE local GPU battery at a time). 30-scenario reflect set. Baselines
# (MAINT-era): qwen 18/30, gemma 25/30; flat = within +-3. Run ONLY after the
# compiler.py DIAGVOICE edit is in the working tree and full pytest is green.
set -uo pipefail
cd /Users/stans/projects/dojo
FILTERS="atrophy_reentry chain_reflect_then chain_strategy_change implicit_ease inferred_restructure learning_loop_chain legitimate_restructure mastery_resolution no_retirement overconfident_fast plateau_remediation premature_resolution reflect_ resolution_amid resolution_despite restructure_minimal retire_on_learner too_easy_calibration too_hard_scaffolding"
echo "=== DIAGVOICE gate1 QWEN start $(date) ==="
python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py qwen3.5:4b --no-think" scratch/token-diet/baselines/diagvoice_qwen_reflect.jsonl 2 $FILTERS
echo "=== DIAGVOICE gate1 QWEN done $(date) ==="
echo "=== DIAGVOICE gate1 GEMMA start $(date) ==="
python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/diagvoice_gemma_reflect.jsonl 2 $FILTERS
echo "=== DIAGVOICE gate1 GEMMA done $(date) ==="
echo "DIAGVOICE-GATE1-ALL-DONE"
