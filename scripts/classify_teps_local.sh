#!/bin/bash
mkdir -p logs
model="qwen2.5:32b-instruct"
context="none"

teps=(
    118 135
    6 72 136 148 149 153 162 163
    45 71
    132 14 105 161
    38 63 88 95
    36 120 152
    19 25 73
    52 29 26 9 109 84 114 75 142 76
)

for tep in "${teps[@]}"; do
    log="logs/tep${tep}_${context}.log"
    echo "=== TEP-${tep} (${context}) starting $(date) ===" | tee -a "$log"
    if uv run scripts/classify_llm.py --tep "$tep" --backend ollama --model "$model" \
        --context "$context" --batch-size 10 --facet-coverage-threshold 0.4 \
        --pipeline legacy \
        >> "$log" 2>&1; then
        echo "=== TEP-${tep} OK $(date) ===" | tee -a "$log"
    else
        echo "=== TEP-${tep} FAILED (exit $?) $(date) ===" | tee -a "$log"
    fi
    echo "cooling down 5 min..." | tee -a "$log"
    sleep 300
done

echo "Done. Failures:"
grep -l FAILED logs/*.log 2>/dev/null
