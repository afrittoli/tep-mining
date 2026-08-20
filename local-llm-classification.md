# Local LLM Classification Tooling

An experimentation/benchmarking harness for comparing local (Ollama) or scripted-API
classification of review comments against the agent-produced ground truth from the
Sub-Task 8 pipeline (`prompts/classify_review_comments.md`). It's a separate, side-by-side
comparison tool, not part of that documented pipeline or the `classify`/`integrate` workflow
described in the main [README.md](README.md#parallel-classification) — nothing here writes to
the shared `comment_classifications.jsonl`, `classification_cost_log.md`, or
`reports/explorer.html`.

## Scripts

- [`scripts/classify_llm.py`](scripts/classify_llm.py) — the classification driver (Ollama or
  `claude-cli` backend). Full usage, every flag, and the design rationale are in its own module
  docstring — read that, or run `uv run scripts/classify_llm.py --help`.
- [`scripts/compare_classifications.py`](scripts/compare_classifications.py) — scores a
  candidate output file against a ground-truth file. Same story: see its module docstring or
  `--help`.
- [`scripts/classify_teps_local.sh`](scripts/classify_teps_local.sh) — loops
  `classify_llm.py` over a fixed TEP list against one Ollama model, unattended, with a cooldown
  between runs. Edit the `teps`/`model`/`context` variables at the top of the script to change
  scope. Writes one log per TEP to `logs/` (gitignored, local only).

## Supporting inputs

- [`scripts/data/few_shot_examples.md`](scripts/data/few_shot_examples.md) — worked examples,
  included in the prompt only with `--few-shot`.
- [`scripts/templates/`](scripts/templates/) — the Jinja2 system/user prompt templates
  `classify_llm.py` renders.

## Ground truth

`processed/tep*/` is gitignored on `main` (see `.gitignore`) — it's the same per-TEP scratch
space the `classify`/`integrate` pipeline uses, so `classify_llm.py` output
(`classify_llm_<backend>_<context>_<model>...jsonl`) stays local-only there by default, same as
any other TEP's scratch files.

The already-integrated TEPs used as comparison baselines (currently 52, 118, 135) are the
exception: their original agent-produced files are committed under an `agent_` prefix —
`agent_classify.jsonl`, `agent_audit.jsonl`, `agent_cost.md`, `agent_explorer.html`, plus the
per-TEP scripts that built them — so they sit alongside `classify_llm.py`'s own (gitignored)
output in the same directory without name collisions. Use them as `--ground-truth` /
`--include-audit` inputs.

## Example

```bash
uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
    --context none

uv run scripts/compare_classifications.py \
    --ground-truth processed/tep52/agent_classify.jsonl \
    --include-audit processed/tep52/agent_audit.jsonl \
    processed/tep52/classify_llm_ollama_none_qwen2.5-32b-instruct.jsonl
```

For an unattended multi-TEP sweep against one model, use `scripts/classify_teps_local.sh`
directly rather than calling `classify_llm.py` in a loop by hand.
