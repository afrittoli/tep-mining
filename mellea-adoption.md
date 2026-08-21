# mellea in `classify_llm.py`

[mellea](https://github.com/generative-computing/mellea) is an open-source library, started by
IBM Research and now growing a wider community, for writing LLM calls as typed, validated Python
instead of hand-assembled JSON schemas and hand-parsed responses. `classify_llm.py` uses it
behind two backends: `--backend mellea` (Ollama, mellea's own backend) and `--backend
mellea-claude-cli` (Claude via `claude -p`, a custom backend built for this project — mellea
ships no Claude backend that can use a Pro/Max subscription's included usage). Both sit alongside
the original `--backend ollama` and `--backend claude-cli`.

Each mellea backend is a **directly comparable partner** to one hand-rolled backend, not a
replacement for it: `mellea` vs `ollama`, `mellea-claude-cli` vs `claude-cli`. Same taxonomy,
same Jinja prompts, same batching and retry loop — the only thing that changes is who builds the
response schema and who parses the answer. That framing matters for what follows: a disagreement
between a pair is a finding about schema-constrained decoding, not about the taxonomy or the
model's actual judgment.

## Why

`classify_llm.py` asks a model for a fixed JSON shape and then has to defend itself against
everything the model might return instead. Before mellea that defence was written by hand, in
three places:

- **`_build_result_schema()` / `_build_score_schema()`** — ~130 lines assembling JSON Schema as
  nested dicts. The important part isn't the boilerplate, it's that `facet` and `value` must be
  *enums of the live taxonomy*: against a plain-string schema, a model that ignores the given
  vocabulary still returns schema-valid JSON, just full of invented facet and value names with no
  signal in them. That constraint has to be rebuilt from `seed-taxonomy.yaml` on every call, and
  narrowed further under `--facet-split`.
- **`_call_ollama()`** — POSTs to `/api/chat`, then `json.loads()` on the response text, with a
  `SystemExit` for the case where the model didn't return JSON at all.
- **`_extract_results()` / `_extract_score_results()`** — `isinstance` checks, `.get()` with
  `None` guards, and `try/except (KeyError, TypeError)` per field, each with a `WARNING` print and
  a drop, because under `--ollama-format json` any field in the response might be missing,
  misnamed, or the wrong type.

None of that is domain logic. It's the cost of treating the model's output as untrusted JSON.
mellea's premise is that a pydantic model carries that contract instead: the schema is derived
from the type, the response is decoded and validated against it, and the code downstream gets a
typed object or an exception — never a half-valid dict to pick through.

The second reason is comparability. This project already runs the same TEP through multiple
models and backends to see how results differ; a mellea backend that's a direct, prompt-for-
prompt partner to its hand-rolled equivalent extends that same comparison to a new axis — how
much a result depends on the model itself versus the schema-constrained decoding path around it.
That's a useful distinction to be able to draw for any model this project evaluates, not just one
— see [Verified so far](#verified-so-far) for a real result from doing exactly that.

## Design

```
classify_llm.py main()
  ├─ --backend ollama            → _call_ollama()          (hand-rolled schema + JSON parsing)
  ├─ --backend claude-cli        → _call_claude_cli()       (hand-rolled schema + JSON parsing)
  ├─ --backend mellea            → _call_mellea()  ─┬─ MelleaSession(OllamaModelBackend)
  └─ --backend mellea-claude-cli → _call_mellea()  ─┘  or  MelleaSession(ClaudeCLIBackend)
```

`_call_mellea()` is backend-agnostic — it takes whichever `MelleaSession` `main()` built and
calls `session.instruct(user_prompt, format=<pydantic model>, strategy=None, model_options=...)`.
`main()` decides which session to build:

```python
if args.backend == "mellea":
    mellea_session = mellea.start_session(backend_name="ollama", model_id=model, base_url=args.ollama_host)
elif args.backend == "mellea-claude-cli":
    mellea_session = MelleaSession(ClaudeCLIBackend(model=model, max_budget_usd=args.max_budget_usd))
```

`start_session()`'s `backend_name` is a closed literal (`ollama`/`hf`/`openai`/`watsonx`/
`litellm`) with no Claude-CLI option — `litellm` can reach Claude, but only through Anthropic API
billing, not a Pro/Max subscription. `MelleaSession(backend: Backend, ...)` itself, though, takes
any `Backend` instance directly; `start_session()` is just a convenience wrapper around exactly
that constructor call. So `scripts/lib/mellea_claude_cli_backend.py`'s `ClaudeCLIBackend` is a plain
`mellea.core.Backend` subclass, built the same way mellea builds its own backends, that shells out
to `claude -p` — this is a first-class, intended extension point, not a workaround.

`_build_result_model()`/`_build_score_model()` are the pydantic counterparts of
`_build_result_schema()`/`_build_score_schema()`, used by both mellea backends identically (the
schema layer doesn't know or care which backend is underneath). The taxonomy enum-narrowing
survives as `Literal[tuple(values)]` built at call time — same constraint, different expression:

| | hand-rolled | mellea |
|---|---|---|
| schema | ~130 lines of nested dicts | pydantic classes |
| enum narrowing | `{"enum": [...]}` | `Literal[tuple(values)]` |
| decode | `json.loads()` + `SystemExit` | mellea, before return |
| shape validation | `isinstance`/`KeyError` guards | pydantic, cannot be skipped |

Checked, not assumed: for every facet scope, both schema styles produce the same facet/value
enums, the same 38-value count, the same `min`/`max` bounds on `--task score`'s array, and the
`reasoning`-before-`matches` field order under `--facet-split` (property order is generation
order under schema-constrained decoding, so this is load-bearing, not cosmetic — pydantic
preserves declaration order, so it holds). One real difference survived that check: under
`--facet-split`, the hand-built schema emits `{"enum": ["principle"]}` for a single-value facet
where pydantic emits `{"const": "principle"}` — semantically equivalent JSON Schema, but a
different input to a grammar-constrained decoder, and a candidate explanation if the two backends
ever diverge specifically in that mode.

### `ClaudeCLIBackend`: what it took to build

mellea's `Backend` abc requires two async methods, `_generate_from_context` (one action) and
`_generate_from_raw` (context-free batch). `claude -p --output-format json` is a single blocking
call, not a token stream, so there's no need for the lazy/streaming resolution machinery
`OllamaModelBackend` builds for Ollama's actually-streaming chat endpoint — just run the
subprocess (`asyncio.create_subprocess_exec`, not blocking `subprocess.run`, since these are
async methods), parse the envelope, and return an already-resolved value.

One real bug surfaced building this, worth recording because it invalidated the obvious reference
point: `mellea.backends.dummy.DummyBackend` — mellea's own minimal "smoke test" backend — looks
like the simplest possible pattern (`ModelOutputThunk(value=...)`, done). It's incomplete.
`mellea.stdlib.functional.aact` asserts `result._generate_log is not None` after resolving a
thunk; every real backend (`ollama.py`, `openai.py`, `litellm.py`, `watsonx.py`,
`huggingface.py`) explicitly builds a `GenerateLog` and assigns it to `mot._generate_log` before
returning, and `DummyBackend` doesn't. Following `DummyBackend`'s pattern produces a backend that
raises `AssertionError` the moment it's driven through `session.instruct()` rather than a bare
`backend.generate_from_context()` call — caught by actually running the backend end-to-end
against Claude, not by reading the reference implementation's docstring. `ClaudeCLIBackend`
builds and attaches a `GenerateLog` in both `_generate_from_context` and `_generate_from_raw`,
matching the real backends' pattern.

## What is used, and why

- **`instruct(..., format=<pydantic model>)`** — the core of it, described above.
- **`ModelOption.SYSTEM_PROMPT`** — `_use_system_user_split()` exists because `granite4:small-h`
  collapsed to near-total tagging failure when everything was crammed into one user turn; its
  chat template is built around a real system/user distinction. On both mellea backends the
  system prompt is passed as `ModelOption.SYSTEM_PROMPT`, producing an actual
  `{"role": "system"}` message (or, for `ClaudeCLIBackend`, `--system-prompt`), so that
  workaround applies unchanged regardless of which mellea backend is in use.
- **`ModelOption.CONTEXT_WINDOW`/`ModelOption.TEMPERATURE`** — backend-neutral names for
  `--num-ctx`/`--temperature`, so the call site names the concept rather than one server's
  spelling of it. `ClaudeCLIBackend` doesn't read either (no `claude -p` equivalent exists, same
  limitation `--backend claude-cli` already has) — harmless if set, silently ignored, same as
  `--temperature` already is for `--backend claude-cli`.
- **One session per run** — built once in `main()`, reused across batches, not recreated per call.

## What is deliberately not used

- **`RejectionSamplingStrategy`** (mellea's default retry-on-failed-requirement strategy) —
  `_call_mellea()` passes `strategy=None`. mellea's model is: attach `requirements`, regenerate
  the whole call on failure. `classify_llm.py` already retries, but *narrowly* —
  `_classify_one_pass()` re-asks only for the comment_ids the model dropped, with a smaller
  prompt. At the default batch size (every comment of a TEP in one call), one dropped id out of
  sixty would mean re-classifying all sixty under `RejectionSamplingStrategy`, at N× the cost and
  latency. The existing targeted loop stays in charge; this is the one place mellea's shape and
  this pipeline's needs genuinely diverge, worth revisiting if mellea grows a partial-repair
  strategy.
- **`@generative`** — mellea's headline feature builds the prompt from a Python function's
  signature, docstring, and type hints. Adopting it here would mean the prompt is no longer the
  Jinja templates in `scripts/templates/`, which breaks the entire comparability premise this
  adoption is built on — a disagreement between `mellea` and `ollama` is only interpretable if the
  prompt text is the one thing that's guaranteed identical. `instruct()` takes the rendered prompt
  as-is and keeps that guarantee.

## Verified so far

Structural equivalence (schema/enum/field-order checks above) was verified without a live model.
Everything below was actually run, on this machine, against real Ollama and real Claude — not
assumed from the structural checks:

- **`--backend mellea`**, `qwen2.5:32b-instruct`, `--task score`, TEP-52 comments `605675529`/
  `605677533`/`581412143`: produced the correct 114 rows (3 comments × 38 taxonomy values), real
  content, no errors.
- **`--backend mellea-claude-cli`**, `sonnet`, same comments/task: produced the correct 114 rows
  through the full `classify_llm.py` pipeline (not just the standalone backend), with confident,
  content-differentiated scores — e.g. comment `605675529` (a reconciler dueling-deletes comment)
  scored `nature/content 0.90, artifact/code 0.80, artifact/reconciler-pattern 0.70`, comparable
  in shape to an earlier direct-Claude test on the same comment.
- **`mellea` vs `ollama` head-to-head**, same model (`qwen2.5:32b-instruct`), same comments: real,
  non-trivial divergence, not just theoretical risk from the `const`-vs-`enum` note above. Both
  backends agree on the top *value* for all three comments (`nature/content`), but mellea scores
  it consistently higher (0.90 vs 0.60–0.80) and picks different secondary values — e.g. on
  `605675529`, `ollama` puts `tests` second (0.60) where `mellea` puts `code` second (0.80).
  Three comments is not enough to say which is "right," but it confirms the comparison is
  actually sensitive to something real, not just a paper hypothesis.

## Known gaps

- **`--ollama-format json` has no mellea equivalent.** mellea always uses its own
  schema-constrained path; that diagnostic (testing whether grammar-constrained decoding itself
  degrades a model's output — see `_call_ollama`'s docstring) stays on `--backend ollama`.
- **Cost tracking isn't wired up for `mellea-claude-cli`.** `_call_mellea()`'s meta dict doesn't
  capture `claude -p`'s `total_cost_usd` the way `_call_claude_cli()` does, so
  `meta.json`'s `total_cost_usd` stays `None` for this backend rather than reporting a
  misleadingly-precise `$0.00`. `--max-budget-usd` still caps each individual call.
  `ClaudeCLIBackend._run_claude_cli` already reads the full envelope; wiring the cost through
  `GenerateLog.extra` into `_call_mellea`'s meta dict is the natural next step if this backend
  sees real use.
- **Dependency cost.** mellea pulls a substantial transitive tree (see `uv add mellea`'s output).
  Worth weighing if the typed path doesn't earn its place in the comparison over time.

## What data needs to be rebuilt, and how

**Nothing existing is stale or wrong.** The agent-produced ground truth
(`processed/tepNN/agent_classify.jsonl`, `agent_audit.jsonl`) comes from a completely separate
pipeline (`prompts/classify_review_comments.md`, a real agent session) and has no dependency on
this script at all. The existing `classify_llm_*.jsonl` comparison artifacts (the qwen2.5
overnight sweep, and the various other model-comparison runs already on disk) remain valid
records of exactly what they say on their filename tag: a specific backend/model/config run at a
specific time. Adding two new backends doesn't invalidate any of that — it adds more comparison
points, it doesn't retroactively change what already ran.

**What's actually missing** is coverage: the `mellea`/`mellea-claude-cli` backends have only been
run on 3 comments each, as a correctness/plumbing check, not as a real classification pass. Two
concrete next steps, in order of what the empirical divergence above makes most worth doing:

1. **Full-TEP `mellea` vs `ollama` comparison**, same model, same TEP, to see whether the
   confidence-inflation pattern found on 3 comments holds at scale:
   ```bash
   uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct --context none
   uv run scripts/classify_llm.py --tep 52 --backend mellea --model qwen2.5:32b-instruct --context none
   uv run scripts/compare_classifications.py \
       --ground-truth processed/tep52/agent_classify.jsonl \
       --include-audit processed/tep52/agent_audit.jsonl \
       processed/tep52/classify_llm_ollama_none_qwen2.5-32b-instruct.jsonl \
       processed/tep52/classify_llm_mellea_none_qwen2.5-32b-instruct.jsonl
   ```
2. **`granite4:small-h` through `mellea`**, since it's a model this project has already spent
   real effort tuning prompts for, and it hasn't been run through either mellea backend yet:
   ```bash
   uv run scripts/classify_llm.py --tep 52 --backend mellea --model granite4:small-h --context none --num-ctx 8192
   ```
   Compare against the existing `--backend ollama --model granite4:small-h` runs already on disk
   for TEP-52/TEP-76/TEP-84 from the earlier tuning sessions.

Only after that comparison would there be a reason to *prefer* a mellea backend for real
classification runs over the hand-rolled ones — and if that happens, it's an explicit decision to
make per-TEP by re-running `classify_llm.py` with the new `--backend`, not a migration script or
a one-time conversion of existing output files. Output files are tagged with the backend
(`classify_llm_{backend}_...`), so old and new runs sit side by side without colliding or needing
cleanup.
