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
"""Compare one or more scripts/classify_llm.py outputs against a ground-truth classify.jsonl.

Scores each candidate file's (comment_id, facet, value) tuples against the ground truth's,
set-wise - micro-averaged precision/recall/F1 across the whole file, not averaged per comment,
so comments with zero real tags (the common case) don't distort the score. Confidence and
evidence text are ignored for scoring; this measures "did it find the same tags," not "did it
phrase the justification the same way."

Usage:
    uv run scripts/compare_classifications.py --ground-truth processed/tep52/classify.jsonl \
        processed/tep52/classify_llm_claude-cli_none_sonnet.jsonl \
        processed/tep52/classify_llm_claude-cli_tep-body_sonnet.jsonl \
        processed/tep52/classify_llm_ollama_none_granite4-small-h.jsonl \
        processed/tep52/classify_llm_ollama_none_qwen2.5-32b-instruct.jsonl

    # include the audit pass's catches in the ground truth (the "complete" answer, not just
    # what a single first-pass read found - fair comparison stays classify.jsonl-only, since
    # every candidate here is also a single pass):
    uv run scripts/compare_classifications.py --ground-truth processed/tep52/classify.jsonl \
        --include-audit processed/tep52/audit.jsonl ...

    # see exactly which (comment_id, facet, value) tuples one candidate got wrong:
    uv run scripts/compare_classifications.py --ground-truth ... --show-diffs CANDIDATE.jsonl
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

Tuple3 = tuple[int, str, str]
Tuple2 = tuple[int, str]


def _load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _prf1(truth: set, candidate: set) -> tuple[float, float, float]:
    if not candidate and not truth:
        return 1.0, 1.0, 1.0
    tp = len(truth & candidate)
    precision = tp / len(candidate) if candidate else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _print_diffs(truth: set, candidate: set) -> None:
    missing = sorted(truth - candidate)
    extra = sorted(candidate - truth)
    print(f"\n  Missing ({len(missing)}) - in ground truth, candidate didn't find:")
    for comment_id, facet, value in missing:
        print(f"    comment {comment_id}: {facet}/{value}")
    print(f"\n  Extra ({len(extra)}) - candidate found, not in ground truth:")
    for comment_id, facet, value in extra:
        print(f"    comment {comment_id}: {facet}/{value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument(
        "--include-audit",
        type=Path,
        default=None,
        help="Also merge this audit.jsonl into the ground truth (the complete answer, not just "
        "one pass's)",
    )
    parser.add_argument(
        "--show-diffs",
        type=Path,
        default=None,
        help="Print the exact missing/extra tuples for this one candidate file",
    )
    parser.add_argument("candidates", nargs="+", type=Path)
    args = parser.parse_args(argv)

    truth_rows = _load_rows(args.ground_truth)
    if args.include_audit:
        truth_rows += _load_rows(args.include_audit)
    truth: set[Tuple3] = {(r["comment_id"], r["facet"], r["value"]) for r in truth_rows}
    truth_value_only: set[Tuple2] = {(r["comment_id"], r["value"]) for r in truth_rows}
    truth_facets = Counter(r["facet"] for r in truth_rows)

    print(
        f"Ground truth: {args.ground_truth}"
        + (f" + {args.include_audit}" if args.include_audit else "")
        + f" ({len(truth)} tags, facets={dict(truth_facets)})\n"
    )

    header = (
        f"{'candidate':<55} {'tags':>6} {'precision':>10} {'recall':>8} {'f1':>6} "
        f"{'val-P':>6} {'val-R':>6}"
    )
    print(header)
    print("-" * len(header))
    for path in args.candidates:
        rows = _load_rows(path)
        candidate: set[Tuple3] = {(r["comment_id"], r["facet"], r["value"]) for r in rows}
        candidate_value_only: set[Tuple2] = {(r["comment_id"], r["value"]) for r in rows}
        precision, recall, f1 = _prf1(truth, candidate)
        val_p, val_r, _ = _prf1(truth_value_only, candidate_value_only)
        print(
            f"{path.name:<55} {len(candidate):>6} {precision:>10.2f} {recall:>8.2f} "
            f"{f1:>6.2f} {val_p:>6.2f} {val_r:>6.2f}"
        )

    print(
        "\n(val-P/val-R: precision/recall on (comment_id, value) alone, ignoring facet - "
        "separates 'wrong facet label' from 'wrong content judgment')\n"
    )

    print("Facet usage (vs. ground truth's own distribution):")
    for path in args.candidates:
        facets = Counter(r["facet"] for r in _load_rows(path))
        print(f"  {path.name:<53} {dict(facets)}")

    if args.show_diffs:
        candidate = {(r["comment_id"], r["facet"], r["value"]) for r in _load_rows(args.show_diffs)}
        print(f"\n=== Diff detail: {args.show_diffs.name} ===")
        _print_diffs(truth, candidate)

    return 0


if __name__ == "__main__":
    sys.exit(main())
