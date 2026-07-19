#!/bin/bash
# Sub-4B bake-off (owner directive 2026-07-20): every candidate runs the FULL
# current corpus under the SAME committed W1 tree, strictly sequentially (the
# local-GPU lane is serial). 0.8b re-runs because its 13/92 predates W1 —
# mixing arms would bias the class verdict against it.
set -u
cd "$(dirname "$0")/../.."
B=scratch/token-diet/baselines
run() { # slug, driver...
  local slug=$1; shift
  echo "=== BAKEOFF $slug start $(date +%H:%M:%S) ==="
  python scratch/token-diet/measure.py "$*" "$B/bakeoff_${slug}.jsonl" 2
  echo "=== BAKEOFF $slug done $(date +%H:%M:%S) ==="
}
run qwen35_08b_w1      "python scratch/token-diet/api_driver.py qwen3.5:0.8b --no-think"
run gemma3_1b_w1       "python scratch/token-diet/api_driver.py gemma3:1b"
run lfm25_12b_w1       "python scratch/token-diet/api_driver.py LiquidAI/lfm2.5-1.2b-instruct:latest"
run lfm25think_12b_w1  "python scratch/token-diet/api_driver.py lfm2.5-thinking:1.2b"
run granite4_1b_w1     "python scratch/token-diet/api_driver.py granite4:1b"
run qwen35_2b_w1       "python scratch/token-diet/api_driver.py qwen3.5:2b --no-think"
echo "BAKEOFF COMPLETE"
