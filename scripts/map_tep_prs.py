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
"""Sub-Task 3: Discover TEP proposal PR numbers from cached GitHub PR metadata."""

import argparse
import json
import re
import sys
from pathlib import Path

RE_TEP_NUMBER = re.compile(r"\bTEP[-:\s]*0*(\d{1,4})\b", re.IGNORECASE)
RE_TEP_PATH = re.compile(r"^teps/(\d{4})-[^/]+\.md$")


def _extract_tep_numbers(text: str) -> list[int]:
    return sorted({int(match.group(1)) for match in RE_TEP_NUMBER.finditer(text)})


def _extract_tep_numbers_from_paths(paths: list[str]) -> list[int]:
    tep_numbers: set[int] = set()
    for path in paths:
        match = RE_TEP_PATH.match(path)
        if match:
            tep_numbers.add(int(match.group(1)))
    return sorted(tep_numbers)


def _load_teps(path: Path) -> dict[int, dict]:
    teps: dict[int, dict] = {}
    if not path.exists():
        return teps
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            teps[record["tep_number"]] = record
    return teps


def _load_pr_cache(path: Path) -> list[dict]:
    prs: list[dict] = []
    if not path.exists():
        return prs
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            prs.append(json.loads(line))
    return prs


def _map_pr_to_teps(pr: dict) -> tuple[list[int], dict[str, list[int] | list[str]]]:
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    labels = [str(label) for label in pr.get("labels", [])]
    files = [str(path) for path in pr.get("files", [])]
    path_teps = _extract_tep_numbers_from_paths(files)
    title_teps = _extract_tep_numbers(title)
    body_teps = _extract_tep_numbers(body)
    text_teps = sorted(set(title_teps) | set(body_teps))

    if len(path_teps) > 1 and len(title_teps) == 1 and title_teps[0] in path_teps:
        tep_numbers = title_teps
        resolution = "title_resolved_from_multi_path"
    elif len(path_teps) > 1 and len(text_teps) == 1 and text_teps[0] in path_teps:
        tep_numbers = text_teps
        resolution = "text_resolved_from_multi_path"
    elif path_teps:
        tep_numbers = path_teps
        resolution = "path"
    else:
        tep_numbers = text_teps
        resolution = "text"

    evidence: dict[str, list[int] | list[str]] = {"resolution": [resolution]}
    if path_teps:
        evidence["path_teps"] = path_teps
    if title_teps:
        evidence["title_teps"] = title_teps
    if body_teps:
        evidence["body_teps"] = body_teps
    if labels:
        evidence["labels"] = labels

    return tep_numbers, evidence


def build_pr_map(prs: list[dict]) -> tuple[dict[int, list[int]], list[dict[str, object]]]:
    pr_map: dict[int, set[int]] = {}
    unmatched: list[dict[str, object]] = []

    for pr in prs:
        if not pr.get("merged_at"):
            continue

        pr_number = int(pr["pr_number"])
        tep_numbers, evidence = _map_pr_to_teps(pr)
        if not tep_numbers:
            continue

        if len(evidence.get("path_teps", [])) > 1 and evidence.get("resolution") not in (
            ["title_resolved_from_multi_path"],
            ["text_resolved_from_multi_path"],
        ):
            unmatched.append(
                {
                    "pr_number": pr_number,
                    "title": pr.get("title"),
                    "tep_numbers": tep_numbers,
                    "reason": "multiple_tep_files_changed",
                }
            )
            continue

        for tep_number in tep_numbers:
            pr_map.setdefault(tep_number, set()).add(pr_number)

    return {
        tep_number: sorted(pr_numbers) for tep_number, pr_numbers in sorted(pr_map.items())
    }, unmatched


def merge_stub_prs(teps: dict[int, dict], pr_map: dict[int, list[int]]) -> dict[int, list[int]]:
    merged = {tep_number: list(pr_numbers) for tep_number, pr_numbers in pr_map.items()}
    for tep_number, record in teps.items():
        stub_prs = []
        if record.get("stub"):
            if record.get("proposal_pr_number"):
                stub_prs.append(int(record["proposal_pr_number"]))
            stub_prs.extend(int(pr_number) for pr_number in record.get("all_open_prs", []))
        if stub_prs:
            current = set(merged.get(tep_number, []))
            current.update(stub_prs)
            merged[tep_number] = sorted(current)
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover TEP proposal PR numbers from cached GitHub PR metadata"
    )
    parser.add_argument(
        "--cache",
        default="raw/community_pr_cache.jsonl",
        help="Path to cached PR metadata JSONL (default: raw/community_pr_cache.jsonl)",
    )
    parser.add_argument(
        "--teps-jsonl",
        default="raw/teps.jsonl",
        help="Path to teps.jsonl for cross-checking (default: raw/teps.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="raw/tep_pr_map.json",
        help="Output JSON file (default: raw/tep_pr_map.json)",
    )
    args = parser.parse_args(argv)

    prs = _load_pr_cache(Path(args.cache))
    teps = _load_teps(Path(args.teps_jsonl))
    pr_map, unmatched = build_pr_map(prs)
    pr_map = merge_stub_prs(teps, pr_map)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({str(k): v for k, v in pr_map.items()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    covered = sum(1 for tep_number in teps if tep_number in pr_map)
    missing = len(teps) - covered

    print("\n=== TEP Proposal PR Mapping Summary ===")
    print(f"Cache file          : {args.cache}")
    print(f"Output file         : {output_path}")
    print(f"TEPs with PR mapping: {covered}")
    print(f"TEPs without mapping: {missing}")
    print(f"Mapped TEP entries  : {len(pr_map)}")
    if unmatched:
        print(f"Skipped ambiguous PRs: {len(unmatched)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
