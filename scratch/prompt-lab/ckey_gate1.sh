#!/bin/bash
# CKEY gate 1 (local shape): reflect minis both 4B models, chained serial.
# Measures the CKEY overlay (reflect_field_rules_default.md id/key contrast).
# Baselines this run: qwen ~13-18/30, gemma ~25-26/30 (band +-3); PRIMARY
# metric = create-op-composition fails DROP + reflect ok same-or-better, no
# new class, qwen NOT regressed. Requires ollama NUM_PARALLEL=4 for workers=2.
set -uo pipefail
cd /Users/stans/projects/dojo
FILTERS="atrophy_reentry chain_reflect_then chain_strategy_change implicit_ease inferred_restructure learning_loop_chain legitimate_restructure mastery_resolution no_retirement overconfident_fast plateau_remediation premature_resolution reflect_ resolution_amid resolution_despite restructure_minimal retire_on_learner too_easy_calibration too_hard_scaffolding"
echo "=== CKEY gate1 QWEN start $(date) ==="
python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py qwen3.5:4b --no-think" scratch/token-diet/baselines/ckey_qwen_reflect.jsonl 2 $FILTERS
echo "=== CKEY gate1 QWEN done $(date) ==="
echo "=== CKEY gate1 GEMMA start $(date) ==="
python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/ckey_gemma_reflect.jsonl 2 $FILTERS
echo "=== CKEY gate1 GEMMA done $(date) ==="
echo "CKEY-GATE1-ALL-DONE"
