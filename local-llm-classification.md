# Local LLM Classification Tooling

An experimentation/benchmarking harness for comparing local (Ollama) or scripted-API
classification of review comments against the agent-produced ground truth from the
Sub-Task 8 pipeline (`prompts/classify_review_comments.md`). It's a separate, side-by-side
comparison tool, not part of that documented pipeline or the `classify`/`integrate` workflow
described in the main [README.md](README.md#parallel-classification) — nothing here writes to
the shared `comment_classifications.jsonl`, `classification_cost_log.md`, or
`reports/explorer.html`.

## Scripts

- [`scripts/classify_llm.py`](scripts/classify_llm.py) — the classification driver (`ollama`,
  `mellea` or `claude-cli` backend). Full usage, every flag, and the design rationale are in its
  own module docstring — read that, or run `uv run scripts/classify_llm.py --help`. Why the
  `mellea` backend exists and what it replaces is in
  [mellea-adoption.md](mellea-adoption.md).
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
space the `classify`/`integrate` pipeline uses. The already-integrated TEPs used as comparison
baselines (currently 52, 118, 135) are the exception: their original agent-produced files are
committed under an `agent_` prefix — `agent_classify.jsonl`, `agent_audit.jsonl`,
`agent_cost.md`, `agent_explorer.html`, plus the per-TEP scripts that built them — so they sit
alongside `classify_llm.py`'s own output in the same directory without name collisions. Use them
as `--ground-truth` / `--include-audit` inputs.

## Committed run results

`classify_llm.py` output (`classify_llm_<backend>_<context>_<model>...jsonl`, plus its
`.candidates.jsonl` and `.meta.json`) is real benchmarking data worth keeping, not scratch, even
though it lands inside the gitignored `processed/tep*/` tree — it's force-added
(`git add -f`) deliberately, per run, rather than made blanket-trackable, so committing a TEP's
result is a conscious choice rather than something that happens by accident on the next `git add
-A`. When adding a new TEP's results, force-add just its `classify_llm_*` files the same way.

Each run's `.meta.json` records `interrupted: true` if it didn't finish (Ctrl-C, or an unhandled
error — both now leave the same marker; see the `except Exception` branch in `classify_llm.py`'s
`main()`) along with `num_batches_completed` out of `num_batches`, so a partial result is never
silently indistinguishable from a complete one. One committed result, TEP-84, predates that fix:
it crashed on a `ReadTimeout` with no `meta.json` at all, so that file was reconstructed by hand
from `logs/tep84_none.log` after the fact (`"reconstructed_from_log": true`, with an `"error"`
field) — the summary counts are accurate but the per-call timing detail couldn't be recovered.
Re-run `--tep 84` for a complete result.

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
