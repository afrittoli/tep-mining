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

Usage:
    uv run scripts/classify_llm.py --tep 52 --backend claude-cli --context none
    uv run scripts/classify_llm.py --tep 52 --backend claude-cli --context tep-body
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
        --context tep-body

    # split into smaller calls instead of one call for the whole TEP - test whether batch size
    # itself is suppressing recall (each batch retries independently for dropped comment_ids):
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model qwen2.5:32b-instruct \
        --context none --batch-size 10

    # inspect exactly what a run would send, without calling the backend or spending budget:
    uv run scripts/classify_llm.py --tep 52 --backend ollama --model granite4:small-h \
        --context tep-body --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader
from ruamel.yaml import YAML

TAXONOMY_PATH = Path("conventions/seed-taxonomy.yaml")
RECORDS_PATH = Path("processed/latest/per_tep_records.json")
FEW_SHOT_EXAMPLES_PATH = Path(__file__).parent / "data" / "few_shot_examples.yaml"
TEMPLATES_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True
)


def _facet_scope_names(taxonomy: dict, facet_scope: str | list[str] | None) -> list[str]:
    """Normalizes the three shapes `facet_scope` can take across this module: `None` (legacy
    unscoped, all facets), a single facet name (legacy --facet-split, one call per facet), or a
    list of facet names (the tiered pipeline's grouped passes - `["area", "nature"]` for Pass 1,
    `["principle"]` for Pass 2, all three explicitly for Pass 3). Returns the facet name list to
    use; callers distinguish "unscoped" from "scoped" via `facet_scope is None`, not via this
    return value, since a single-facet legacy scope and the unscoped case both need distinct
    prompt wording (see _build_system_prompt)."""
    if facet_scope is None:
        return list(taxonomy["facets"].keys())
    if isinstance(facet_scope, str):
        return [facet_scope]
    return list(facet_scope)


def _build_result_schema(taxonomy: dict, facet_scope: str | list[str] | None = None) -> dict:
    """`facet`/`value` are enums of the actual taxonomy, not free strings - otherwise a model
    that ignores the given vocabulary still produces schema-valid JSON, just full of invented
    facet/value names with zero real signal (observed: one model invented a whole new facet,
    another used real values under invented facet names - both pass a plain-string schema).

    `facet_scope` narrows both enums to one or more facets - a single facet name for legacy
    --facet-split mode, a list of facet names for the tiered pipeline's grouped passes (Pass 1:
    area+nature together, Pass 2: principle alone, Pass 3: all three explicitly) - and, whenever
    scoped (str or non-empty list, i.e. not the bare unscoped `None` case), adds a required
    `reasoning` field ordered *before* `matches` in the schema - with schema-constrained
    decoding, property order is generation order, so this forces the model to write its
    analysis before committing to a match rather than justifying one after the fact.
    """
    facet_names = _facet_scope_names(taxonomy, facet_scope)
    all_values = sorted(
        {
            v["value"]
            for name in facet_names
            for v in (taxonomy["facets"][name].get("values") or [])
        }
    )

    result_item_properties: dict = {"comment_id": {"type": "integer"}}
    result_item_required = ["comment_id"]
    if facet_scope is not None:
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
                "quote": {
                    "type": "string",
                    "description": "An exact, or very-near-exact, literal substring copied "
                    "directly from THIS COMMENT's own text that supports the match - not a "
                    "paraphrase (that's what `evidence` is for). Used mechanically afterward "
                    "to measure how much of the comment's text the matches actually account "
                    "for, so copy real words from the comment rather than lightly rewording "
                    "them.",
                },
            },
            "required": ["facet", "value", "confidence", "evidence", "quote"],
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


def _load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))


def _taxonomy_prompt_block(taxonomy: dict, facet_names: list[str] | None = None) -> str:
    """Facet/value/description text for the prompt - not the whole file; semantics/provenance/
    parent bookkeeping isn't needed to make a classification call. `facet_names` restricts this
    to a subset of facets (used for a scoped pass - legacy --facet-split's one facet, or the
    tiered pipeline's area+nature / principle / all-three groupings); omit for the full,
    unscoped taxonomy."""
    lines: list[str] = []
    names = facet_names if facet_names is not None else list(taxonomy["facets"].keys())
    for facet_name in names:
        facet = taxonomy["facets"][facet_name]
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


def _load_few_shot_examples(path: Path = FEW_SHOT_EXAMPLES_PATH) -> list[dict]:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))["examples"]


def _few_shot_examples_block(
    examples: list[dict], facet_scope: str | list[str] | None = None
) -> str:
    """Projects data/few_shot_examples.yaml's per-facet views into the prose block shown in
    the prompt.

    Unscoped (`facet_scope=None`): each example shows its full multi-facet `matches` list, no
    `reasoning` field - matching the unscoped result schema.

    Facet-scoped (a single facet name, legacy --facet-split; or a list of facet names, the
    tiered pipeline's grouped passes): each example shows only the listed facet(s)' slice(s),
    combined into one `matches` list (each entry still tagged with its own `facet`), with the
    `reasoning` field the scoped schema requires (see _build_result_schema's docstring for why
    that's paired with facet-scoping) - synthesized by joining each scoped facet's own
    `reasoning` when more than one is in play, since the schema has one `reasoning` string per
    comment, not one per facet. Only surfaces `candidates` entries that are gap proposals for
    one of the scoped facets - a scoped call is told to only consider those facets, so it
    shouldn't be handed a different facet's gap.
    """
    facet_names = [facet_scope] if isinstance(facet_scope, str) else facet_scope
    lines = [
        "# Worked examples",
        "",
        "`evidence` is a tight paraphrase of the specific part of the comment that justifies a "
        "match, never the whole comment copied verbatim; `quote` is a separate, exact (or "
        "very-near-exact) literal substring of the comment - copy real words, don't paraphrase "
        "them there. An empty `matches` list is a complete, correct answer - most comments "
        "legitimately match nothing"
        + (f" in {', '.join(facet_names)}" if facet_names else ", on any facet")
        + ", do not force one just to produce output.",
        "",
    ]
    for i, ex in enumerate(examples, start=1):
        comment_id = 900000000 + i
        if facet_names:
            views = [ex["facets"][f] for f in facet_names]
            matches = [
                {
                    "facet": f,
                    **{k: m[k] for k in ("value", "confidence", "evidence", "quote")},
                }
                for f, view in zip(facet_names, views)
                for m in view["matches"]
            ]
            reasoning = " ".join(v["reasoning"].strip() for v in views)
            item = {"comment_id": comment_id, "reasoning": reasoning, "matches": matches}
            candidates = [c for c in ex["candidates"] if c["candidate_facet"] in facet_names]
        else:
            matches = [
                {
                    "facet": facet_name,
                    **{k: m[k] for k in ("value", "confidence", "evidence", "quote")},
                }
                for facet_name, view in ex["facets"].items()
                for m in view["matches"]
            ]
            item = {"comment_id": comment_id, "matches": matches}
            candidates = ex["candidates"]

        lines.append(f"Example {i} - {ex['label']}:")
        lines.append("")
        lines.append(f'Comment: "{ex["comment"]}"')
        lines.append("")
        lines.append("Good output:")
        lines.append("")
        lines.append("```json")
        if candidates:
            envelope = {
                "results": [item],
                "candidates": [
                    {
                        "comment_id": comment_id,
                        "fragment": c["fragment"],
                        "candidate_facet": c["candidate_facet"],
                        "candidate_value": c["candidate_value"],
                        "candidate_description": c["candidate_description"],
                    }
                    for c in candidates
                ],
            }
            lines.append(json.dumps(envelope, indent=2))
        else:
            lines.append(json.dumps(item, indent=2))
        lines.append("```")
        if candidates:
            lines.append("")
            lines.append(
                "This comment gets both a normal match AND a candidate (the gap nothing in "
                "the taxonomy names yet) - the two are not exclusive."
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_system_prompt(
    taxonomy: dict,
    taxonomy_block: str,
    tep_body_block: str | None,
    facet_coverage_threshold: float | None = None,
    examples_block: str | None = None,
    facet_scope: str | list[str] | None = None,
) -> str:
    """Renders templates/system_prompt.md.j2 - everything that doesn't change per batch: task
    framing, taxonomy, optional TEP body, optional facet-coverage nudge, optional worked
    examples. Kept separate from the comments themselves (see _build_user_prompt) since some
    models (observed: granite4) are trained around a real system/user split and behave more
    generically when everything is crammed into one user turn.

    `facet_scope` narrows the prompt to describe only the given facet(s) - a single facet name
    for legacy --facet-split mode, or a list of facet names for the tiered pipeline's grouped
    passes (Pass 1: area+nature, Pass 2: principle, Pass 3: all three explicitly); see
    _build_result_schema for why any non-None scope is paired with a required `reasoning`
    field."""
    facet_scope_names = None
    scoped_taxonomy_block = None
    if facet_scope is not None:
        facet_scope_names = _facet_scope_names(taxonomy, facet_scope)
        scoped_taxonomy_block = _taxonomy_prompt_block(taxonomy, facet_scope_names)
    template = _jinja_env.get_template("system_prompt.md.j2")
    return template.render(
        facet_scope_names=facet_scope_names,
        scoped_taxonomy_block=scoped_taxonomy_block,
        taxonomy_block=taxonomy_block,
        tep_body_block=tep_body_block,
        examples_block=examples_block,
        facet_coverage_threshold=facet_coverage_threshold,
    )


def _build_user_prompt(
    comments: list[dict],
    context_by_id: dict[int, str] | None = None,
    note: str | None = None,
) -> str:
    """Renders templates/user_prompt.md.j2 - just the comment list, so it's cheap to rebuild
    per retry without re-rendering the (unchanging) system prompt.

    `context_by_id` (Pass 3 only) attaches, under each comment, a one-line summary of what
    Pass 1/2 already found for it - Pass 3 "sees all of Pass 1 + Pass 2's results as context"
    per the plan doc, so it can correct or extend a prior pass's judgment rather than starting
    blind. `note` is an optional leading paragraph (also Pass 3: explains why these particular
    comments were flagged and what's expected of a re-check)."""
    template = _jinja_env.get_template("user_prompt.md.j2")
    rendered = [
        {
            "comment_id": c["comment_id"],
            "pr_number": c["pr_number"],
            "loc": c.get("section") or c.get("path") or "",
            "author": c.get("author") or "",
            "body": c["body"],
            "context": (context_by_id or {}).get(c["comment_id"]),
        }
        for c in comments
    ]
    return template.render(comments=rendered, note=note)


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
    think: str | None = None,
) -> tuple[dict, dict]:
    """`think` is granite4.2's built-in thinking-mode dial on Ollama's /api/chat (`think: low`
    for the tiered pipeline's fast Pass 1/2 calls, `think: high` for Pass 3's expensive
    re-check on flagged comments only) - a top-level field on the request, not an `options`
    entry. Passed through as-is (str, e.g. "low"/"medium"/"high", or a bool for models whose
    Ollama integration only supports on/off); omitted entirely when None, so non-thinking
    models and the legacy pipeline see byte-identical requests to before this was added."""
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
    payload: dict = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
    }
    if options:
        payload["options"] = options
    if think is not None:
        payload["think"] = think
    resp = requests.post(f"{host}/api/chat", json=payload, timeout=1800)
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    meta = {
        "backend": "ollama",
        "model": model,
        "think": think,
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


def _extract_results(
    parsed: dict, by_id: dict[int, dict]
) -> tuple[list[dict], list[dict], set[int]]:
    seen_ids: set[int] = set()
    rows = []
    for entry in parsed.get("results", []):
        cid = entry["comment_id"]
        seen_ids.add(cid)
        c = by_id.get(cid)
        if c is None:
            print(f"WARNING: model returned unknown comment_id {cid}, dropping", file=sys.stderr)
            continue
        reasoning = entry.get("reasoning")
        for m in entry.get("matches", []):
            row = {
                "repo": c["repo"],
                "pr_number": c["pr_number"],
                "comment_id": cid,
                "facet": m["facet"],
                "value": m["value"],
                "confidence": m["confidence"],
                "evidence": m["evidence"],
            }
            if "quote" in m:
                row["quote"] = m["quote"]
            if reasoning is not None:
                row["reasoning"] = reasoning
            rows.append(row)

    candidates = []
    for cand in parsed.get("candidates", []):
        cid = cand["comment_id"]
        c = by_id.get(cid)
        if c is None:
            print(
                f"WARNING: model returned a candidate for unknown comment_id {cid}, dropping",
                file=sys.stderr,
            )
            continue
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

    return rows, candidates, seen_ids


def _find_quote_span(text: str, quote: str) -> tuple[int, int] | None:
    """Locates `quote` inside `text`, tolerating only whitespace differences (a model
    re-wrapping a quote across a line break, or collapsing internal spacing) - not fuzzy or
    approximate matching. Returns the quote's (start, end) character span in `text`'s own
    coordinates, or None if it isn't grounded in `text` at all - a quote that doesn't even
    near-exactly match the comment gives no real evidence anything was accounted for, so it's
    treated as not covering anything, not as "probably fine"."""
    quote = quote.strip()
    if not quote:
        return None
    idx = text.find(quote)
    if idx != -1:
        return idx, idx + len(quote)
    tokens = quote.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(tok) for tok in tokens)
    m = re.search(pattern, text)
    if m:
        return m.start(), m.end()
    return None


def uncovered_fraction(comment_body: str, quotes: list[str]) -> float:
    """Part 2's "catching missed tags on comments that did get tagged" heuristic: union the
    character spans of `quotes` found (near-exactly, via _find_quote_span) in `comment_body`,
    and return the fraction of `comment_body`'s characters falling outside that union - pure
    string math, no model call. A comment with no quotes at all is fully uncovered (1.0); an
    empty `comment_body` is vacuously fully covered (0.0), since there's no text left over to
    miss. This is a standalone, model-independent function specifically so it can be sanity-
    checked with plain inline cases rather than trusted on faith - see
    tests/test_classify_llm.py."""
    n = len(comment_body)
    if n == 0:
        return 0.0
    covered = bytearray(n)
    for q in quotes:
        span = _find_quote_span(comment_body, q)
        if span:
            start, end = span
            covered[start:end] = b"\x01" * (end - start)
    return covered.count(0) / n


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
    max_retries: int,
    build_user_prompt: Callable[[list[dict]], str] = _build_user_prompt,
) -> tuple[list[dict], list[dict], list[int], list[dict]]:
    """One (system_prompt, schema) pass against one batch, retrying only for comment_ids it
    drops. Returns (rows, candidates, still-missing comment_ids, list of per-call metadata -
    primary call first, then retries). Used once per facet in --facet-split mode, once per
    tiered-pipeline pass (Pass 1/2/3 - see _run_tiered_batch), or once overall in plain
    single-call legacy mode - see _classify_batch. `build_user_prompt` defaults to the plain
    comment-list renderer; Pass 3 passes a closure that also attaches each comment's Pass 1/2
    context and an explanatory note (see _run_tiered_batch)."""
    user_prompt = build_user_prompt(batch)
    parsed, meta = call_fn(system_prompt, user_prompt, schema)
    rows, candidates, seen_ids = _extract_results(parsed, by_id)
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
        retry_user_prompt = build_user_prompt([by_id[c] for c in missing])
        retry_parsed, retry_meta = call_fn(system_prompt, retry_user_prompt, schema)
        metas.append(retry_meta)
        new_rows, new_candidates, new_seen = _extract_results(retry_parsed, by_id)
        rows += new_rows
        candidates += new_candidates
        seen_ids |= new_seen
        missing = sorted(batch_ids - seen_ids)

    if missing:
        print(
            f"  WARNING: {len(missing)} comment_id(s) never returned after {attempt} "
            f"retr{'y' if attempt == 1 else 'ies'}: {missing}",
            file=sys.stderr,
        )
    return rows, candidates, missing, metas


def _print_dry_run(passes: list[tuple[str, str, dict]], batch: list[dict], model: str) -> None:
    """Prints exactly what --backend would send for one example batch, without calling it -
    applies the same system/user split as _call() in main(), so what's printed matches what a
    real run would send byte-for-byte. One block per pass (just "all" normally, one per facet
    in --facet-split mode)."""
    user_prompt = _build_user_prompt(batch)
    for label, system_prompt, _schema in passes:
        sp, up = system_prompt, user_prompt
        if not _use_system_user_split(model):
            sp, up = None, f"{system_prompt}\n\n{user_prompt}"
        print(f"===== pass: {label} =====")
        if sp is not None:
            print("----- system prompt -----")
            print(sp)
            print("----- user prompt -----")
            print(up)
        else:
            print("----- combined prompt (no system/user split for this model) -----")
            print(up)
        print()


def _classify_batch(
    batch: list[dict],
    by_id: dict[int, dict],
    passes: list[tuple[str, str, dict]],
    call_fn,
    max_retries: int,
) -> tuple[list[dict], list[dict], list[int], list[dict]]:
    """Runs every (label, system_prompt, schema) pass against this batch and merges the
    results - one pass by default, three (one per facet) in --facet-split mode. `passes` is
    precomputed once per run in main(), not rebuilt per batch, since none of it depends on
    batch content."""
    all_rows: list[dict] = []
    all_candidates: list[dict] = []
    all_missing: set[int] = set()
    all_metas: list[dict] = []
    for label, system_prompt, schema in passes:
        if len(passes) > 1:
            print(f"  [{label}]", file=sys.stderr)
        rows, candidates, missing, metas = _classify_one_pass(
            batch, by_id, system_prompt, schema, call_fn, max_retries
        )
        all_rows += rows
        all_candidates += candidates
        all_missing.update(missing)
        all_metas += metas
    return all_rows, all_candidates, sorted(all_missing), all_metas


# --- Tiered pipeline (taxonomy-and-pipeline-plan.md Part 2) -------------------------------
#
# Pass 1 (area+nature together) and Pass 2 (principle, skipping nature:none comments) run on a
# fast model; only comments either pass flagged - or the quote-coverage heuristic flags despite
# confident matches - go to Pass 3, a slower/thinking model. This is the default pipeline (see
# --pipeline); the single-call/--facet-split machinery above is kept as --pipeline legacy for a
# future claude-cli cost comparison, not deleted.


def _missing_facet_flags(rows: list[dict], comment_ids: set[int]) -> dict[int, list[str]]:
    """Pass 1's flagging rule: `area` almost never comes back confidently empty (near-mandatory
    coverage) and `nature` should always commit to something, including the explicit `none`
    value - a comment with no area match, or no nature match at all, after Pass 1 is itself a
    signal something went wrong, not a normal outcome. Returns {comment_id: [missing facet
    name(s)]} for comments missing at least one of the two - this naturally also covers
    comments the model dropped entirely (zero rows), which are missing both."""
    has_area = {r["comment_id"] for r in rows if r["facet"] == "area"}
    has_nature = {r["comment_id"] for r in rows if r["facet"] == "nature"}
    flags: dict[int, list[str]] = {}
    for cid in comment_ids:
        missing = [
            name for name, seen in (("area", has_area), ("nature", has_nature)) if cid not in seen
        ]
        if missing:
            flags[cid] = missing
    return flags


def _nature_none_ids(rows: list[dict]) -> set[int]:
    """Pass 2 skips every comment Pass 1 tagged `nature: none` - the explicit "reviewed,
    insignificant" signal, so there's nothing for a principle pass to look for."""
    return {r["comment_id"] for r in rows if r["facet"] == "nature" and r["value"] == "none"}


def _low_confidence_ids(rows: list[dict], facet: str, threshold: float) -> set[int]:
    """Comments with at least one `facet` match below `threshold` - Pass 2's confidence-gated
    escalation rule (a confident empty result needs no follow-up; a low-confidence match does,
    per the plan doc: principle isn't assumed rare, but flagging it is gated on confidence, not
    presence)."""
    return {
        r["comment_id"]
        for r in rows
        if r["facet"] == facet and r["confidence"] is not None and r["confidence"] < threshold
    }


def _quote_coverage_flags(
    rows: list[dict],
    by_id: dict[int, dict],
    threshold: float,
    exclude_ids: AbstractSet[int] = frozenset(),
) -> dict[int, float]:
    """The plan doc's "catching missed tags on comments that did get tagged" heuristic: for
    every comment with at least one match so far, union its matches' `quote` spans against its
    own text via uncovered_fraction, and flag it if more than `threshold` of the comment's text
    falls outside that union - even though it already had confident matches. Comments with zero
    matches at all aren't in scope here (that's Pass 1's missing-facet and nature:none
    handling, not this heuristic). `exclude_ids` is meant for nature:none comments: a short
    acknowledgment's one or two quotes rarely cover 100% of its scaffolding words/punctuation,
    which would otherwise re-flag a comment Pass 1 already confidently marked insignificant -
    defeating the point of nature:none skipping further passes at all."""
    quotes_by_comment: dict[int, list[str]] = {}
    for r in rows:
        if r["comment_id"] in exclude_ids:
            continue
        quote = r.get("quote")
        if quote:
            quotes_by_comment.setdefault(r["comment_id"], []).append(quote)
    flags: dict[int, float] = {}
    for cid, quotes in quotes_by_comment.items():
        frac = uncovered_fraction(by_id[cid]["body"], quotes)
        if frac > threshold:
            flags[cid] = frac
    return flags


PASS2_NOTE = (
    'Each comment below already has an area/nature tag from an earlier pass, shown as "already '
    'found" - use it as context for whether a documented principle applies (e.g. a `code` area '
    "plus a `content` nature is more likely to raise a design-principle concern than a `docs` "
    "area plus `formatting`), but let the comment's own text decide - don't tag a principle "
    "just because the area suggests one might apply."
)

PASS3_NOTE = (
    'Every comment below was already looked at by an earlier, faster pass - shown as "already '
    'found", plus why it was flagged for this closer look (a missing area or nature match, a '
    "low-confidence principle match, or matched quotes that didn't account for most of the "
    "comment's text). Re-evaluate each one across all three facets from scratch: correct, "
    "extend, or confirm what's already there - don't just repeat it unexamined."
)


def _tags_context_by_id(rows: list[dict], comment_ids: set[int]) -> dict[int, str]:
    """A comment's already-tagged (facet/value, confidence) pairs as a one-line display string -
    the "already found" context shown to Pass 2 (which the plan doc describes as seeing Pass 1's
    results) and the tag portion of Pass 3's richer per-comment context (see
    _pass3_context_by_id, which adds the flag reason on top of this)."""
    by_cid: dict[int, list[dict]] = {}
    for r in rows:
        by_cid.setdefault(r["comment_id"], []).append(r)
    return {
        cid: (
            "; ".join(
                f"{r['facet']}/{r['value']} (confidence {r['confidence']:.2f})"
                for r in by_cid.get(cid, [])
            )
            or "nothing tagged"
        )
        for cid in comment_ids
    }


def _pass3_context_by_id(
    rows: list[dict], flag_info: dict[int, dict], comment_ids: set[int]
) -> dict[int, str]:
    """Builds the "already found" line shown under each flagged comment in Pass 3's user
    prompt - what Pass 1/2 already tagged, plus why this comment was flagged - so Pass 3 (which
    "sees all of Pass 1 + Pass 2's results as context" per the plan doc) can correct or extend a
    prior judgment instead of starting blind."""
    tag_strs = _tags_context_by_id(rows, comment_ids)
    out: dict[int, str] = {}
    for cid in comment_ids:
        info = flag_info.get(cid, {})
        reasons = []
        if info.get("missing_facets"):
            reasons.append("missing " + "/".join(info["missing_facets"]))
        if info.get("principle_pass_dropped"):
            reasons.append("principle pass never returned this comment")
        if info.get("low_confidence_principle"):
            reasons.append("low-confidence principle match")
        if "uncovered_fraction" in info:
            reasons.append(
                f"~{info['uncovered_fraction']:.0%} of the comment's text uncovered by quotes"
            )
        out[cid] = f"{tag_strs[cid]} -- flagged because: {', '.join(reasons) or 'unknown'}"
    return out


def _run_tiered_batch(
    batch: list[dict],
    by_id: dict[int, dict],
    pass1: tuple[str, dict],
    pass2: tuple[str, dict],
    pass3: tuple[str, dict],
    call_12,
    call_3,
    max_retries: int,
    principle_confidence_threshold: float,
    quote_coverage_threshold: float,
) -> tuple[list[dict], list[dict], list[int], list[dict], list[dict]]:
    """Runs the 3-pass tiered pipeline against one batch: Pass 1 (area+nature together), Pass 2
    (principle, skipping nature:none comments), then Pass 3 (all three facets, thinking model)
    on only the comments either pass flagged, plus any comment the quote-coverage heuristic
    flags despite already having confident matches. Pass 3's output fully replaces Pass 1/2's
    rows for the comments it re-processes - it sees their results as context and is expected to
    correct or confirm them, not add a second, possibly-conflicting opinion alongside.

    Returns (rows, candidates, missing_comment_ids, call_metas, flag_records) - `flag_records`
    is one dict per batch comment (not just flagged ones), with the raw signals that did or
    didn't trigger escalation, meant to be written to `<tag>.flags.jsonl` for future threshold
    tuning (the plan doc's Open Questions: the cutoffs aren't tuned from real data yet).

    `missing_comment_ids` is exactly Pass 3's own leftover-missing set: every comment_id Pass
    1/2 fully dropped is, by construction, also flagged (see _missing_facet_flags), so it's
    already inside escalate_ids and gets one more chance in Pass 3; only a comment Pass 3 also
    drops counts as still missing overall.
    """
    pass1_system_prompt, pass1_schema = pass1
    pass2_system_prompt, pass2_schema = pass2
    pass3_system_prompt, pass3_schema = pass3
    batch_ids = {c["comment_id"] for c in batch}

    print("  [pass 1: area+nature]", file=sys.stderr)
    rows1, candidates1, missing1, metas1 = _classify_one_pass(
        batch, by_id, pass1_system_prompt, pass1_schema, call_12, max_retries
    )
    missing_facets = _missing_facet_flags(rows1, batch_ids)

    skip_ids = _nature_none_ids(rows1)
    pass2_batch = [c for c in batch if c["comment_id"] not in skip_ids]
    rows2: list[dict] = []
    candidates2: list[dict] = []
    missing2: list[int] = []
    metas2: list[dict] = []
    if pass2_batch:
        print(
            f"  [pass 2: principle, {len(pass2_batch)}/{len(batch)} comments - "
            f"{len(skip_ids)} skipped as nature:none]",
            file=sys.stderr,
        )
        pass1_context = _tags_context_by_id(
            rows1, {c["comment_id"] for c in pass2_batch}
        )
        rows2, candidates2, missing2, metas2 = _classify_one_pass(
            pass2_batch,
            by_id,
            pass2_system_prompt,
            pass2_schema,
            call_12,
            max_retries,
            build_user_prompt=lambda cs: _build_user_prompt(cs, pass1_context, PASS2_NOTE),
        )
    elif skip_ids:
        print("  [pass 2: skipped entirely - every comment was nature:none]", file=sys.stderr)

    low_conf_principle = _low_confidence_ids(rows2, "principle", principle_confidence_threshold)
    pass2_dropped = set(missing2)
    quote_flags = _quote_coverage_flags(
        rows1 + rows2, by_id, quote_coverage_threshold, exclude_ids=skip_ids
    )

    flag_info: dict[int, dict] = {}
    for cid, missing_names in missing_facets.items():
        flag_info.setdefault(cid, {})["missing_facets"] = missing_names
    for cid in pass2_dropped:
        flag_info.setdefault(cid, {})["principle_pass_dropped"] = True
    for cid in low_conf_principle:
        flag_info.setdefault(cid, {})["low_confidence_principle"] = True
    for cid, frac in quote_flags.items():
        flag_info.setdefault(cid, {})["uncovered_fraction"] = frac

    escalate_ids = sorted(flag_info)
    flag_records = [
        {
            "comment_id": cid,
            "missing_facets": flag_info.get(cid, {}).get("missing_facets", []),
            "principle_pass_dropped": flag_info.get(cid, {}).get("principle_pass_dropped", False),
            "low_confidence_principle": flag_info.get(cid, {}).get(
                "low_confidence_principle", False
            ),
            "uncovered_fraction": flag_info.get(cid, {}).get("uncovered_fraction"),
            "escalated_to_pass3": cid in flag_info,
        }
        for cid in sorted(batch_ids)
    ]

    rows3: list[dict] = []
    candidates3: list[dict] = []
    missing3: list[int] = []
    metas3: list[dict] = []
    if escalate_ids:
        print(
            f"  [pass 3: thinking model, {len(escalate_ids)}/{len(batch)} comments flagged: "
            f"{escalate_ids}]",
            file=sys.stderr,
        )
        pass3_batch = [by_id[cid] for cid in escalate_ids]
        context_by_id = _pass3_context_by_id(rows1 + rows2, flag_info, set(escalate_ids))
        rows3, candidates3, missing3, metas3 = _classify_one_pass(
            pass3_batch,
            by_id,
            pass3_system_prompt,
            pass3_schema,
            call_3,
            max_retries,
            build_user_prompt=lambda cs: _build_user_prompt(cs, context_by_id, PASS3_NOTE),
        )
    else:
        print("  [pass 3: skipped - nothing flagged]", file=sys.stderr)

    escalated = set(escalate_ids)
    rows = [r for r in rows1 + rows2 if r["comment_id"] not in escalated] + rows3
    candidates = [
        c for c in candidates1 + candidates2 if c["comment_id"] not in escalated
    ] + candidates3
    metas = metas1 + metas2 + metas3
    return rows, candidates, sorted(missing3), metas, flag_records


def _run_legacy(
    args: argparse.Namespace,
    taxonomy: dict,
    taxonomy_block: str,
    tep_body_block: str | None,
    few_shot_examples: list[dict] | None,
    comments: list[dict],
    by_id: dict[int, dict],
    batches: list[list[dict]],
    model: str,
    call_fn,
    tag: str,
    out_dir: Path,
) -> int:
    """The original single-call (or --facet-split, one call per facet) pipeline - kept
    available for a future claude-cli cost comparison per the plan doc's Execution mode &
    backends section (fewer, larger calls may be meaningfully cheaper there than under Ollama,
    where call count doesn't cost money the same way). Not the default; see --pipeline."""
    facet_scopes: list[str | None] = (
        list(taxonomy["facets"].keys()) if args.facet_split else [None]
    )
    passes = [
        (
            facet_scope if isinstance(facet_scope, str) else "all",
            _build_system_prompt(
                taxonomy,
                taxonomy_block,
                tep_body_block,
                args.facet_coverage_threshold,
                _few_shot_examples_block(few_shot_examples, facet_scope)
                if few_shot_examples
                else None,
                facet_scope,
            ),
            _build_result_schema(taxonomy, facet_scope),
        )
        for facet_scope in facet_scopes
    ]

    if args.batch_size:
        tag += f"_batch{args.batch_size}"
    if args.facet_coverage_threshold is not None:
        tag += f"_facetcov{args.facet_coverage_threshold}"
    if args.num_ctx:
        tag += f"_numctx{args.num_ctx}"
    if args.temperature is not None:
        tag += f"_temp{args.temperature}"
    if args.few_shot:
        tag += "_fewshot"
    if args.facet_split:
        tag += "_facetsplit"

    if args.dry_run:
        print(
            f"TEP-{args.tep}: dry run (--pipeline legacy), showing pass(es) for batch "
            f"1/{len(batches)} ({len(batches[0])} of {len(comments)} comments), model={model}\n",
            file=sys.stderr,
        )
        _print_dry_run(passes, batches[0], model)
        return 0

    out_path = out_dir / f"{tag}.jsonl"
    candidates_path = out_dir / f"{tag}.candidates.jsonl"
    meta_path = out_dir / f"{tag}.meta.json"

    def _write_meta(num_batches_done: int, interrupted: bool) -> None:
        meta = {
            "pipeline": "legacy",
            "backend": args.backend,
            "model": model,
            "tep": args.tep,
            "context": args.context,
            "batch_size": args.batch_size or len(comments),
            "num_batches": len(batches),
            "num_batches_completed": num_batches_done,
            "interrupted": interrupted,
            "facet_coverage_threshold": args.facet_coverage_threshold,
            "num_ctx": args.num_ctx,
            "temperature": args.temperature,
            "few_shot": args.few_shot,
            "facet_split": args.facet_split,
            "num_comments": len(comments),
            "num_rows": len(rows),
            "num_candidates": len(candidates),
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

    print(
        f"TEP-{args.tep}: {len(comments)} comments in {len(batches)} batch(es) of up to "
        f"{args.batch_size or len(comments)}, context={args.context}, backend={args.backend}, "
        f"model={model}, pipeline=legacy\nwriting incrementally to {out_path} as each batch "
        f"completes - open it any time to check progress, or Ctrl-C to stop early and keep "
        f"what's done so far",
        file=sys.stderr,
    )

    rows: list[dict] = []
    candidates: list[dict] = []
    missing: list[int] = []
    all_metas: list[dict] = []
    batches_done = 0
    run_start = time.time()
    with out_path.open("w") as out_f, candidates_path.open("w") as cand_f:
        try:
            for i, batch in enumerate(batches, 1):
                batch_start = time.time()
                now_str = time.strftime("%H:%M:%S")
                print(
                    f"[{now_str}] batch {i}/{len(batches)} ({len(batch)} comments)...",
                    file=sys.stderr,
                )
                batch_rows, batch_candidates, batch_missing, batch_metas = _classify_batch(
                    batch,
                    by_id,
                    passes,
                    call_fn(model, None),
                    args.max_retries,
                )
                rows += batch_rows
                candidates += batch_candidates
                missing += batch_missing
                all_metas += batch_metas
                batches_done = i

                for r in batch_rows:
                    out_f.write(json.dumps(r) + "\n")
                for c in batch_candidates:
                    cand_f.write(json.dumps(c) + "\n")
                out_f.flush()
                cand_f.flush()

                batch_elapsed = time.time() - batch_start
                total_elapsed = time.time() - run_start
                remaining = len(batches) - i
                eta = (total_elapsed / i) * remaining if i else 0.0
                facet_counts = Counter(r["facet"] for r in batch_rows)
                cost = sum(m.get("cost_usd") or 0 for m in batch_metas)
                cost_str = f", ${cost:.3f}" if args.backend == "claude-cli" else ""
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
                f"rows and {len(candidates)} candidates written so far in {out_path} and "
                f"{candidates_path} (meta.json marked interrupted=true).",
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
    print(f"wrote run metadata -> {meta_path}", file=sys.stderr)
    return 0


def _run_tiered(
    args: argparse.Namespace,
    taxonomy: dict,
    taxonomy_block: str,
    tep_body_block: str | None,
    few_shot_examples: list[dict] | None,
    comments: list[dict],
    by_id: dict[int, dict],
    batches: list[list[dict]],
    model: str,
    pass3_model: str,
    think: str | None,
    pass3_think: str | None,
    principle_confidence_threshold: float,
    quote_coverage_threshold: float,
    call_fn,
    tag: str,
    out_dir: Path,
) -> int:
    """The default 3-pass pipeline (taxonomy-and-pipeline-plan.md Part 2): Pass 1 (area+nature
    together, fast model), Pass 2 (principle, same fast model, skipping nature:none comments),
    Pass 3 (thinking model, only comments either pass flagged or the quote-coverage heuristic
    flagged). See _run_tiered_batch for the per-batch mechanics."""
    pass1_scope = ["area", "nature"]
    pass2_scope = ["principle"]
    pass3_scope = list(taxonomy["facets"].keys())  # all three, explicitly - see _facet_scope_names

    def _pass(scope: list[str]) -> tuple[str, dict]:
        system_prompt = _build_system_prompt(
            taxonomy,
            taxonomy_block,
            tep_body_block,
            None,  # facet_coverage_threshold: legacy-only: each tiered pass is already scoped
            _few_shot_examples_block(few_shot_examples, scope) if few_shot_examples else None,
            scope,
        )
        return system_prompt, _build_result_schema(taxonomy, scope)

    pass1 = _pass(pass1_scope)
    pass2 = _pass(pass2_scope)
    pass3 = _pass(pass3_scope)

    call_12 = call_fn(model, think)
    call_3 = call_fn(pass3_model, pass3_think)

    pass3_model_slug = pass3_model.replace(":", "-").replace("/", "-")
    tag += (
        f"_tiered_pass3-{pass3_model_slug}_think-{think or 'off'}_pass3think-{pass3_think or 'off'}"
        f"_pconf{principle_confidence_threshold}_qcov{quote_coverage_threshold}"
    )
    if args.batch_size:
        tag += f"_batch{args.batch_size}"
    if args.num_ctx:
        tag += f"_numctx{args.num_ctx}"
    if args.temperature is not None:
        tag += f"_temp{args.temperature}"
    if args.few_shot:
        tag += "_fewshot"

    if args.dry_run:
        print(
            f"TEP-{args.tep}: dry run (--pipeline tiered), showing Pass 1/2/3 prompts for batch "
            f"1/{len(batches)} ({len(batches[0])} of {len(comments)} comments), "
            f"model={model} (pass 1-2), pass3-model={pass3_model}\nPass 3's real prompt only "
            "includes comments actually flagged at runtime - shown here against the full "
            "batch, illustratively, since nothing has run yet.\n",
            file=sys.stderr,
        )
        _print_dry_run(
            [("pass1-area-nature", pass1[0], pass1[1]), ("pass2-principle", pass2[0], pass2[1])],
            batches[0],
            model,
        )
        _print_dry_run(
            [("pass3-thinking (illustrative)", pass3[0], pass3[1])], batches[0], pass3_model
        )
        return 0

    out_path = out_dir / f"{tag}.jsonl"
    candidates_path = out_dir / f"{tag}.candidates.jsonl"
    flags_path = out_dir / f"{tag}.flags.jsonl"
    meta_path = out_dir / f"{tag}.meta.json"

    def _write_meta(num_batches_done: int, interrupted: bool) -> None:
        meta = {
            "pipeline": "tiered",
            "backend": args.backend,
            "model": model,
            "pass3_model": pass3_model,
            "think": think,
            "pass3_think": pass3_think,
            "principle_confidence_threshold": principle_confidence_threshold,
            "quote_coverage_threshold": quote_coverage_threshold,
            "tep": args.tep,
            "context": args.context,
            "batch_size": args.batch_size or len(comments),
            "num_batches": len(batches),
            "num_batches_completed": num_batches_done,
            "interrupted": interrupted,
            "num_ctx": args.num_ctx,
            "temperature": args.temperature,
            "few_shot": args.few_shot,
            "num_comments": len(comments),
            "num_rows": len(rows),
            "num_candidates": len(candidates),
            "num_escalated_to_pass3": sum(1 for f in flag_records if f["escalated_to_pass3"]),
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

    print(
        f"TEP-{args.tep}: {len(comments)} comments in {len(batches)} batch(es) of up to "
        f"{args.batch_size or len(comments)}, context={args.context}, backend={args.backend}, "
        f"pipeline=tiered, model={model} (pass 1-2), pass3-model={pass3_model}\nwriting "
        f"incrementally to {out_path} as each batch completes - open it any time to check "
        f"progress, or Ctrl-C to stop early and keep what's done so far",
        file=sys.stderr,
    )

    rows: list[dict] = []
    candidates: list[dict] = []
    missing: list[int] = []
    all_metas: list[dict] = []
    flag_records: list[dict] = []
    batches_done = 0
    run_start = time.time()
    with (
        out_path.open("w") as out_f,
        candidates_path.open("w") as cand_f,
        flags_path.open("w") as flags_f,
    ):
        try:
            for i, batch in enumerate(batches, 1):
                batch_start = time.time()
                now_str = time.strftime("%H:%M:%S")
                print(
                    f"[{now_str}] batch {i}/{len(batches)} ({len(batch)} comments)...",
                    file=sys.stderr,
                )
                batch_rows, batch_candidates, batch_missing, batch_metas, batch_flags = (
                    _run_tiered_batch(
                        batch,
                        by_id,
                        pass1,
                        pass2,
                        pass3,
                        call_12,
                        call_3,
                        args.max_retries,
                        principle_confidence_threshold,
                        quote_coverage_threshold,
                    )
                )
                rows += batch_rows
                candidates += batch_candidates
                missing += batch_missing
                all_metas += batch_metas
                flag_records += batch_flags
                batches_done = i

                for r in batch_rows:
                    out_f.write(json.dumps(r) + "\n")
                for c in batch_candidates:
                    cand_f.write(json.dumps(c) + "\n")
                for f in batch_flags:
                    flags_f.write(json.dumps(f) + "\n")
                out_f.flush()
                cand_f.flush()
                flags_f.flush()

                batch_elapsed = time.time() - batch_start
                total_elapsed = time.time() - run_start
                remaining = len(batches) - i
                eta = (total_elapsed / i) * remaining if i else 0.0
                facet_counts = Counter(r["facet"] for r in batch_rows)
                num_escalated = sum(1 for f in batch_flags if f["escalated_to_pass3"])
                cost = sum(m.get("cost_usd") or 0 for m in batch_metas)
                cost_str = f", ${cost:.3f}" if args.backend == "claude-cli" else ""
                print(
                    f"  -> {len(batch_rows)} tag(s) {dict(facet_counts)}, "
                    f"{len(batch_candidates)} candidate(s), {num_escalated}/{len(batch)} "
                    f"escalated to pass 3{cost_str} (running total: {len(rows)} tags, "
                    f"{len(candidates)} candidates) [batch took {batch_elapsed:.0f}s, elapsed "
                    f"{total_elapsed:.0f}s, ~{eta:.0f}s / {remaining} batch(es) left]",
                    file=sys.stderr,
                )
        except KeyboardInterrupt:
            _write_meta(batches_done, interrupted=True)
            print(
                f"\nInterrupted after {batches_done}/{len(batches)} batches. Kept {len(rows)} "
                f"rows and {len(candidates)} candidates written so far in {out_path} and "
                f"{candidates_path} (meta.json marked interrupted=true).",
                file=sys.stderr,
            )
            return 130
        except Exception:
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
    print(f"wrote {len(flag_records)} flag record(s) -> {flags_path}", file=sys.stderr)
    print(f"wrote run metadata -> {meta_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument("--backend", choices=["claude-cli", "ollama"], required=True)
    parser.add_argument(
        "--model",
        default=None,
        help="Backend model name. Default: 'sonnet' for claude-cli under --pipeline legacy; "
        "required for --backend ollama under --pipeline legacy; 'granite4.2:8b' under the "
        "default --pipeline tiered (Pass 1/2's model - see --pass3-model for Pass 3's).",
    )
    parser.add_argument(
        "--pass3-model",
        default=None,
        help="Model for the tiered pipeline's Pass 3 (the thinking-model re-check, run only on "
        "comments flagged by Pass 1/2 or the quote-coverage heuristic). Default "
        "'granite4.2:30b'. Only meaningful under --pipeline tiered (the default).",
    )
    parser.add_argument("--context", choices=["none", "tep-body"], default="none")
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
        help="--pipeline legacy only: ask about each of the three facets in a separate call "
        "instead of one combined call - narrower scope per call, and each call's schema "
        "requires a `reasoning` field (written before `matches`, so schema-constrained "
        "generation is forced through analysis-then-answer rather than answer-first) plus "
        "constrains the facet/value enums to just that one facet. Roughly 3x the calls per "
        "batch, so 3x the cost/time. --facet-coverage-threshold has no effect in this mode - "
        "each call already asks about exactly one facet, so 'check all three' doesn't apply. "
        "An error under --pipeline tiered (the default) - its own 3-pass structure is the "
        "modern replacement for this.",
    )
    parser.add_argument(
        "--pipeline",
        choices=["tiered", "legacy"],
        default="tiered",
        help="'tiered' (default): the 3-pass pipeline from taxonomy-and-pipeline-plan.md Part "
        "2 - Pass 1 (area+nature together), Pass 2 (principle, skipping nature:none comments, "
        "confidence-gated Pass 3 escalation), Pass 3 (thinking model, only comments either "
        "pass flagged or the quote-coverage heuristic flagged). 'legacy': the original single-"
        "call (or --facet-split) behavior, kept available for a future claude-cli cost "
        "comparison - fewer, larger calls may be meaningfully cheaper there than under Ollama, "
        "where call count doesn't cost money the same way.",
    )
    parser.add_argument(
        "--think",
        default=None,
        help="granite4.2's thinking-mode dial (Ollama /api/chat's top-level 'think' field, e.g. "
        "low/medium/high) for the tiered pipeline's Pass 1/2 calls. Default 'low' under "
        "--pipeline tiered; has no effect under --pipeline legacy or --backend claude-cli "
        "(Ollama-only).",
    )
    parser.add_argument(
        "--pass3-think",
        default=None,
        help="Same as --think, for the tiered pipeline's Pass 3 call only (typically a higher "
        "thinking level, since Pass 3's input is already filtered down to flagged comments). "
        "Default 'high' under --pipeline tiered.",
    )
    parser.add_argument(
        "--principle-confidence-threshold",
        type=float,
        default=None,
        help="--pipeline tiered only: Pass 2 escalates a comment to Pass 3 if it has a "
        "principle match below this confidence (a confident empty result needs no follow-up). "
        "Default 0.5 - not yet tuned against real data, see the plan doc's Open Questions.",
    )
    parser.add_argument(
        "--quote-coverage-threshold",
        type=float,
        default=None,
        help="--pipeline tiered only: escalate a comment to Pass 3 if more than this fraction "
        "of its text falls outside the union of its matches' `quote` spans (see "
        "uncovered_fraction), even if every match found so far was confident. Default 0.3 - "
        "not yet tuned against real data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rendered system and user prompt(s) for one example batch (the first "
        "one) and exit, without calling the backend or writing any output files - inspect "
        "exactly what a model would see before spending real budget/time on a full run.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.pipeline == "tiered" and args.facet_split:
        parser.error(
            "--facet-split has no meaning under --pipeline tiered (the 3-pass structure "
            "replaces it) - use --pipeline legacy --facet-split for the old all-three-separate "
            "behavior"
        )
    if args.backend == "claude-cli" and args.temperature is not None:
        print(
            "WARNING: --temperature has no effect on --backend claude-cli, ignoring",
            file=sys.stderr,
        )

    if args.pipeline == "legacy":
        if args.backend == "ollama" and not args.model:
            parser.error("--model is required for --backend ollama --pipeline legacy")
        model = args.model or "sonnet"
        pass3_model = ""
        think = None
        pass3_think = None
        principle_confidence_threshold = 0.0
        quote_coverage_threshold = 0.0
        if (
            args.pass3_model
            or args.think is not None
            or args.pass3_think is not None
            or args.principle_confidence_threshold is not None
            or args.quote_coverage_threshold is not None
        ):
            print(
                "WARNING: --pass3-model/--think/--pass3-think/--principle-confidence-threshold/"
                "--quote-coverage-threshold only apply to --pipeline tiered, ignoring under "
                "--pipeline legacy",
                file=sys.stderr,
            )
    else:
        model = args.model or "granite4.2:8b"
        pass3_model = args.pass3_model or "granite4.2:30b"
        think = args.think if args.think is not None else "low"
        pass3_think = args.pass3_think if args.pass3_think is not None else "high"
        principle_confidence_threshold = (
            args.principle_confidence_threshold
            if args.principle_confidence_threshold is not None
            else 0.5
        )
        quote_coverage_threshold = (
            args.quote_coverage_threshold if args.quote_coverage_threshold is not None else 0.3
        )
        if args.facet_coverage_threshold is not None:
            print(
                "WARNING: --facet-coverage-threshold has no effect under --pipeline tiered "
                "(each pass is already narrowly scoped to specific facets), ignoring",
                file=sys.stderr,
            )
        if args.backend == "claude-cli":
            print(
                "WARNING: --think/--pass3-think have no effect on --backend claude-cli "
                "(Ollama-only), ignoring",
                file=sys.stderr,
            )
            think = None
            pass3_think = None

    record = _load_tep_record(args.tep)
    comments = _comments_for(record)
    taxonomy = _load_taxonomy()
    taxonomy_block = _taxonomy_prompt_block(taxonomy)
    tep_body_block = None
    if args.context == "tep-body":
        if not args.teps_dir:
            parser.error("--context tep-body needs --teps-dir or COMMUNITY_REPO_PATH set")
        tep_body_block = _tep_body_block(record, Path(args.teps_dir).expanduser().resolve())
    few_shot_examples = _load_few_shot_examples() if args.few_shot else None

    by_id = {c["comment_id"]: c for c in comments}
    batches = _chunk(comments, args.batch_size)

    def _call(model_name: str, think_level: str | None):
        def _inner(system_prompt: str, user_prompt: str, schema: dict) -> tuple[dict, dict]:
            sp: str | None = system_prompt
            up = user_prompt
            if not _use_system_user_split(model_name):
                sp = None
                up = f"{system_prompt}\n\n{user_prompt}"
            if args.backend == "claude-cli":
                return _call_claude_cli(sp, up, model_name, args.max_budget_usd, schema)
            return _call_ollama(
                sp,
                up,
                model_name,
                args.ollama_host,
                schema,
                args.num_ctx,
                args.temperature,
                think_level,
            )

        return _inner

    out_dir = args.out_dir or Path(f"processed/tep{args.tep}")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_slug = model.replace(":", "-").replace("/", "-")
    tag = f"classify_llm_{args.backend}_{args.context}_{model_slug}"

    if args.pipeline == "tiered":
        return _run_tiered(
            args,
            taxonomy,
            taxonomy_block,
            tep_body_block,
            few_shot_examples,
            comments,
            by_id,
            batches,
            model,
            pass3_model,
            think,
            pass3_think,
            principle_confidence_threshold,
            quote_coverage_threshold,
            _call,
            tag,
            out_dir,
        )
    return _run_legacy(
        args,
        taxonomy,
        taxonomy_block,
        tep_body_block,
        few_shot_examples,
        comments,
        by_id,
        batches,
        model,
        _call,
        tag,
        out_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
