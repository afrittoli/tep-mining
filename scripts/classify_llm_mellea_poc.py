#!/usr/bin/env python3
# Copyright 2026 The Tekton Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Draft: what scripts/classify_llm.py's Ollama path looks like rewritten on mellea
(https://github.com/generative-computing/mellea), a library for typed/validated LLM calls.

Not wired into classify_llm.py or its CLI - a standalone comparison of two functions, to
evaluate before committing to broader adoption. See "Findings" at the bottom for what would
block adopting mellea for the rest of the script.

What this replaces, function-for-function
------------------------------------------
classify_llm.py today (hand-rolled):
  _build_result_schema()  - ~90 lines building a JSON-Schema dict by hand, with an inline
                             comment explaining *why* facet/value must be enums and not free
                             strings (a model ignoring the taxonomy still produces schema-
                             valid JSON full of invented names against a plain-string schema).
  _call_ollama()           - POSTs to /api/chat with format=schema, then json.loads()s the
                             response content by hand.
  _extract_results()       - ~70 lines of manual dict-shape validation: isinstance checks,
                             .get(...) with None-checks, try/except KeyError per field, a
                             WARNING print for every way the model's JSON can be malformed.

mellea replacement (this file):
  ClassificationBatch(BaseModel)  - the enum-narrowing trick becomes a Literal[*values] built
                                    from the taxonomy, same reasoning as the original comment,
                                    expressed as a type instead of a schema dict.
  classify_comments()              - an @generative-decorated function; mellea builds the JSON
                                    schema from the type hints, calls Ollama's structured-
                                    output mode, and parses+validates the response itself.
  classify_batch_mellea()          - the only "call it" code left; no manual json.loads, no
                                    isinstance/KeyError guards - a ValidationError from mellea
                                    replaces the whole WARNING-print-and-drop apparatus.

Verified against the real package (`pip install mellea`, v0.7.0) - the start_session(),
@generative and RejectionSamplingStrategy signatures cited here and in Findings were read off
installed source, not just documentation. mellea is deliberately not added to pyproject.toml
yet: this is an evaluation draft, and Findings #1/#2 should be settled before taking on the
dependency. Not run end-to-end against a live Ollama server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import mellea
from mellea import generative
from mellea.backends.model_options import ModelOption
from pydantic import BaseModel, Field
from ruamel.yaml import YAML

TAXONOMY_PATH = Path("conventions/seed-taxonomy.yaml")


def _load_taxonomy() -> dict:
    return YAML(typ="safe").load(TAXONOMY_PATH.read_text(encoding="utf-8"))


# --- typed replacement for _build_result_schema() -------------------------------------------
#
# Built once at import time, same as classify_llm.py builds TAXONOMY_PATH's contents once in
# main() and threads it through - but here the taxonomy has to be loaded *before* the
# @generative function below is defined, not per-call: mellea resolves a generative stub's
# return type from its annotation at decoration time, so the schema can't be assembled lazily
# inside classify_batch_mellea() the way _build_result_schema(taxonomy, facet_scope) is today.
# See Findings #3 for what this means for --facet-split/--task score's *per-call* schema shapes.

_taxonomy = _load_taxonomy()
_facet_names = list(_taxonomy["facets"].keys())
_all_values = sorted(
    {v["value"] for facet in _taxonomy["facets"].values() for v in (facet.get("values") or [])}
)

_Facet = Literal[tuple(_facet_names)]  # type: ignore[valid-type]
_Value = Literal[tuple(_all_values)]  # type: ignore[valid-type]


class Match(BaseModel):
    facet: _Facet
    value: _Value
    confidence: float
    evidence: str = Field(
        description="A quote or tight paraphrase of the specific words in THIS COMMENT that "
        "justify the match. Never the taxonomy value's own definition."
    )


class CommentResult(BaseModel):
    comment_id: int
    matches: list[Match]


class Candidate(BaseModel):
    comment_id: int
    fragment: str
    candidate_facet: str
    candidate_value: str
    candidate_description: str


class ClassificationBatch(BaseModel):
    results: list[CommentResult]
    candidates: list[Candidate]


# --- typed replacement for _call_ollama() + _extract_results() ------------------------------


@generative
def classify_comments(
    taxonomy_block: str, tep_body_block: str, comments_block: str
) -> ClassificationBatch:
    """Classify each PR review comment's facet/value matches against the taxonomy.

    taxonomy:
    {taxonomy_block}

    TEP body (may be empty):
    {tep_body_block}

    comments (JSON, one object per comment with comment_id/pr_number/author/body):
    {comments_block}

    For every comment, list each taxonomy (facet, value) it plausibly touches, with a
    confidence and evidence quoted from that specific comment. Also list any comment
    fragment that nothing in the taxonomy covers as a candidate, not a match.
    """
    ...


def classify_batch_mellea(
    taxonomy_block: str,
    tep_body_block: str | None,
    comments_block: str,
    model_id: str,
    ollama_host: str,
    num_ctx: int | None,
    temperature: float | None,
) -> ClassificationBatch:
    """One batch, one call - the direct counterpart to _classify_one_pass()'s first attempt,
    before its missing-comment_id retry loop (see Findings #2 for why that loop doesn't map
    onto mellea's retry model)."""
    model_options = {}
    if num_ctx:
        model_options[ModelOption.CONTEXT_WINDOW] = num_ctx
    if temperature is not None:
        model_options[ModelOption.TEMPERATURE] = temperature

    m = mellea.start_session(
        backend_name="ollama",
        model_id=model_id,
        base_url=ollama_host,
        model_options=model_options or None,
    )

    # No `requirements=`/`strategy=` here even though mellea supports both (see Findings #2) -
    # a requirement like "every input comment_id appears in the output" is exactly what
    # classify_llm.py's retry loop already checks, but mellea can only act on it by
    # regenerating the whole batch, not by re-asking for just the dropped ids.
    return classify_comments(
        m,
        taxonomy_block=taxonomy_block,
        tep_body_block=tep_body_block or "",
        comments_block=comments_block,
    )


# --- Findings --------------------------------------------------------------------------------
#
# 1. No claude-cli backend. mellea's backend_name is one of "ollama" | "hf" | "openai" |
#    "watsonx" | "litellm" (confirmed from mellea.start_session's real signature, not just
#    docs). classify_llm.py's --backend claude-cli shells out to `claude -p ...` specifically
#    to bill against a Claude Pro/Max subscription instead of the Anthropic API (see this
#    script's module docstring). litellm could reach Claude, but only via API billing - it
#    can't reproduce the CLI-subscription path, which is the entire reason that backend
#    exists. Adopting mellea for --backend claude-cli would mean writing a custom mellea
#    Backend subclass that still shells out to `claude -p`, at which point mellea is only
#    buying the typed-output layer on top, not the call itself.
#
# 2. Retry semantics don't match. classify_llm.py's _classify_one_pass() retries by re-asking
#    ONLY for the comment_ids the model dropped (a targeted, cheap follow-up call with a
#    smaller prompt). mellea's RejectionSamplingStrategy(loop_budget=N) - confirmed from the
#    installed package - regenerates the ENTIRE batch from scratch each time a requirement
#    fails. For the default --batch-size ("all of the TEP's comments in one call"), that turns
#    a cheap N-missing-ids retry into a full re-classification of every comment, at N times
#    the cost/time, every time even one comment_id gets dropped. This is a behavior change,
#    not a drop-in swap - worth a design decision (accept the cost? keep the manual retry loop
#    wrapped around a mellea call instead of using its built-in strategy?) before adopting
#    mellea for retry handling specifically.
#
# 3. Per-call schema shapes (--facet-split, --task score) are awkward under @generative.
#    _build_result_schema(taxonomy, facet_scope) and _build_score_schema(...) both build a
#    *different* schema per call - narrower enums for one facet, or minItems=maxItems=
#    len(values) for --task score's must-score-everything constraint. @generative wants one
#    fixed return type per decorated function, resolved at decoration time (see the taxonomy-
#    at-import-time comment above), so each distinct shape needs its own module-level type +
#    @generative function (e.g. classify_comments_for_facet(facet), score_comments()) rather
#    than the single schema-building function classify_llm.py has today. Doable, just a
#    different shape of code - more functions, less per-call parameterization.
#
# 4. --ollama-format json (unconstrained) and _use_system_user_split()'s per-model system/user
#    workaround have no documented mellea equivalent at this layer - worth checking mellea's
#    backend/session config for either before treating them as blockers rather than
#    currently-undiscovered options. --ollama-format json exists to test whether Ollama's
#    grammar-constrained decoding is itself the cause of granite4's degenerate --task score
#    output (see _call_ollama's docstring); losing that toggle would remove a live diagnostic.
#
# Net: the typed-output half of this file (collapsing _build_result_schema/_extract_results
# into pydantic models) is a clean, representative win. The call-and-retry half surfaces two
# real blockers (#1, #2) that affect any broader adoption, not just this one script - worth
# resolving before spending more time on a fuller port.
