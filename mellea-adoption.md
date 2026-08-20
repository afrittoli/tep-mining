# mellea in `classify_llm.py`

[mellea](https://github.com/generative-computing/mellea) is a library for writing LLM calls as
typed, validated Python instead of hand-assembled JSON schemas and hand-parsed responses.
`classify_llm.py` uses it behind `--backend mellea`, as a third path alongside `--backend ollama`
and `--backend claude-cli`.

This document covers why it was adopted, which parts of it are actually used, which are
deliberately not, and what it replaced. Flag-level usage stays in the script's own module
docstring and `--help`, per the convention in
[local-llm-classification.md](local-llm-classification.md).

## Why

`classify_llm.py` asks a model for a fixed JSON shape and then has to defend itself against
everything the model might return instead. Before mellea that defence was written by hand, in
three places:

- **`_build_result_schema()` / `_build_score_schema()`** — ~130 lines assembling JSON Schema as
  nested dicts. The important part isn't the boilerplate, it's that `facet` and `value` must be
  *enums of the live taxonomy*: against a plain-string schema, a model that ignores the given
  vocabulary still returns schema-valid JSON, just full of invented facet and value names with
  no signal in them. That constraint has to be rebuilt from `seed-taxonomy.yaml` on every call,
  and narrowed further under `--facet-split`.
- **`_call_ollama()`** — POSTs to `/api/chat`, then `json.loads()` on the response text, with a
  `SystemExit` for the case where the model didn't return JSON at all.
- **`_extract_results()` / `_extract_score_results()`** — ~150 lines of `isinstance` checks,
  `.get()` with `None` guards, and `try/except KeyError` per field, each with a `WARNING` print
  and a drop, because any field in the response might be missing, misnamed, or the wrong type.

None of that is domain logic. It's the cost of treating the model's output as untrusted JSON.
mellea's premise is that a pydantic model can carry that contract instead: the schema is derived
from the type, the response is decoded and validated against it, and the code downstream gets a
typed object or an exception — never a half-valid dict to pick through.

The second reason is comparability. The interesting open question in this harness is how much of
a weak result is the *model* and how much is the schema-constrained decoding path. Having two
backends that send identical prompts to the same Ollama server but differ only in who builds the
schema and who parses the response makes that question answerable by running both on one TEP.

## What is used, and why

### `instruct(..., format=<pydantic model>)` — typed structured output

The core of it. `_call_mellea()` passes the already-rendered prompt and a pydantic model; mellea
derives the JSON schema, sends it as Ollama's `format`, and validates the response before
returning.

`_build_result_model()` and `_build_score_model()` are the pydantic counterparts of the two
schema builders. The taxonomy enum-narrowing survives as `Literal[tuple(values)]` built at call
time, so the constraint is identical — only its expression changed:

| | hand-rolled | mellea |
|---|---|---|
| schema | ~130 lines of nested dicts | pydantic classes |
| enum narrowing | `{"enum": [...]}` | `Literal[tuple(values)]` |
| decode | `json.loads()` + `SystemExit` | mellea, before return |
| shape validation | ~150 lines of guards | pydantic, cannot be skipped |

The two paths were checked against each other rather than assumed equivalent: for every facet
scope, both produce the same facet and value enums, the same 38-value count, the same
`min`/`max` bounds on `--task score`'s array, and — the load-bearing one — the same
`reasoning`-before-`matches` field order under `--facet-split`. That ordering is not cosmetic:
under schema-constrained decoding, property order is generation order, so it forces the model to
write its analysis before committing to a match. Pydantic preserves declaration order, so it
holds.

Because mellea guarantees the response parses into the model, the defensive branches in
`_extract_results()` cannot trigger on this path. They stay for `--backend ollama`, which still
needs them — especially under `--ollama-format json`, where the model picks its own JSON shape.

### `ModelOption.*` — backend-neutral option names

`num_ctx` and `temperature` go through `ModelOption.CONTEXT_WINDOW` and
`ModelOption.TEMPERATURE` rather than Ollama's own option names. Small, but it means the call
site names the concept rather than one server's spelling of it.

### `ModelOption.SYSTEM_PROMPT` — a real system message

`_use_system_user_split()` exists because `granite4:small-h` collapsed to near-total tagging
failure when everything was crammed into one user turn; its chat template is built around a real
system/user distinction. On the mellea path the system prompt is passed as
`ModelOption.SYSTEM_PROMPT`, which produces an actual `{"role": "system"}` message, so that
workaround applies unchanged. Verified by inspecting the request that reaches the server.

### One session per run

`start_session()` pulls the model if it isn't already local, so it's created once in `main()` and
reused across batches rather than per call.

## What is deliberately not used

### `RejectionSamplingStrategy` — mellea's retry loop

`_call_mellea()` passes `strategy=None`, overriding mellea's default.

mellea's model is: attach `requirements` to a call, and on a failed requirement, regenerate. That
is a poor fit here. `classify_llm.py` already has a retry loop, and it retries *narrowly* — when
the model drops comment_ids from its results, `_classify_one_pass()` re-asks for exactly the
dropped ids with a smaller prompt. `RejectionSamplingStrategy` regenerates the **whole batch**.
At the default batch size — every comment of a TEP in one call — one dropped id out of sixty
would mean re-classifying all sixty, at N times the cost and latency.

The requirement is expressible ("every input comment_id appears in the output"); it's the repair
strategy that doesn't fit. So the existing targeted loop stays in charge and mellea's is off.
This is the one place where mellea's shape and this pipeline's needs genuinely diverge, and it's
worth revisiting if mellea ever grows a partial-repair strategy.

### The `@generative` decorator

mellea's headline feature builds the prompt from a Python function's name, signature, docstring
and type hints. It is a good fit for new code and a bad fit here, for one specific reason:
the prompt would no longer be the Jinja templates in `scripts/templates/`.

That would break the comparison the backend exists for. `--backend mellea` is only informative
against `--backend ollama` if the *only* difference is schema construction and response parsing;
if the prompt text also changed, a disagreement between them would be uninterpretable.
`instruct()` takes the rendered prompt as-is and keeps that guarantee. `@generative` remains the
right tool if this harness ever grows a call that isn't being compared against an existing one.

## Known differences and open items

- **`const` vs `enum` for single-value facets.** Under `--facet-split`, the hand-built schema
  emits `{"enum": ["principle"]}` where pydantic emits `{"const": "principle"}`. Semantically
  equivalent and both valid JSON Schema, but they are different inputs to a grammar-constrained
  decoder, so it's a candidate explanation if the two backends ever diverge in that mode.
- **Not yet run against a real model.** The backend was verified end to end against a stub
  Ollama server across `--task classify`, `--facet-split` and `--task score` — prompts, retry
  loop, JSONL output and `meta.json` all behave as before. That proves the plumbing, not that any
  given model classifies well through this path. A same-model, same-TEP run of `--backend ollama`
  against `--backend mellea` is the next step.
- **`--ollama-format json` has no mellea equivalent.** That flag exists to test whether
  grammar-constrained decoding is itself degrading output (see `_call_ollama`'s docstring);
  mellea always uses its own schema-constrained path, so the diagnostic stays on
  `--backend ollama`.
- **Dependency cost.** mellea pulls a substantial transitive tree. Worth weighing if the typed
  path doesn't earn its place in the comparison.

## Running the comparison

```bash
uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
    --context none
uv run scripts/classify_llm.py --tep 52 --backend mellea --model qwen2.5:32b-instruct \
    --context none

uv run scripts/compare_classifications.py \
    --ground-truth processed/tep52/agent_classify.jsonl \
    --include-audit processed/tep52/agent_audit.jsonl \
    processed/tep52/classify_llm_mellea_none_qwen2.5-32b-instruct.jsonl
```

Output files are tagged with the backend, so the two runs land side by side in the same
directory without colliding.
