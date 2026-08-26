# Local LLM Classification Tooling

An experimentation/benchmarking harness for comparing local (Ollama) or scripted-API
classification of review comments against the agent-produced ground truth from the
Sub-Task 8 pipeline (`prompts/classify_review_comments.md`). It's a separate, side-by-side
comparison tool, not part of that documented pipeline or the `classify`/`integrate` workflow
described in the main [README.md](README.md#parallel-classification) — nothing here writes to
the shared `comment_classifications.jsonl`, `classification_cost_log.md`, or
`reports/explorer.html`.

See [`taxonomy-and-pipeline-plan.md`](taxonomy-and-pipeline-plan.md) for the design rationale
behind the current taxonomy shape (`conventions/seed-taxonomy.yaml`'s `area`/`nature`/`principle`
facets) and the tiered pipeline described below.

## Pipeline

`classify_llm.py` has two pipeline modes, selected by `--pipeline` (default `tiered`):

- **`tiered`** (default): the 3-pass pipeline from the plan doc's Part 2. Pass 1 tags
  `area`+`nature` together on a fast model (default `granite4.2:8b`, `think: low`); Pass 2 tags
  `principle` on the same fast model, skipping any comment Pass 1 tagged `nature: none`; Pass 3
  re-processes, on a slower/thinking model (default `granite4.2:30b`, `think: high`), only the
  comments either pass flagged - a missing `area`/`nature` match, a low-confidence `principle`
  match (`--principle-confidence-threshold`), or the *quote-coverage heuristic*: each match now
  carries a `quote` (an exact/near-exact literal substring of the comment, alongside the existing
  paraphrased `evidence`), and `uncovered_fraction()` in `classify_llm.py` measures - in pure
  Python, no model call - what fraction of a comment's text falls outside the union of its
  matched quote spans; a comment that's confidently tagged but still has a lot of unaccounted-for
  text also escalates to Pass 3 (`--quote-coverage-threshold`). Pass 3 sees Pass 1/2's findings as
  context and its output replaces theirs for the comments it re-processes. Every batch comment
  (not just escalated ones) gets a row in a new `<tag>.flags.jsonl` output, for tuning the two
  thresholds against real data later - neither has been tuned yet, see the plan doc's Open
  Questions.
- **`legacy`**: the original single-call (or `--facet-split`, one call per facet, all three
  fully independent) behavior, kept available - not deleted, not the default - for a future
  cost comparison against the `claude-cli` backend specifically, where fewer/larger calls may be
  cheaper than under Ollama.

Every pass's model is CLI-configurable (`--model` for Pass 1/2, `--pass3-model` for Pass 3 -
never hardcoded), same for the Ollama `think` level (`--think`, `--pass3-think`).

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

- [`scripts/data/few_shot_examples.yaml`](scripts/data/few_shot_examples.yaml) — worked
  examples, included in the prompt only with `--few-shot`. Each example carries a per-facet
  view so it renders correctly combined, scoped to a single facet (`--pipeline legacy
  --facet-split`), or scoped to a group of facets (the tiered pipeline's Pass 1 `area`+`nature`,
  Pass 2 `principle`, Pass 3 all three); see `_few_shot_examples_block` in `classify_llm.py`.
  Every example match also carries a `quote` (an exact substring of that example's own comment
  text), matching the schema's required `quote` field.
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

**Caveat**: these `agent_*` ground-truth files predate the taxonomy revision in
`taxonomy-and-pipeline-plan.md` Part 1 — they still use the old facet name `artifact` (now
`area`) and the old `nature: structure` value (now `formatting`), and never emit `nature: none`
or `quote`. A raw `compare_classifications.py` run against a current-taxonomy candidate will
therefore show spurious `(comment_id, facet, value)` mismatches from the rename alone, on top of
any real quality difference — `compare_classifications.py`'s `val-P`/`val-R` columns (value-only,
ignoring facet) sidestep the `artifact`→`area` rename but not the `structure`→`formatting` one.
Re-running the `classify`/`integrate` pipeline against the revised taxonomy to produce fresh
ground truth is out of scope here; until then, read comparisons against these files as
directional, not literal.

## Committed run results

`classify_llm.py` output (`classify_llm_<backend>_<context>_<model>...jsonl`, plus its
`.candidates.jsonl`, `.meta.json`, and — `--pipeline tiered` runs only — `.flags.jsonl`, one row
per comment recording which escalation signal(s) fired) is real benchmarking data worth keeping,
not scratch, even though it lands inside the gitignored `processed/tep*/` tree — it's force-added
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
# tiered pipeline (default) - granite4.2:8b for Pass 1/2, granite4.2:30b for Pass 3
uv run scripts/classify_llm.py --tep 52 --backend ollama --context none

# legacy single-call pipeline, e.g. for a claude-cli cost comparison
uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
    --context none --pipeline legacy

uv run scripts/compare_classifications.py \
    --ground-truth processed/tep52/agent_classify.jsonl \
    --include-audit processed/tep52/agent_audit.jsonl \
    processed/tep52/classify_llm_ollama_none_granite4.2-8b_tiered_*.jsonl
```

For an unattended multi-TEP sweep against one model, use `scripts/classify_teps_local.sh`
directly rather than calling `classify_llm.py` in a loop by hand.
