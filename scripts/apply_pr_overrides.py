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
"""Fetch metadata for manually-"included" PRs that were never linked or discovered.

overrides/pr_attribution_overrides.jsonl can name a PR that no other sub-task
ever fetched (that's exactly why a human had to add it manually). This finds
those — any "include" entry whose (repo, pr_number) isn't yet in
raw/impl_prs.jsonl — and fetches them the same way Sub-Task 5/6 do, tagged
discovered_via: "manual_override". Run this before `make synthesize` whenever
a fresh "include" override references an unknown PR; synthesize.py itself
does no network I/O and will just show such a PR as not-yet-fetched otherwise.

Usage:
    uv run scripts/apply_pr_overrides.py
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.fetch_impl_prs import (
    _append_jsonl,
    _load_existing_prs,
    _load_existing_review_comments,
    _load_jsonl,
    _session,
    fetch_one_impl_pr,
)

load_dotenv()

DISCOVERED_VIA_MANUAL = "manual_override"


def _pending_includes(
    overrides_path: Path, existing_prs: set[tuple[str, int]]
) -> list[tuple[str, int]]:
    """(repo, pr_number) pairs named by an "include" override, not yet fetched by anything."""
    pending: set[tuple[str, int]] = set()
    for rec in _load_jsonl(overrides_path):
        if rec.get("action") != "include":
            continue
        pair = (str(rec["repo"]), int(rec["pr_number"]))
        if pair not in existing_prs:
            pending.add(pair)
    return sorted(pending)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Fetch metadata for "include" overrides not yet in impl_prs.jsonl'
    )
    parser.add_argument("--overrides", default="overrides/pr_attribution_overrides.jsonl")
    parser.add_argument("--impl-prs", default="raw/impl_prs.jsonl")
    parser.add_argument("--output-reviews", default="raw/impl_pr_reviews.jsonl")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub token (default: $GITHUB_TOKEN or $GH_TOKEN)",
    )
    args = parser.parse_args(argv)

    impl_prs_path = Path(args.impl_prs)
    output_reviews_path = Path(args.output_reviews)
    existing_prs = _load_existing_prs(impl_prs_path)
    pending = _pending_includes(Path(args.overrides), existing_prs)

    if not pending:
        print('Nothing to fetch — every "include" override already has PR metadata.')
        return 0

    if not args.token:
        print(
            f"ERROR: {len(pending)} pending include(s) need fetching but no GitHub token found. "
            "Set GITHUB_TOKEN in .env or pass --token.",
            file=sys.stderr,
        )
        return 1

    existing_comments = _load_existing_review_comments(output_reviews_path)
    session = _session(args.token)
    last_logged_remaining: int | None = None

    print(f"[progress] fetching {len(pending)} manually-included PR(s)", flush=True)
    for index, (repo, pr_number) in enumerate(pending, start=1):
        print(f"[progress] {repo}#{pr_number} ({index}/{len(pending)})", flush=True)
        pr_record, review_records, last_logged_remaining = fetch_one_impl_pr(
            session, repo, pr_number, DISCOVERED_VIA_MANUAL, last_logged_remaining
        )
        _append_jsonl(impl_prs_path, [pr_record])

        new_comments = []
        for comment_record in review_records:
            key = (repo, pr_number, comment_record["comment_id"])
            if key not in existing_comments:
                new_comments.append(comment_record)
                existing_comments.add(key)
        _append_jsonl(output_reviews_path, new_comments)

    print(f"\nFetched {len(pending)} PR(s). Written: {impl_prs_path}, {output_reviews_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
