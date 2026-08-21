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
"""Classify one TEP's review comments via a scripted LLM call, not an agent session.

prompts/classify_review_comments.md is written for an autonomous coding agent - worktree
setup, validation, commit, human review - but only one part of that actually needs a model:
the per-comment classification judgment. This script isolates that one call behind a plain
batch pipeline, the same shape as scripts/synthesize.py or scripts/fetch_impl_prs.py (load
upstream JSON, call an external API, write a JSONL artifact), so a local model (Ollama) or a
scripted Claude call can be compared against the existing agent-produced classify.jsonl -
with or without extra context - without spinning up a full agent session.

The "claude-cli" backend runs `claude -p --output-format json --json-schema ...`, which uses
a Claude Pro/Max subscription's included usage rather than separate Anthropic API billing
(see --max-budget-usd for a per-run safety cap; --tools "" keeps it a pure text-in/JSON-out
call with no file/bash access, so it can't drift into the permission-prompt problems this
pipeline has hit before).

Also asks for the same "uncovered fragment" signal as the audit pass in
classify_review_comments.md (a `candidates` array alongside `results`) - a comment fragment
nothing in the taxonomy covers is a real, first-class outcome here too, not just something an
autonomous agent happens to notice.

Deliberately out of scope: worktree/git/commit mechanics, and treating candidates as anything
but a proposal - this produces a comparison artifact, not a real classify.jsonl to commit.

The "mellea" backend is a third path to the same Ollama server: identical rendered prompts and
identical retry loop, but the response schema is derived from pydantic models and the response
is decoded/validated by mellea rather than by this script's hand-rolled guards. It exists to be
compared against "ollama" on the same TEP - if the two disagree, that's a finding about
schema-constrained decoding, not about the taxonomy. It only ever covers the Ollama path;
--backend claude-cli keeps its own subprocess call, since driving Claude through a Pro/Max
subscription means going through the CLI.

Usage:
    uv run scripts/classify_llm.py --tep 52 --backend claude-cli --context none
    uv run scripts/classify_llm.py --tep 52 --backend claude-cli --context tep-body
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
        --context tep-body

    # same call through mellea, for a like-for-like comparison against --backend ollama:
    uv run scripts/classify_llm.py --tep 52 --backend mellea --model qwen2.5:32b-instruct \
        --context tep-body

    # split into smaller calls instead of one call for the whole TEP - test whether batch size
    # itself is suppressing recall (each batch retries independently for dropped comment_ids):
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
        --context none --batch-size 10

    # diagnostic: score every taxonomy value's relevance per comment instead of just selecting
    # matches, on a small slice of comments (batch-size 5, first batch only):
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model granite4:small-h \
        --context none --task score --batch-size 5 --max-batches 1
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Literal

import mellea
import requests
from jinja2 import Environment, FileSystemLoader
from lib.mellea_claude_cli_backend import ClaudeCLIBackend
from mellea.backends.model_options import ModelOption
from mellea.stdlib.session import MelleaSession
from pydantic import BaseModel, Field
from ruamel.yaml import YAML

TAXONOMY_PATH = Path("conventions/seed-taxonomy.yaml")
RECORDS_PATH = Path("processed/latest/per_tep_records.json")
FEW_SHOT_EXAMPLES_PATH = Path(__file__).parent / "data" / "few_shot_examples.md"
TEMPLATES_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True
)


def _facet_and_values(taxonomy: dict, facet_scope: str | None) -> tuple[list[str], list[str]]:
    """The (facet_names, all_values) pair every schema/model builder narrows its enums to -
    one facet's values under --facet-split, the whole taxonomy otherwise."""
    if facet_scope:
        return [facet_scope], sorted(
            v["value"] for v in taxonomy["facets"][facet_scope].get("values") or []
        )
    return list(taxonomy["facets"].keys()), sorted(
        {v["value"] for facet in taxonomy["facets"].values() for v in (facet.get("values") or [])}
    )


def _build_result_schema(taxonomy: dict, facet_scope: str | None = None) -> dict:
    """`facet`/`value` are enums of the actual taxonomy, not free strings - otherwise a model
    that ignores the given vocabulary still produces schema-valid JSON, just full of invented
    facet/value names with zero real signal (observed: one model invented a whole new facet,
    another used real values under invented facet names - both pass a plain-string schema).

    `facet_scope` narrows both enums to one facet (used in --facet-split mode) and adds a
    required `reasoning` field ordered *before* `matches` in the schema - with schema-
    constrained decoding, property order is generation order, so this forces the model to
    write its analysis before committing to a match rather than justifying one after the fact.
    """
    facet_names, all_values = _facet_and_values(taxonomy, facet_scope)

    result_item_properties: dict = {"comment_id": {"type": "integer"}}
    result_item_required = ["comment_id"]
    if facet_scope:
        result_item_properties["reasoning"] = {
            "type": "string",
            "description": "1-2 sentences on what the comment is about and whether it "
            "plausibly touches this facet - written before matches, to inform the choice.",
        }
        result_item_required.append("reasoning")
    result_item_properties["matches"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "facet": {"type": "string", "enum": facet_names},
                "value": {"type": "string", "enum": all_values},
                "confidence": {"type": "number"},
                "evidence": {
                    "type": "string",
                    "description": "A quote or tight paraphrase of the specific words in "
                    "THIS COMMENT that justify the match. Never the taxonomy value's own "
                    "definition, and never generic phrasing like 'this touches on X' - name "
                    "what the comment actually says.",
                },
            },
            "required": ["facet", "value", "confidence", "evidence"],
        },
    }
    result_item_required.append("matches")

    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": result_item_properties,
                    "required": result_item_required,
                },
            },
            "candidates": {
                "type": "array",
                "description": "Comment fragments nothing in the taxonomy covers - proposals, "
                "not tags. See audit_classification_coverage.md's 'uncovered fragment' case.",
                "items": {
                    "type": "object",
                    "properties": {
                        "comment_id": {"type": "integer"},
                        "fragment": {"type": "string"},
                        "candidate_facet": {"type": "string"},
                        "candidate_value": {"type": "string"},
                        "candidate_description": {"type": "string"},
                    },
                    "required": [
                        "comment_id",
                        "fragment",
                        "candidate_facet",
                        "candidate_value",
                        "candidate_description",
                    ],
                },
            },
        },
        "required": ["results", "candidates"],
    }


def _build_score_schema(taxonomy: dict, facet_scope: str | None = None) -> dict:
    """--task score's schema: instead of selecting matches, the model rates every taxonomy
    value's relevance to each comment on a 0.0-1.0 scale. Diagnostic tool for telling apart "the
    model ranks correctly but --facet-coverage-threshold (or its own judgment) draws the line in
    the wrong place" from "the model can't discriminate relevant from irrelevant values at all" -
    a distinction --task classify's top-picks-only output can't show.

    minItems/maxItems on `scores` both equal the total number of taxonomy values (or one facet's
    values, under --facet-split) so the model is structurally required to score every value, not
    just the ones it would normally tag - schema-constrained decoding enforces the count even if
    the prompt's wording doesn't land.
    """
    facet_names, all_values = _facet_and_values(taxonomy, facet_scope)
    total_values = len(all_values)

    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "comment_id": {"type": "integer"},
                        "scores": {
                            "type": "array",
                            "minItems": total_values,
                            "maxItems": total_values,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "facet": {"type": "string", "enum": facet_names},
                                    "value": {"type": "string", "enum": all_values},
                                    "score": {"type": "number"},
                                },
                                "required": ["facet", "value", "score"],
                            },
                        },
                    },
                    "required": ["comment_id", "scores"],
                },
            },
        },
        "required": ["results"],
    }


def _build_result_model(taxonomy: dict, facet_scope: str | None = None) -> type[BaseModel]:
    """--backend mellea's counterpart to _build_result_schema(): the same enum-narrowed shape,
    expressed as pydantic types instead of a hand-written JSON-Schema dict, because mellea's
    `format=` takes a model class and derives the schema itself.

    The reasons behind the shape are unchanged and still load-bearing - see
    _build_result_schema's docstring for why facet/value are enums rather than free strings,
    and why `reasoning` is declared *before* `matches` under --facet-split (declaration order
    is generation order under schema-constrained decoding).
    """
    facet_names, all_values = _facet_and_values(taxonomy, facet_scope)

    facet_t = Literal[tuple(facet_names)]  # type: ignore[valid-type]
    value_t = Literal[tuple(all_values)]  # type: ignore[valid-type]

    class Match(BaseModel):
        facet: facet_t
        value: value_t
        confidence: float
        evidence: str = Field(
            description="A quote or tight paraphrase of the specific words in THIS COMMENT "
            "that justify the match. Never the taxonomy value's own definition, and never "
            "generic phrasing like 'this touches on X' - name what the comment actually says."
        )

    if facet_scope:

        class CommentResult(BaseModel):
            comment_id: int
            reasoning: str = Field(
                description="1-2 sentences on what the comment is about and whether it "
                "plausibly touches this facet - written before matches, to inform the choice."
            )
            matches: list[Match]

    else:

        class CommentResult(BaseModel):  # type: ignore[no-redef]
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
        candidates: list[Candidate] = Field(
            description="Comment fragments nothing in the taxonomy covers - proposals, not "
            "tags. See audit_classification_coverage.md's 'uncovered fragment' case."
        )

    return ClassificationBatch


def _build_score_model(taxonomy: dict, facet_scope: str | None = None) -> type[BaseModel]:
    """--backend mellea's counterpart to _build_score_schema(). min_length/max_length both
    equal the taxonomy value count for the same reason the JSON-Schema version sets
    minItems/maxItems: the model must score every value, not just the ones it would tag."""
    facet_names, all_values = _facet_and_values(taxonomy, facet_scope)
    total_values = len(all_values)

    facet_t = Literal[tuple(facet_names)]  # type: ignore[valid-type]
    value_t = Literal[tuple(all_values)]  # type: ignore[valid-type]

    class Score(BaseModel):
        facet: facet_t
        value: value_t
        score: float

    class CommentScores(BaseModel):
        comment_id: int
        scores: list[Score] = Field(min_length=total_values, max_length=total_values)

    class ScoreBatch(BaseModel):
        results: list[CommentScores]

    return ScoreBatch


def _load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def _taxonomy_prompt_block(taxonomy: dict) -> str:
    """Facet/value/description text for the prompt - not the whole file; semantics/provenance/
    parent bookkeeping isn't needed to make a classification call."""
    lines: list[str] = []
    for facet_name, facet in taxonomy["facets"].items():
        lines.append(f"## {facet_name}: {facet['description'].strip()}")
        for v in facet.get("values") or []:
            lines.append(f"- {v['value']}: {v['description'].strip()}")
        lines.append("")
    return "\n".join(lines)


def _load_tep_record(tep_number: int, path: Path = RECORDS_PATH) -> dict:
    records = json.loads(path.read_text(encoding="utf-8"))
    for r in records:
        if r["tep_number"] == tep_number:
            return r
    raise SystemExit(f"TEP-{tep_number} not found in {path}")


def _comments_for(record: dict) -> list[dict]:
    """Flatten proposal + impl PR comments, same set classify_review_comments.md's agent reads."""
    out: list[dict] = []
    for c in record["proposal_pr"]["comments"]:
        out.append(
            {
                "comment_id": c["comment_id"],
                "repo": "community",
                "pr_number": c["pr_number"],
                "author": c.get("author"),
                "section": c.get("section"),
                "body": c["body"],
            }
        )
    for pr in record["impl_prs"]["items"]:
        for c in pr["comments"]:
            out.append(
                {
                    "comment_id": c["comment_id"],
                    "repo": pr["repo"],
                    "pr_number": pr["pr_number"],
                    "author": c.get("author"),
                    "path": c.get("path"),
                    "body": c["body"],
                }
            )
    return out


def _tep_body_block(record: dict, teps_dir: Path) -> str:
    source_file = record.get("source_file")
    if not source_file:
        raise SystemExit(f"TEP-{record['tep_number']} has no source_file - can't load its body")
    tep_path = teps_dir / source_file
    if not tep_path.is_file():
        raise SystemExit(f"TEP body not found at {tep_path} - check --teps-dir/COMMUNITY_REPO_PATH")
    return tep_path.read_text(encoding="utf-8")


def _load_few_shot_examples(path: Path = FEW_SHOT_EXAMPLES_PATH) -> str:
    return path.read_text(encoding="utf-8")


def _build_system_prompt(
    taxonomy: dict,
    taxonomy_block: str,
    tep_body_block: str | None,
    facet_coverage_threshold: float | None = None,
    examples_block: str | None = None,
    facet_scope: str | None = None,
    template_path: Path | None = None,
) -> str:
    """Renders templates/system_prompt.md.j2 (or `template_path`, for testing prompt-wording
    variants without editing the canonical template in place - must accept the same variables
    this function passes to render()) - everything that doesn't change per batch: task framing,
    taxonomy, optional TEP body, optional facet-coverage nudge, optional worked examples. Kept
    separate from the comments themselves (see _build_user_prompt) since some models (observed:
    granite4) are trained around a real system/user split and behave more generically when
    everything is crammed into one user turn.

    `facet_scope` narrows the prompt to describe one facet only, for --facet-split mode; see
    _build_result_schema for why that's paired with a required `reasoning` field."""
    facet_description = None
    facet_values = None
    if facet_scope:
        facet_description = taxonomy["facets"][facet_scope]["description"].strip()
        facet_values = [
            {"value": v["value"], "description": v["description"].strip()}
            for v in taxonomy["facets"][facet_scope].get("values") or []
        ]
    if template_path:
        template = Environment().from_string(template_path.read_text(encoding="utf-8"))
    else:
        template = _jinja_env.get_template("system_prompt.md.j2")
    return template.render(
        facet_scope=facet_scope,
        facet_description=facet_description,
        facet_values=facet_values,
        taxonomy_block=taxonomy_block,
        tep_body_block=tep_body_block,
        examples_block=examples_block,
        facet_coverage_threshold=facet_coverage_threshold,
    )


def _build_user_prompt(comments: list[dict]) -> str:
    """Renders templates/user_prompt.md.j2 - just the comment list, so it's cheap to rebuild
    per retry without re-rendering the (unchanging) system prompt."""
    template = _jinja_env.get_template("user_prompt.md.j2")
    rendered = [
        {
            "comment_id": c["comment_id"],
            "pr_number": c["pr_number"],
            "loc": c.get("section") or c.get("path") or "",
            "author": c.get("author") or "",
            "body": c["body"],
        }
        for c in comments
    ]
    return template.render(comments=rendered)


def _call_claude_cli(
    system_prompt: str | None, user_prompt: str, model: str, max_budget_usd: float, schema: dict
) -> tuple[dict, dict]:
    cmd = [
        "claude",
        "-p",
        user_prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        "--tools",
        "",
        "--no-session-persistence",
        "--model",
        model,
        "--max-budget-usd",
        str(max_budget_usd),
    ]
    if system_prompt is not None:
        cmd += ["--system-prompt", system_prompt]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"claude -p exited {proc.returncode}\nstderr: {proc.stderr}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise SystemExit(f"claude -p reported an error: {envelope}")
    meta = {
        "backend": "claude-cli",
        "model": model,
        "cost_usd": envelope.get("total_cost_usd"),
        "duration_ms": envelope.get("duration_ms"),
    }
    return envelope["structured_output"], meta


def _call_ollama(
    system_prompt: str | None,
    user_prompt: str,
    model: str,
    host: str,
    schema: dict,
    num_ctx: int | None,
    temperature: float | None,
    ollama_format: str = "schema",
) -> tuple[dict, dict]:
    """`ollama_format` picks Ollama's structured-output mode: 'schema' (default) sends the full
    JSON schema as `format`, grammar-constraining decoding so every token is forced onto a
    schema-valid path. 'json' sends the literal string 'json' instead - only syntactically valid
    JSON is enforced, no schema/vocabulary constraint - so the model reasons and picks its own
    JSON shape/values freely, guided by the prompt text alone. Added to test a specific
    hypothesis on granite4 (a hybrid Mamba-transformer architecture): that grammar-constrained
    decoding, developed and tuned mostly against pure-transformer models, may itself be
    responsible for the degenerate/bucketed --task score output observed under 'schema' mode,
    rather than the model's underlying judgment being that poor."""
    start = time.time()
    options: dict[str, int | float] = {}
    if num_ctx:
        options["num_ctx"] = num_ctx
    if temperature is not None:
        options["temperature"] = temperature
    messages = []
    if system_prompt is not None:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    payload = {
        "model": model,
        "messages": messages,
        "format": schema if ollama_format == "schema" else "json",
        "stream": False,
    }
    if options:
        payload["options"] = options
    resp = requests.post(f"{host}/api/chat", json=payload, timeout=1800)
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    meta = {
        "backend": "ollama",
        "model": model,
        "duration_ms": int((time.time() - start) * 1000),
        "eval_count": data.get("eval_count"),
        "prompt_eval_count": data.get("prompt_eval_count"),
    }
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ollama response wasn't valid JSON ({exc}):\n{content[:2000]}") from exc

    if not parsed.get("results") and not parsed.get("candidates"):
        print(
            f"WARNING: {model} returned technically-valid JSON but empty/missing "
            f"results and candidates - raw response follows, since this usually means the "
            f"model didn't understand the schema/task rather than a genuine all-zero batch:\n"
            f"{json.dumps(parsed, indent=2)[:3000]}",
            file=sys.stderr,
        )
    return parsed, meta


def _call_mellea(
    system_prompt: str | None,
    user_prompt: str,
    session: "mellea.MelleaSession",
    model: str,
    output_model: type[BaseModel],
    num_ctx: int | None,
    temperature: float | None,
) -> tuple[dict, dict]:
    """The mellea equivalent of _call_ollama: same Ollama server, same rendered prompts, but
    the response is decoded and validated against `output_model` by mellea instead of by hand.

    `strategy=None` is deliberate. mellea's default is RejectionSamplingStrategy, which on a
    failed requirement regenerates the WHOLE batch; this pipeline instead re-asks only for the
    comment_ids the model dropped (see _classify_one_pass), which at the default batch size -
    every comment of a TEP in one call - is dramatically cheaper. Keeping the existing targeted
    retry loop and disabling mellea's own is the point, not an oversight.

    Unlike _call_ollama, the system prompt is passed as a real system message via
    ModelOption.SYSTEM_PROMPT rather than being concatenated into the user turn, so
    _use_system_user_split()'s per-model workaround still applies here unchanged.
    """
    start = time.time()
    model_options: dict = {}
    if system_prompt is not None:
        model_options[ModelOption.SYSTEM_PROMPT] = system_prompt
    if num_ctx:
        model_options[ModelOption.CONTEXT_WINDOW] = num_ctx
    if temperature is not None:
        model_options[ModelOption.TEMPERATURE] = temperature

    result = session.instruct(
        user_prompt,
        format=output_model,
        strategy=None,
        model_options=model_options or None,
    )
    content = result.value
    meta = {
        "backend": "mellea",
        "model": model,
        "duration_ms": int((time.time() - start) * 1000),
    }
    if content is None:
        raise SystemExit(f"mellea returned no content (error: {result.error})")
    # mellea guarantees the response parses into output_model, so the isinstance/KeyError
    # guards _extract_results needs for --ollama-format json can't trigger on this path.
    # model_dump() hands back the same plain-dict shape the extractors already expect.
    return output_model.model_validate_json(content).model_dump(), meta


def _extract_results(
    parsed: dict, by_id: dict[int, dict]
) -> tuple[list[dict], list[dict], list[dict], set[int]]:
    """Returns (rows, candidates, reasoning_log, seen_ids). `reasoning_log` has one entry per
    comment that carried a `reasoning` field (--facet-split mode only), regardless of whether
    it produced any matches - otherwise a zero-match comment's reasoning is generated and then
    silently thrown away, which is exactly the case most worth seeing when debugging why a
    comment got nothing."""
    seen_ids: set[int] = set()
    rows = []
    reasoning_log = []
    for entry in parsed.get("results", []):
        if not isinstance(entry, dict):
            # Only reachable with --ollama-format json - a model free to pick its own JSON
            # shape can put a bare string/number in `results` instead of an object.
            print(f"WARNING: result entry isn't an object, dropping: {entry!r}", file=sys.stderr)
            continue
        cid = entry.get("comment_id")
        if cid is None:
            print(f"WARNING: result entry missing comment_id, dropping: {entry}", file=sys.stderr)
            continue
        seen_ids.add(cid)
        c = by_id.get(cid)
        if c is None:
            print(f"WARNING: model returned unknown comment_id {cid}, dropping", file=sys.stderr)
            continue
        reasoning = entry.get("reasoning")
        matches = entry.get("matches", [])
        if reasoning is not None:
            reasoning_log.append(
                {
                    "repo": c["repo"],
                    "pr_number": c["pr_number"],
                    "comment_id": cid,
                    "reasoning": reasoning,
                    "num_matches": len(matches),
                }
            )
        for m in matches:
            if not isinstance(m, dict):
                print(f"WARNING: match entry isn't an object, dropping: {m!r}", file=sys.stderr)
                continue
            try:
                row = {
                    "repo": c["repo"],
                    "pr_number": c["pr_number"],
                    "comment_id": cid,
                    "facet": m["facet"],
                    "value": m["value"],
                    "confidence": m["confidence"],
                    "evidence": m["evidence"],
                }
            except (KeyError, TypeError) as exc:
                # Only reachable with --ollama-format json (schema mode structurally guarantees
                # these fields) - a model free to pick its own JSON shape can omit/misname one.
                print(
                    f"WARNING: match for comment_id {cid} missing field ({exc}), dropping: {m}",
                    file=sys.stderr,
                )
                continue
            if reasoning is not None:
                row["reasoning"] = reasoning
            rows.append(row)

    candidates = []
    for cand in parsed.get("candidates", []):
        if not isinstance(cand, dict):
            print(f"WARNING: candidate isn't an object, dropping: {cand!r}", file=sys.stderr)
            continue
        cid = cand.get("comment_id")
        if cid is None:
            print(f"WARNING: candidate missing comment_id, dropping: {cand}", file=sys.stderr)
            continue
        c = by_id.get(cid)
        if c is None:
            print(
                f"WARNING: model returned a candidate for unknown comment_id {cid}, dropping",
                file=sys.stderr,
            )
            continue
        try:
            candidates.append(
                {
                    "repo": c["repo"],
                    "pr_number": c["pr_number"],
                    "comment_id": cid,
                    "fragment": cand["fragment"],
                    "candidate_facet": cand["candidate_facet"],
                    "candidate_value": cand["candidate_value"],
                    "candidate_description": cand["candidate_description"],
                }
            )
        except (KeyError, TypeError) as exc:
            print(
                f"WARNING: candidate for comment_id {cid} missing field ({exc}), dropping: {cand}",
                file=sys.stderr,
            )

    return rows, candidates, reasoning_log, seen_ids


def _extract_score_results(
    parsed: dict, by_id: dict[int, dict]
) -> tuple[list[dict], list[dict], list[dict], set[int]]:
    """--task score's counterpart to _extract_results - same return shape (rows, candidates,
    reasoning_log, seen_ids) so _classify_one_pass/_classify_batch stay task-agnostic; candidates
    and reasoning_log are always empty here since --task score has neither concept."""
    seen_ids: set[int] = set()
    rows = []
    for entry in parsed.get("results", []):
        if not isinstance(entry, dict):
            # Only reachable with --ollama-format json - a model free to pick its own JSON
            # shape can put a bare string/number in `results` instead of an object.
            print(f"WARNING: result entry isn't an object, dropping: {entry!r}", file=sys.stderr)
            continue
        cid = entry.get("comment_id")
        if cid is None:
            print(f"WARNING: result entry missing comment_id, dropping: {entry}", file=sys.stderr)
            continue
        seen_ids.add(cid)
        c = by_id.get(cid)
        if c is None:
            print(f"WARNING: model returned unknown comment_id {cid}, dropping", file=sys.stderr)
            continue
        for s in entry.get("scores", []):
            if not isinstance(s, dict):
                print(f"WARNING: score entry isn't an object, dropping: {s!r}", file=sys.stderr)
                continue
            try:
                rows.append(
                    {
                        "repo": c["repo"],
                        "pr_number": c["pr_number"],
                        "comment_id": cid,
                        "facet": s["facet"],
                        "value": s["value"],
                        "score": s["score"],
                    }
                )
            except (KeyError, TypeError) as exc:
                # Only reachable with --ollama-format json (schema mode structurally guarantees
                # these fields) - a model free to pick its own JSON shape can omit/misname one.
                print(
                    f"WARNING: score for comment_id {cid} missing field ({exc}), dropping: {s}",
                    file=sys.stderr,
                )
    return rows, [], [], seen_ids


def _use_system_user_split(model: str) -> bool:
    """granite4:small-h collapsed to near-total facet-tagging failure regardless of batch size
    or context window; its chat template (see `ollama show granite4:small-h`) is built around a
    real system/user distinction, unlike the single combined user message this script sends by
    default. Scoped to the model that actually showed the problem, not applied blanket, so it
    doesn't change results for models that were already working fine as a single message."""
    return "granite" in model.lower()


def _chunk(items: list[dict], size: int | None) -> list[list[dict]]:
    if not size or size >= len(items):
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _classify_one_pass(
    batch: list[dict],
    by_id: dict[int, dict],
    system_prompt: str,
    schema: dict,
    call_fn,
    extract_fn,
    max_retries: int,
) -> tuple[list[dict], list[dict], list[dict], list[int], list[dict]]:
    """One (system_prompt, schema) pass against one batch, retrying only for comment_ids it
    drops. Returns (rows, candidates, reasoning_log, still-missing comment_ids, list of per-call
    metadata - primary call first, then retries). Used once per facet in --facet-split mode, or
    once overall otherwise - see _classify_batch. `extract_fn` is _extract_results or (--task
    score) _extract_score_results - both share the (parsed, by_id) -> (rows, candidates,
    reasoning_log, seen_ids) shape, so this function doesn't need to know which task is running."""
    user_prompt = _build_user_prompt(batch)
    parsed, meta = call_fn(system_prompt, user_prompt, schema)
    rows, candidates, reasoning_log, seen_ids = extract_fn(parsed, by_id)
    batch_ids = {c["comment_id"] for c in batch}
    missing = sorted(batch_ids - seen_ids)
    metas = [meta]

    attempt = 0
    while missing and attempt < max_retries:
        attempt += 1
        print(
            f"  retry {attempt}/{max_retries}: re-asking for {len(missing)} dropped "
            f"comment_id(s): {missing}",
            file=sys.stderr,
        )
        retry_user_prompt = _build_user_prompt([by_id[c] for c in missing])
        retry_parsed, retry_meta = call_fn(system_prompt, retry_user_prompt, schema)
        metas.append(retry_meta)
        new_rows, new_candidates, new_reasoning, new_seen = extract_fn(retry_parsed, by_id)
        rows += new_rows
        candidates += new_candidates
        reasoning_log += new_reasoning
        seen_ids |= new_seen
        missing = sorted(batch_ids - seen_ids)

    if missing:
        print(
            f"  WARNING: {len(missing)} comment_id(s) never returned after {attempt} "
            f"retr{'y' if attempt == 1 else 'ies'}: {missing}",
            file=sys.stderr,
        )
    return rows, candidates, reasoning_log, missing, metas


def _classify_batch(
    batch: list[dict],
    by_id: dict[int, dict],
    passes: list[tuple[str, str, dict]],
    call_fn,
    extract_fn,
    max_retries: int,
) -> tuple[list[dict], list[dict], list[dict], list[int], list[dict]]:
    """Runs every (label, system_prompt, schema) pass against this batch and merges the
    results - one pass by default, three (one per facet) in --facet-split mode. `passes` is
    precomputed once per run in main(), not rebuilt per batch, since none of it depends on
    batch content. Each reasoning_log entry is tagged with which pass's `label` produced it."""
    all_rows: list[dict] = []
    all_candidates: list[dict] = []
    all_reasoning: list[dict] = []
    all_missing: set[int] = set()
    all_metas: list[dict] = []
    for label, system_prompt, schema in passes:
        if len(passes) > 1:
            print(f"  [{label}]", file=sys.stderr)
        rows, candidates, reasoning_log, missing, metas = _classify_one_pass(
            batch, by_id, system_prompt, schema, call_fn, extract_fn, max_retries
        )
        for r in reasoning_log:
            r["facet"] = label
        all_rows += rows
        all_candidates += candidates
        all_reasoning += reasoning_log
        all_missing.update(missing)
        all_metas += metas
    return all_rows, all_candidates, all_reasoning, sorted(all_missing), all_metas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument(
        "--task",
        choices=["classify", "score"],
        default="classify",
        help="'classify' (default) selects top matches per comment, same as the agent pipeline. "
        "'score' is a diagnostic pass instead: rate every taxonomy value's relevance to each "
        "comment 0.0-1.0, to tell apart 'the model ranks correctly but its match threshold is "
        "off' from 'the model can't discriminate relevant from irrelevant values at all'. Uses "
        f"{TEMPLATES_DIR / 'taxonomy_score_prompt.md.j2'} by default (override with "
        "--system-prompt-template); produces no candidates or reasoning log.",
    )
    parser.add_argument(
        "--backend",
        choices=["claude-cli", "ollama", "mellea", "mellea-claude-cli"],
        required=True,
        help="'ollama' calls the Ollama HTTP API directly with a hand-built JSON schema. "
        "'mellea' talks to the same Ollama server through mellea, deriving the schema from "
        "pydantic models and validating the response itself - same prompts, same retry loop, "
        "so its output is directly comparable to 'ollama'. 'claude-cli' shells out to "
        "`claude -p`, using a Claude Pro/Max subscription's included usage. 'mellea-claude-cli' "
        "drives that same claude-cli subprocess call through mellea's typed format=<pydantic "
        "model> path (scripts/lib/mellea_claude_cli_backend.py), directly comparable to "
        "'claude-cli' the same way 'mellea' is comparable to 'ollama'.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Backend model name (default: 'sonnet' for claude-cli; required for ollama)",
    )
    parser.add_argument("--context", choices=["none", "tep-body"], default="none")
    parser.add_argument(
        "--comment-ids",
        type=int,
        nargs="+",
        default=None,
        help="Only process these specific comment_id(s) (space-separated) instead of the whole "
        "TEP - e.g. ones you already have manually-audited ground truth for, so a diagnostic "
        "run can be checked against a known answer instead of an arbitrary file-order slice. "
        "Filters before batching, so combines normally with --batch-size/--max-batches.",
    )
    parser.add_argument(
        "--teps-dir",
        default=(os.environ.get("COMMUNITY_REPO_PATH", "") + "/teps") or None,
        help="Path to tektoncd/community/teps/ (only needed for --context tep-body)",
    )
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="Cap Ollama's context window (options.num_ctx) instead of using the model's "
        "default. Some models default to a huge context (e.g. 128K-256K) and Ollama "
        "pre-allocates KV-cache sized for it regardless of actual prompt size - on memory-"
        "constrained hardware this can exceed available memory and cause severe slowdowns "
        "or degraded output. Our prompts are a few thousand tokens; try 8192 or 16384.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature (Ollama only - no equivalent claude-cli flag). Lower values "
        "(e.g. 0.1-0.2) push toward more deterministic, less generic output - worth trying on a "
        "model that seems to be giving vague/uniform-confidence answers rather than reasoning "
        "per comment.",
    )
    parser.add_argument(
        "--ollama-format",
        choices=["schema", "json"],
        default="schema",
        help="Ollama's structured-output mode (--backend ollama only, no effect on claude-cli). "
        "'schema' (default) grammar-constrains decoding to the exact result schema - every "
        "token forced onto a schema-valid path. 'json' only enforces syntactically valid JSON, "
        "no schema/vocabulary constraint, so the model reasons and picks its own JSON shape/"
        "values freely, guided by the prompt text alone. Try this if schema mode's output looks "
        "degenerate (e.g. --task score producing near-uniform/bucketed scores) to test whether "
        "the grammar constraint itself - not the model's underlying judgment - is the "
        "bottleneck, e.g. a hybrid Mamba-transformer architecture not playing well with "
        "grammar-constrained decoding the way pure-transformer models do.",
    )
    parser.add_argument("--max-budget-usd", type=float, default=2.0)
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Re-ask, for comment_ids the model dropped from its results array, up to this "
        "many times before giving up on them",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Comments per call (default: all of the TEP's comments in one call). Lower this "
        "toward 1 to test whether batch size itself is suppressing recall - each batch is an "
        "independent call, so cost/time scale roughly with number of batches, not comments.",
    )
    parser.add_argument(
        "--facet-coverage-threshold",
        type=float,
        default=None,
        help="Nudge the model to actively check all three facets (not just default to one, a "
        "failure mode observed with granite4/qwen2.5) before concluding a facet has no match - "
        "but only include a match at or above this confidence. Omit to leave this out of the "
        "prompt entirely (the pre-existing behavior). Try ~0.4 as a starting point.",
    )
    parser.add_argument(
        "--few-shot",
        action="store_true",
        help=f"Include worked examples from {FEW_SHOT_EXAMPLES_PATH} in the system prompt - "
        "adds ~20%% to a batch=10 prompt. Try this on a model that seems to be pattern-filling "
        "the schema rather than reasoning (observed: granite4 copying comment text verbatim "
        "into `evidence`, or giving near-uniform confidence regardless of content).",
    )
    parser.add_argument(
        "--facet-split",
        action="store_true",
        help="Ask about each of the three facets in a separate call instead of one combined "
        "call - narrower scope per call, and each call's schema requires a `reasoning` field "
        "(written before `matches`, so schema-constrained generation is forced through "
        "analysis-then-answer rather than answer-first) plus constrains the facet/value enums "
        "to just that one facet. Roughly 3x the calls per batch, so 3x the cost/time. "
        "--facet-coverage-threshold has no effect in this mode - each call already asks about "
        "exactly one facet, so 'check all three' doesn't apply.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Only run the first N batches instead of the whole TEP. Combine with --batch-size "
        "to process an exact, small number of comments cheaply for a quick experiment - e.g. "
        "--batch-size 5 --max-batches 1 processes just the first 5 comments.",
    )
    parser.add_argument(
        "--system-prompt-template",
        type=Path,
        default=None,
        help="Use an alternate system-prompt template instead of "
        f"{TEMPLATES_DIR / 'system_prompt.md.j2'} - must accept the same template variables "
        "(facet_scope, facet_description, facet_values, taxonomy_block, tep_body_block, "
        "examples_block, facet_coverage_threshold). For testing prompt-wording variants "
        "without editing the canonical template in place.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.backend in ("ollama", "mellea") and not args.model:
        parser.error(f"--model is required for --backend {args.backend}")
    if args.backend in ("claude-cli", "mellea-claude-cli") and args.temperature is not None:
        print(
            f"WARNING: --temperature has no effect on --backend {args.backend}, ignoring",
            file=sys.stderr,
        )
    if args.backend != "ollama" and args.ollama_format != "schema":
        print(
            f"WARNING: --ollama-format has no effect on --backend {args.backend}, ignoring "
            "(mellea always uses its own schema-constrained decoding path)",
            file=sys.stderr,
        )
    model = args.model or "sonnet"

    record = _load_tep_record(args.tep)
    comments = _comments_for(record)
    if args.comment_ids:
        wanted = set(args.comment_ids)
        comments = [c for c in comments if c["comment_id"] in wanted]
        not_found = wanted - {c["comment_id"] for c in comments}
        if not_found:
            parser.error(f"--comment-ids not found in TEP-{args.tep}: {sorted(not_found)}")
    taxonomy = _load_taxonomy()
    taxonomy_block = _taxonomy_prompt_block(taxonomy)
    tep_body_block = None
    if args.context == "tep-body":
        if not args.teps_dir:
            parser.error("--context tep-body needs --teps-dir or COMMUNITY_REPO_PATH set")
        tep_body_block = _tep_body_block(record, Path(args.teps_dir).expanduser().resolve())
    examples_block = _load_few_shot_examples() if args.few_shot else None
    if args.few_shot and args.task == "score":
        print(
            "WARNING: --few-shot's worked examples are written for --task classify's "
            "matches/candidates shape and aren't referenced by the default --task score "
            "template - ignoring unless --system-prompt-template points at a template that "
            "uses examples_block itself",
            file=sys.stderr,
        )

    default_score_template = TEMPLATES_DIR / "taxonomy_score_prompt.md.j2"
    system_prompt_template = args.system_prompt_template or (
        default_score_template if args.task == "score" else None
    )
    # Both --backend mellea and --backend mellea-claude-cli need a pydantic model where the
    # others need a JSON-Schema dict; both builders take (taxonomy, facet_scope) and both are
    # opaque to _classify_batch, which just threads whichever one it gets back into _call.
    if args.backend in ("mellea", "mellea-claude-cli"):
        schema_fn = _build_score_model if args.task == "score" else _build_result_model
    else:
        schema_fn = _build_score_schema if args.task == "score" else _build_result_schema
    extract_fn = _extract_score_results if args.task == "score" else _extract_results

    # One (label, system_prompt, schema) pass per facet in --facet-split mode, or a single
    # combined pass otherwise - computed once here since none of it depends on batch content.
    facet_scopes: list[str | None] = list(taxonomy["facets"].keys()) if args.facet_split else [None]
    passes = [
        (
            facet_scope or "all",
            _build_system_prompt(
                taxonomy,
                taxonomy_block,
                tep_body_block,
                args.facet_coverage_threshold,
                examples_block,
                facet_scope,
                system_prompt_template,
            ),
            schema_fn(taxonomy, facet_scope),
        )
        for facet_scope in facet_scopes
    ]

    # One session for the whole run, not one per call - start_session() pulls the model if it
    # isn't present locally, which is wasted work on every batch after the first.
    mellea_session = None
    if args.backend == "mellea":
        mellea_session = mellea.start_session(
            backend_name="ollama",
            model_id=model,
            base_url=args.ollama_host,
        )
    elif args.backend == "mellea-claude-cli":
        # start_session()'s backend_name is a closed literal (ollama/hf/openai/watsonx/litellm)
        # with no claude-cli option, so construct the custom Backend directly and hand it to
        # MelleaSession - the same thing start_session() does internally for its own backends.
        mellea_session = MelleaSession(
            ClaudeCLIBackend(model=model, max_budget_usd=args.max_budget_usd)
        )

    def _call(system_prompt: str, user_prompt: str, schema) -> tuple[dict, dict]:
        sp: str | None = system_prompt
        up = user_prompt
        if not _use_system_user_split(model):
            sp = None
            up = f"{system_prompt}\n\n{user_prompt}"
        if args.backend == "claude-cli":
            return _call_claude_cli(sp, up, model, args.max_budget_usd, schema)
        if args.backend in ("mellea", "mellea-claude-cli"):
            assert mellea_session is not None
            return _call_mellea(
                sp, up, mellea_session, model, schema, args.num_ctx, args.temperature
            )
        return _call_ollama(
            sp,
            up,
            model,
            args.ollama_host,
            schema,
            args.num_ctx,
            args.temperature,
            args.ollama_format,
        )

    by_id = {c["comment_id"]: c for c in comments}
    batches = _chunk(comments, args.batch_size)
    if args.max_batches:
        batches = batches[: args.max_batches]

    out_dir = args.out_dir or Path(f"processed/tep{args.tep}")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"classify_llm_{args.backend}_{args.context}_{model.replace(':', '-').replace('/', '-')}"
    if args.task != "classify":
        tag += f"_task-{args.task}"
    if args.comment_ids:
        tag += f"_ids{len(args.comment_ids)}"
    if args.batch_size:
        tag += f"_batch{args.batch_size}"
    if args.facet_coverage_threshold is not None:
        tag += f"_facetcov{args.facet_coverage_threshold}"
    if args.ollama_format != "schema":
        tag += f"_fmt-{args.ollama_format}"
    if args.num_ctx:
        tag += f"_numctx{args.num_ctx}"
    if args.temperature is not None:
        tag += f"_temp{args.temperature}"
    if args.few_shot:
        tag += "_fewshot"
    if args.facet_split:
        tag += "_facetsplit"
    if args.max_batches:
        tag += f"_maxbatches{args.max_batches}"
    if system_prompt_template:
        template_name = system_prompt_template.name.removesuffix(".md.j2")
        tag += f"_tmpl-{template_name}"
    out_path = out_dir / f"{tag}.jsonl"
    candidates_path = out_dir / f"{tag}.candidates.jsonl"
    reasoning_path = out_dir / f"{tag}.reasoning.jsonl"
    meta_path = out_dir / f"{tag}.meta.json"

    def _write_meta(num_batches_done: int, interrupted: bool) -> None:
        meta = {
            "backend": args.backend,
            "model": model,
            "tep": args.tep,
            "task": args.task,
            "context": args.context,
            "comment_ids": args.comment_ids,
            "ollama_format": args.ollama_format,
            "batch_size": args.batch_size or len(comments),
            "num_batches": len(batches),
            "num_batches_completed": num_batches_done,
            "interrupted": interrupted,
            "facet_coverage_threshold": args.facet_coverage_threshold,
            "num_ctx": args.num_ctx,
            "temperature": args.temperature,
            "few_shot": args.few_shot,
            "facet_split": args.facet_split,
            "max_batches": args.max_batches,
            "system_prompt_template": (
                str(system_prompt_template) if system_prompt_template else None
            ),
            "num_comments": len(comments),
            "num_rows": len(rows),
            "num_candidates": len(candidates),
            "num_reasoning_entries": len(reasoning_entries),
            "missing_comment_ids": sorted(missing),
            "num_calls": len(all_metas),
            "calls": all_metas,
            "total_cost_usd": (
                sum(m.get("cost_usd") or 0 for m in all_metas)
                if args.backend == "claude-cli"
                else None
            ),
            "total_duration_ms": sum(m.get("duration_ms") or 0 for m in all_metas),
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    comments_in_scope = sum(len(b) for b in batches)
    scope_note = (
        f"{comments_in_scope} of {len(comments)} comments (--max-batches {args.max_batches})"
        if args.max_batches
        else f"{len(comments)} comments"
    )
    print(
        f"TEP-{args.tep}: {scope_note} in {len(batches)} batch(es) of up to "
        f"{args.batch_size or len(comments)}, context={args.context}, backend={args.backend}, "
        f"model={model}\nwriting incrementally to {out_path} as each batch completes - open it "
        f"any time to check progress, or Ctrl-C to stop early and keep what's done so far",
        file=sys.stderr,
    )

    rows: list[dict] = []
    candidates: list[dict] = []
    reasoning_entries: list[dict] = []
    missing: list[int] = []
    all_metas: list[dict] = []
    batches_done = 0
    run_start = time.time()
    with (
        out_path.open("w") as out_f,
        candidates_path.open("w") as cand_f,
        reasoning_path.open("w") as reasoning_f,
    ):
        try:
            for i, batch in enumerate(batches, 1):
                batch_start = time.time()
                now_str = time.strftime("%H:%M:%S")
                print(
                    f"[{now_str}] batch {i}/{len(batches)} ({len(batch)} comments)...",
                    file=sys.stderr,
                )
                batch_rows, batch_candidates, batch_reasoning, batch_missing, batch_metas = (
                    _classify_batch(
                        batch,
                        by_id,
                        passes,
                        _call,
                        extract_fn,
                        args.max_retries,
                    )
                )
                rows += batch_rows
                candidates += batch_candidates
                reasoning_entries += batch_reasoning
                missing += batch_missing
                all_metas += batch_metas
                batches_done = i

                for r in batch_rows:
                    out_f.write(json.dumps(r) + "\n")
                for c in batch_candidates:
                    cand_f.write(json.dumps(c) + "\n")
                for rr in batch_reasoning:
                    reasoning_f.write(json.dumps(rr) + "\n")
                out_f.flush()
                cand_f.flush()
                reasoning_f.flush()

                batch_elapsed = time.time() - batch_start
                total_elapsed = time.time() - run_start
                remaining = len(batches) - i
                eta = (total_elapsed / i) * remaining if i else 0.0
                cost = sum(m.get("cost_usd") or 0 for m in batch_metas)
                cost_str = f", ${cost:.3f}" if args.backend == "claude-cli" else ""
                if args.task == "score":
                    print(
                        f"  -> {len(batch_rows)} score(s) across {len(batch)} comment(s)"
                        f"{cost_str} (running total: {len(rows)} scores) "
                        f"[batch took {batch_elapsed:.0f}s, elapsed {total_elapsed:.0f}s, "
                        f"~{eta:.0f}s / {remaining} batch(es) left]",
                        file=sys.stderr,
                    )
                else:
                    facet_counts = Counter(r["facet"] for r in batch_rows)
                    print(
                        f"  -> {len(batch_rows)} tag(s) {dict(facet_counts)}, "
                        f"{len(batch_candidates)} candidate(s){cost_str} "
                        f"(running total: {len(rows)} tags, {len(candidates)} candidates) "
                        f"[batch took {batch_elapsed:.0f}s, elapsed {total_elapsed:.0f}s, "
                        f"~{eta:.0f}s / {remaining} batch(es) left]",
                        file=sys.stderr,
                    )
        except KeyboardInterrupt:
            _write_meta(batches_done, interrupted=True)
            print(
                f"\nInterrupted after {batches_done}/{len(batches)} batches. Kept {len(rows)} "
                f"rows, {len(candidates)} candidates, and {len(reasoning_entries)} reasoning "
                f"entries written so far in {out_path}, {candidates_path}, and {reasoning_path} "
                f"(meta.json marked interrupted=true).",
                file=sys.stderr,
            )
            return 130
        except Exception:
            # A user Ctrl-C leaves a self-documenting meta.json (interrupted=true) so a
            # partial run is never mistaken for a complete one; an unhandled error (timeout,
            # connection drop, etc. - observed on a real TEP-84 run) used to skip _write_meta
            # entirely and leave nothing distinguishing it from a complete run except the
            # missing meta.json file. Write the same marker here before re-raising, so the
            # traceback still surfaces (the caller/shell loop still sees a non-zero exit) but
            # the partial output is never silently indistinguishable from a finished one.
            _write_meta(batches_done, interrupted=True)
            print(
                f"\nFailed after {batches_done}/{len(batches)} batches. Kept {len(rows)} rows "
                f"and {len(candidates)} candidates written so far in {out_path} and "
                f"{candidates_path} (meta.json marked interrupted=true). Re-run with the same "
                "args to retry.",
                file=sys.stderr,
            )
            raise

    _write_meta(batches_done, interrupted=False)

    print(f"wrote {len(rows)} rows -> {out_path}", file=sys.stderr)
    print(f"wrote {len(candidates)} candidate(s) -> {candidates_path}", file=sys.stderr)
    print(f"wrote {len(reasoning_entries)} reasoning entries -> {reasoning_path}", file=sys.stderr)
    print(f"wrote run metadata -> {meta_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
