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
"""Compare a taxonomy-rebaseline classification pass (an agent_classify_v2.jsonl produced under
the revised area/principle/nature taxonomy - see taxonomy-and-pipeline-plan.md) against a TEP's
original agent-produced ground truth, normalizing for the taxonomy's own changes so the
comparison measures actual agreement, not just the artifact->area rename.

This is a different comparison than scripts/compare_classifications.py: that script scores a
scripted model's output against ground truth under one shared taxonomy. This one scores two
ground-truth passes, written under two different taxonomy versions, against each other.

Bucketing: a comment whose normalized-old tag set exactly equals its new tag set counts as
"clean agree" and isn't surfaced further. A comment lands in "expected" only if every added tag
is a mechanical consequence of the taxonomy revision itself - `nature: none` (didn't exist
before), an `area` tag added alongside tags the comment already had (area wasn't mandatory
before), or a `nature` tag added on a comment that had zero `nature` tags before (nature wasn't
mandatory before either) - and nothing is missing. Everything else with any missing or extra
tag lands in "judgment": a real difference between the two passes worth a human look.

Usage:
    uv run scripts/compare_taxonomy_rebaseline.py --tep 52 \
        --ground-truth processed/tep52/agent_classify.jsonl \
        --include-audit processed/tep52/agent_audit.jsonl \
        --candidate processed/tep52/agent_classify_v2.jsonl \
        --repos results#103,community#347,community#357 \
        --out processed/tep52/report_full.json
"""

import argparse
import json
from pathlib import Path

MOVED_TO_PRINCIPLE = {
    "functionality",
    "incremental-delivery",
    "reconciler-pattern",
    "container-image-config",
    "approval-process",
    "tep-staging",
}
DROPPED = {"pr-size"}

Tag = tuple[str, str]


def _load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _normalize(row: dict) -> Tag | None:
    """Maps one old-taxonomy (facet, value) row onto its new-taxonomy equivalent, per
    taxonomy-and-pipeline-plan.md's Part 1. Returns None for a dropped value."""
    facet, value = row["facet"], row["value"]
    if facet == "artifact":
        if value in DROPPED:
            return None
        facet = "principle" if value in MOVED_TO_PRINCIPLE else "area"
    elif facet == "nature" and value == "structure":
        value = "formatting"
    return (facet, value)


def _comments_for_tep(records_path: Path, tep: int) -> dict[int, dict]:
    records = json.loads(records_path.read_text())
    rec = next(r for r in records if r["tep_number"] == tep)
    comments: dict[int, dict] = {}
    for c in rec["proposal_pr"]["comments"]:
        comments[c["comment_id"]] = {
            "repo": "community",
            "pr_number": c["pr_number"],
            "author": c.get("author") or "unknown",
            "loc": c.get("section") or "",
            "body": c["body"],
        }
    for pr in rec["impl_prs"]["items"]:
        for c in pr["comments"]:
            comments[c["comment_id"]] = {
                "repo": pr["repo"],
                "pr_number": pr["pr_number"],
                "author": c.get("author") or "unknown",
                "loc": c.get("path") or "",
                "body": c["body"],
            }
    return comments


def build(
    tep: int,
    ground_truth: Path,
    include_audit: Path | None,
    candidate: Path,
    records_path: Path,
    repos: list[str],
) -> dict:
    old_rows = _load_rows(ground_truth)
    if include_audit:
        old_rows += _load_rows(include_audit)
    new_rows = _load_rows(candidate)
    comments = _comments_for_tep(records_path, tep)

    old_by_cid: dict[int, set[Tag]] = {}
    for r in old_rows:
        n = _normalize(r)
        if n:
            old_by_cid.setdefault(r["comment_id"], set()).add(n)
    new_by_cid: dict[int, set[Tag]] = {}
    for r in new_rows:
        new_by_cid.setdefault(r["comment_id"], set()).add((r["facet"], r["value"]))

    all_cids = sorted(set(old_by_cid) | set(new_by_cid))
    expected: list[dict] = []
    judgment: list[dict] = []
    clean_agree = 0
    old_total = sum(len(v) for v in old_by_cid.values())
    new_total = sum(len(v) for v in new_by_cid.values())
    agree = sum(len(old_by_cid.get(c, set()) & new_by_cid.get(c, set())) for c in all_cids)

    for cid in all_cids:
        old_keys = old_by_cid.get(cid, set())
        new_keys = new_by_cid.get(cid, set())
        missing = old_keys - new_keys
        extra = new_keys - old_keys
        if not missing and not extra:
            clean_agree += 1
            continue
        old_had_nature = any(f == "nature" for f, _ in old_keys)

        def is_mechanical(fv: Tag) -> bool:
            f, v = fv
            if f == "nature" and v == "none":
                return True
            if f == "area" and old_keys:
                return True
            if f == "nature" and not old_had_nature:
                return True
            return False

        if not missing and all(is_mechanical(fv) for fv in extra):
            expected.append({"cid": cid, "extra": sorted(extra), "meta": comments.get(cid, {})})
        else:
            judgment.append(
                {
                    "cid": cid,
                    "meta": comments.get(cid, {}),
                    "old": sorted(old_keys),
                    "new": sorted(new_keys),
                    "missing": sorted(missing),
                    "extra": sorted(extra),
                }
            )

    return {
        "summary": {
            "old_total": old_total,
            "new_total": new_total,
            "agree": agree,
            "clean_agree": clean_agree,
            "total_comments": len(all_cids),
            "repos": repos,
        },
        "expected": expected,
        "judgment": judgment,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--include-audit", type=Path, default=None)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--records",
        type=Path,
        default=Path("processed/latest/per_tep_records.json"),
    )
    parser.add_argument(
        "--repos",
        required=True,
        help="Comma-separated repo#pr labels for the report footer, e.g. "
        "'results#103,community#347,community#357'",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    data = build(
        args.tep,
        args.ground_truth,
        args.include_audit,
        args.candidate,
        args.records,
        args.repos.split(","),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2))

    s = data["summary"]
    p = s["agree"] / s["new_total"] if s["new_total"] else 0.0
    r = s["agree"] / s["old_total"] if s["old_total"] else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    print(f"wrote {args.out}")
    print(
        f"old={s['old_total']} new={s['new_total']} agree={s['agree']} P={p:.3f} R={r:.3f} F1={f1:.3f}"
    )
    print(
        f"clean_agree={s['clean_agree']} expected={len(data['expected'])} judgment={len(data['judgment'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
