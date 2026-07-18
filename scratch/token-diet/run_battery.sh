#!/bin/zsh
# Token-diet measurement battery. Run from repo root on branch dev/token-diet.
# PRECONDITION: ollama server running with parallelism:
#   pkill -f "ollama serve"; OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=1 ollama serve &
# Usage: zsh scratch/token-diet/run_battery.sh <tag>
# <tag> names the output files (e.g. "base" for baseline, "armJ", "armJS").
# Comment out lines already collected for that tag.
set -x
W=scratch/token-diet
T=${1:?tag required, e.g. base or armJ}
python $W/measure.py "ollama run gemma3:1b" $W/baselines/${T}_gemma1b.jsonl 4
python $W/measure.py "ollama run LiquidAI/lfm2.5-1.2b-instruct:latest" $W/baselines/${T}_lfm.jsonl 4
python $W/measure.py "ollama run gemma3:4b" $W/baselines/${T}_gemma4b.jsonl 3
python $W/measure.py "ollama run qwen3:4b" $W/baselines/${T}_qwen4b.jsonl 3
echo ALL_BATTERIES_DONE
