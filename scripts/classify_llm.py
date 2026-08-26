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
) -> tuple[list[dict], list[dict], list[int], list[dict]]:
    """One (system_prompt, schema) pass against one batch, retrying only for comment_ids it
    drops. Returns (rows, candidates, still-missing comment_ids, list of per-call metadata -
    primary call first, then retries). Used once per facet in --facet-split mode, or once
    overall otherwise - see _classify_batch."""
    user_prompt = _build_user_prompt(batch)
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
        retry_user_prompt = _build_user_prompt([by_id[c] for c in missing])
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument("--backend", choices=["claude-cli", "ollama"], required=True)
    parser.add_argument(
        "--model",
        default=None,
        help="Backend model name (default: 'sonnet' for claude-cli; required for ollama)",
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
        help="Ask about each of the three facets in a separate call instead of one combined "
        "call - narrower scope per call, and each call's schema requires a `reasoning` field "
        "(written before `matches`, so schema-constrained generation is forced through "
        "analysis-then-answer rather than answer-first) plus constrains the facet/value enums "
        "to just that one facet. Roughly 3x the calls per batch, so 3x the cost/time. "
        "--facet-coverage-threshold has no effect in this mode - each call already asks about "
        "exactly one facet, so 'check all three' doesn't apply.",
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

    if args.backend == "ollama" and not args.model:
        parser.error("--model is required for --backend ollama")
    if args.backend == "claude-cli" and args.temperature is not None:
        print(
            "WARNING: --temperature has no effect on --backend claude-cli, ignoring",
            file=sys.stderr,
        )
    model = args.model or "sonnet"

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

    # One (label, system_prompt, schema) pass per facet in --facet-split mode, or a single
    # combined pass otherwise - computed once here since none of it depends on batch content.
    # Few-shot examples are re-projected per facet_scope (see _few_shot_examples_block) since a
    # facet-scoped call needs each example sliced to just that facet, with a `reasoning` field.
    facet_scopes: list[str | None] = list(taxonomy["facets"].keys()) if args.facet_split else [None]
    passes = [
        (
            facet_scope or "all",
            _build_system_prompt(
                taxonomy,
                taxonomy_block,
                tep_body_block,
                args.facet_coverage_threshold,
                _few_shot_examples_block(few_shot_examples, facet_scope) if few_shot_examples else None,
                facet_scope,
            ),
            _build_result_schema(taxonomy, facet_scope),
        )
        for facet_scope in facet_scopes
    ]

    def _call(system_prompt: str, user_prompt: str, schema: dict) -> tuple[dict, dict]:
        sp: str | None = system_prompt
        up = user_prompt
        if not _use_system_user_split(model):
            sp = None
            up = f"{system_prompt}\n\n{user_prompt}"
        if args.backend == "claude-cli":
            return _call_claude_cli(sp, up, model, args.max_budget_usd, schema)
        return _call_ollama(
            sp,
            up,
            model,
            args.ollama_host,
            schema,
            args.num_ctx,
            args.temperature,
        )

    by_id = {c["comment_id"]: c for c in comments}
    batches = _chunk(comments, args.batch_size)

    if args.dry_run:
        print(
            f"TEP-{args.tep}: dry run, showing pass(es) for batch 1/{len(batches)} "
            f"({len(batches[0])} of {len(comments)} comments), model={model}\n",
            file=sys.stderr,
        )
        _print_dry_run(passes, batches[0], model)
        return 0

    out_dir = args.out_dir or Path(f"processed/tep{args.tep}")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"classify_llm_{args.backend}_{args.context}_{model.replace(':', '-').replace('/', '-')}"
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
    out_path = out_dir / f"{tag}.jsonl"
    candidates_path = out_dir / f"{tag}.candidates.jsonl"
    meta_path = out_dir / f"{tag}.meta.json"

    def _write_meta(num_batches_done: int, interrupted: bool) -> None:
        meta = {
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
        f"model={model}\nwriting incrementally to {out_path} as each batch completes - open it "
        f"any time to check progress, or Ctrl-C to stop early and keep what's done so far",
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
                    _call,
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


if __name__ == "__main__":
    sys.exit(main())
