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
"""Merge an explorer-exported corrections file into the matching overrides/*.jsonl file.

The explorer's "Export as JSONL" buttons trigger a browser download instead of requiring
copy-paste out of a textarea. This script takes that downloaded file and appends its records
into the right overrides/ file — auto-detected from the record shape, since each export only
ever contains one correction type — skipping any record that's byte-for-byte already present,
so it's safe to run more than once on the same (or an overlapping) export.

Usage:
    uv run scripts/apply_export.py ~/Downloads/pr_attribution_overrides.export.jsonl
    uv run scripts/apply_export.py ~/Downloads/section_overrides.export.jsonl --target overrides/section_overrides.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

# Order matters: check the most specific shape first. known-commit and pr-attribution records
# both carry tep_number + repo, so the more specific key (commit_sha vs. pr_number+action)
# must be checked before a looser one could accidentally match.
TARGET_BY_SHAPE = [
    ({"tep_number", "repo", "commit_sha"}, "overrides/known_commits.jsonl"),
    ({"tep_number", "repo", "pr_number", "action"}, "overrides/pr_attribution_overrides.jsonl"),
    ({"repo", "pr_number", "comment_id", "override_section"}, "overrides/section_overrides.jsonl"),
]


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _detect_target(record: dict) -> str | None:
    """Which overrides/*.jsonl file a record belongs to, from its own field shape."""
    for required_keys, target in TARGET_BY_SHAPE:
        if required_keys.issubset(record.keys()):
            return target
    return None


def _merge(records: list[dict], target_path: Path) -> tuple[int, int]:
    """Append records into target_path, skipping ones already present (compared after
    normalizing key order, since browser-exported JSON and this codebase's own
    json.dumps(..., sort_keys=True) convention don't otherwise match byte-for-byte).
    Returns (appended, skipped)."""
    existing = {json.dumps(r, sort_keys=True) for r in _load_jsonl(target_path)}
    appended = 0
    skipped = 0
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("a", encoding="utf-8") as fh:
        for rec in records:
            line = json.dumps(rec, sort_keys=True)
            if line in existing:
                skipped += 1
                continue
            fh.write(line + "\n")
            existing.add(line)
            appended += 1
    return appended, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge an explorer-exported corrections file into overrides/*.jsonl"
    )
    parser.add_argument("export_file", help="Path to the downloaded *.export.jsonl file")
    parser.add_argument(
        "--target",
        default=None,
        help="Which overrides/*.jsonl file to merge into (default: auto-detect from record shape)",
    )
    args = parser.parse_args(argv)

    export_path = Path(args.export_file)
    if not export_path.exists():
        print(f"ERROR: {export_path} not found", file=sys.stderr)
        return 1

    records = _load_jsonl(export_path)
    if not records:
        print("Nothing to merge — export file is empty.")
        return 0

    by_target: dict[str, list[dict]] = {}
    for rec in records:
        target = args.target or _detect_target(rec)
        if target is None:
            print(
                f"ERROR: could not tell which overrides file this record belongs to: {rec}",
                file=sys.stderr,
            )
            return 1
        by_target.setdefault(target, []).append(rec)

    for target, recs in by_target.items():
        appended, skipped = _merge(recs, Path(target))
        print(f"{target}: appended {appended}, skipped {skipped} already-present")

    return 0


if __name__ == "__main__":
    sys.exit(main())
