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
"""Fast, throwaway harness for one classification pass - prompt wording, few-shot example
selection, temperature, batch size - without classify_llm.py's retry/write/tagging machinery.

classify_llm.py is the production pipeline: it retries dropped comment_ids, writes incremental
JSONL/meta files, and names its output after every flag in play, because a real run has to be
reproducible and auditable. None of that helps while hunting for the cheapest prompt that still
gets full facet coverage, or checking whether a given setting removes batch-size sensitivity in
one pass - it just adds ceremony between changing one variable and seeing the output. This
script reuses classify_llm's own prompt/schema/call building blocks (so the two can never drift
apart) and does the minimum around them: build one facet-scoped pass, call it (optionally
chunked into several calls over the chosen comments), print each call's raw output and timing,
done. No retries, and nothing is written to disk unless --out is given.

A configuration that looks good here still needs a real classify_llm.py run before it's
trusted: this script never retries a dropped comment_id and never writes the tagged/flags/meta
files a real run does, so a good result here means "worth trying for real," not "validated."

Usage:
    # Pass 1 (area+nature) on a hand-picked comment set at temperature 0
    uv run scripts/classify_experiment.py --tep 33 \
        --comment-ids 592407509,592408643,601841038 --temperature 0

    # same set, batch=1 vs one call for everything, to compare timing/output directly
    uv run scripts/classify_experiment.py --tep 33 --comment-ids ... --batch-size 1
    uv run scripts/classify_experiment.py --tep 33 --comment-ids ...

    # Pass 2 (principle) with only examples 1 and 7 from few_shot_examples.yaml
    uv run scripts/classify_experiment.py --tep 33 --comment-ids ... \
        --facets principle --examples 1,7

    # a hand-edited/trimmed system prompt instead of the templated one
    uv run scripts/classify_experiment.py --tep 33 --comment-ids ... \
        --system-prompt-file /tmp/trimmed_prompt.md

    # inspect what would be sent, without calling the backend
    uv run scripts/classify_experiment.py --tep 33 --comment-ids ... --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

from scripts.classify_llm import (
    _build_result_schema,
    _build_system_prompt,
    _build_user_prompt,
    _call_ollama,
    _chunk,
    _comments_for,
    _few_shot_examples_block,
    _load_few_shot_examples,
    _load_taxonomy,
    _load_tep_record,
    _taxonomy_prompt_block,
    _use_system_user_split,
)


def _print_summary(parsed: dict) -> None:
    for entry in parsed.get("results", []):
        cid = entry["comment_id"]
        reasoning = entry.get("reasoning")
        print(f"  [{cid}]" + (f" {reasoning}" if reasoning else ""))
        matches = entry.get("matches", [])
        if not matches:
            print("      (no matches)")
        for m in matches:
            print(f"      {m['facet']}/{m['value']} (conf {m['confidence']:.2f}) - {m['evidence']}")
    for cand in parsed.get("candidates", []):
        print(
            f"  [{cand['comment_id']}] CANDIDATE {cand['candidate_facet']}/"
            f"{cand['candidate_value']} - {cand['candidate_description']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument(
        "--comment-ids",
        default=None,
        help="Comma-separated comment_ids to run against. Default: every comment in the TEP.",
    )
    parser.add_argument(
        "--facets",
        default="area,nature",
        help="Comma-separated facet names to scope this pass to: 'area,nature' for a Pass-1-"
        "style call, 'principle' for Pass 2, 'area,nature,principle' for a Pass-3-style call "
        "across all three. Default: area,nature.",
    )
    parser.add_argument("--model", default="granite4.2:8b")
    parser.add_argument(
        "--think",
        default="low",
        help="Ollama think value. 'false' sends a real JSON boolean false (granite: no <think> "
        "block at all - confirmed via its Ollama chat template, the only genuine off switch). "
        "'true' sends boolean true. 'low' is the only string granite's template treats "
        "specially (appends a brevity nudge); 'medium'/'high' are accepted but are no-ops on "
        "granite - same as leaving thinking on with no nudge. Default: low.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-ctx", type=int, default=None)
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Comments per call. Default: one call for the whole --comment-ids set.",
    )
    parser.add_argument("--no-few-shot", action="store_true")
    parser.add_argument(
        "--examples",
        default=None,
        help="Comma-separated 1-indexed subset of data/few_shot_examples.yaml to include "
        "(default: all 8). Ignored with --no-few-shot.",
    )
    parser.add_argument(
        "--system-prompt-file",
        type=Path,
        default=None,
        help="Replace the rendered system prompt with this file's contents verbatim - for "
        "trying hand-edited/trimmed wording without touching system_prompt.md.j2.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Repeat each call this many times (e.g. to check temp=0 determinism, or "
        "temp>0 variance).",
    )
    parser.add_argument(
        "--raw", action="store_true", help="Also print each call's full parsed JSON response."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Append every call's {batch, repeat, meta, parsed} as one JSON line to this file, "
        "for diffing between runs later.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the system/user prompt(s) that would be sent and exit, without calling "
        "the backend.",
    )
    args = parser.parse_args(argv)

    taxonomy = _load_taxonomy()
    facet_scope = args.facets.split(",")
    unknown_facets = [f for f in facet_scope if f not in taxonomy["facets"]]
    if unknown_facets:
        parser.error(f"--facets: not in the taxonomy: {unknown_facets}")
    think: str | bool | None
    if args.think in ("false", "off"):
        think = False
    elif args.think == "true":
        think = True
    elif args.think == "none":
        think = None
    else:
        think = args.think

    record = _load_tep_record(args.tep)
    comments = _comments_for(record)
    by_id = {c["comment_id"]: c for c in comments}
    if args.comment_ids:
        wanted = [int(x) for x in args.comment_ids.split(",")]
        missing = [cid for cid in wanted if cid not in by_id]
        if missing:
            parser.error(f"--comment-ids: not found in TEP-{args.tep}: {missing}")
        chosen = [by_id[cid] for cid in wanted]
    else:
        chosen = comments

    taxonomy_block = _taxonomy_prompt_block(taxonomy)
    examples_block = None
    if not args.no_few_shot:
        examples = _load_few_shot_examples()
        if args.examples:
            idx = [int(x) for x in args.examples.split(",")]
            out_of_range = [i for i in idx if i < 1 or i > len(examples)]
            if out_of_range:
                parser.error(f"--examples: out of range 1-{len(examples)}: {out_of_range}")
            examples = [examples[i - 1] for i in idx]
        examples_block = _few_shot_examples_block(examples, facet_scope)

    if args.system_prompt_file:
        system_prompt = args.system_prompt_file.read_text(encoding="utf-8")
    else:
        system_prompt = _build_system_prompt(
            taxonomy, taxonomy_block, None, None, examples_block, facet_scope
        )
    schema = _build_result_schema(taxonomy, facet_scope)

    split = _use_system_user_split(args.model)
    sp_for_call = system_prompt if split else None

    batches = _chunk(chosen, args.batch_size)
    print(
        f"TEP-{args.tep}: {len(chosen)} comment(s) in {len(batches)} call(s) of up to "
        f"{args.batch_size or len(chosen)}, facets={facet_scope}, model={args.model}, "
        f"think={think}, temperature={args.temperature}, num_ctx={args.num_ctx}, "
        f"system_prompt={'override file' if args.system_prompt_file else 'built'} "
        f"({len(system_prompt)} chars)",
        file=sys.stderr,
    )

    if args.dry_run:
        print(f"\n----- system prompt{'' if split else ' (folded into user turn below)'} -----")
        if split:
            print(system_prompt)
        print(f"\n----- user prompt (batch 1/{len(batches)}) -----")
        up = _build_user_prompt(batches[0])
        print(up if split else f"{system_prompt}\n\n{up}")
        return 0

    out_f = args.out.open("a", encoding="utf-8") if args.out else None
    try:
        for i, batch in enumerate(batches, 1):
            batch_ids = [c["comment_id"] for c in batch]
            up = _build_user_prompt(batch)
            up_for_call = up if split else f"{system_prompt}\n\n{up}"
            for r in range(1, args.repeat + 1):
                label = f"call {i}/{len(batches)}"
                if args.repeat > 1:
                    label += f", repeat {r}/{args.repeat}"
                print(f"\n===== {label}: comment_ids={batch_ids} =====", file=sys.stderr)
                parsed, meta = _call_ollama(
                    sp_for_call,
                    up_for_call,
                    args.model,
                    args.ollama_host,
                    schema,
                    args.num_ctx,
                    args.temperature,
                    think,
                )
                seen = {e["comment_id"] for e in parsed.get("results", [])}
                dropped = [cid for cid in batch_ids if cid not in seen]
                print(
                    f"  {meta['duration_ms']}ms, eval_count={meta.get('eval_count')}, "
                    f"prompt_eval_count={meta.get('prompt_eval_count')}"
                    + (f", DROPPED: {dropped}" if dropped else ""),
                    file=sys.stderr,
                )
                _print_summary(parsed)
                if args.raw:
                    print(json.dumps(parsed, indent=2))
                if out_f:
                    out_f.write(
                        json.dumps(
                            {"batch": batch_ids, "repeat": r, "meta": meta, "parsed": parsed}
                        )
                        + "\n"
                    )
                    out_f.flush()
    finally:
        if out_f:
            out_f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
