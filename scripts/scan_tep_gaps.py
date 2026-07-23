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
"""Scan GitHub for TEP numbers that have no merged .md file.

For each TEP number in the range [1, max_tep] that is absent from
raw/teps.jsonl, this script:
  1. Searches the tektoncd/community repo for open/closed PRs whose
     title contains that TEP number.
  2. Writes a gap record to raw/tep_gaps.jsonl describing what was found.
  3. For TEP numbers that have an open (unmerged) PR, synthesises a stub
     record and appends it to raw/teps.jsonl so downstream stages have
     at least title/status/authors/proposal_pr data.

Renaming overrides (--rename N:M) are applied before any lookup so that
numbers that have been redirected (e.g. TEP-0190→0171) are tracked under
their *new* canonical number.

Usage:
    uv run scripts/scan_tep_gaps.py
    uv run scripts/scan_tep_gaps.py --max-tep 173 --rename 190:171 --rename 191:172 --rename 192:173
    uv run scripts/scan_tep_gaps.py --teps-jsonl raw/teps.jsonl --gaps-out raw/tep_gaps.jsonl
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMUNITY_REPO = "tektoncd/community"
GITHUB_API = "https://api.github.com"
RE_TEP_IN_TITLE = re.compile(r"TEP[:\s-]*0*(\d+)\b", re.IGNORECASE)

# Gap record: fate values
FATE_NEVER_ASSIGNED = "never_assigned"     # no PR found at all
FATE_CLOSED_NO_MERGE = "closed_no_merge"  # PR(s) closed without merging
FATE_OPEN_PR = "open_pr"                  # open PR(s) exist
FATE_CONFLICT = "conflict"                # multiple open PRs claiming same number
FATE_RENUMBERED = "renumbered"            # canonical number changed (--rename)

# Stub record status for open-PR TEPs
STATUS_PROPOSED = "proposed"


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def _session(token: str | None) -> requests.Session:
    s = requests.Session()
    s.headers["Accept"] = "application/vnd.github+json"
    s.headers["X-GitHub-Api-Version"] = "2022-11-28"
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def _check_rate(resp: requests.Response, threshold: int = 5) -> None:
    remaining = int(resp.headers.get("X-RateLimit-Remaining", 999))
    if remaining <= threshold:
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait = max(0, reset_ts - int(datetime.now(timezone.utc).timestamp())) + 2
        print(f"  [rate-limit] remaining={remaining}, sleeping {wait}s …", flush=True)
        time.sleep(wait)


def search_prs_for_tep(session: requests.Session, tep_number: int) -> list[dict]:
    """Search for PRs in tektoncd/community whose title contains TEP-NNNN."""
    # Use the search API; it supports both open and closed in one call
    query = f'repo:{COMMUNITY_REPO} type:pr "TEP-{tep_number:04d}" in:title'
    url = f"{GITHUB_API}/search/issues"
    params = {"q": query, "per_page": 20}
    results = []
    while url:
        resp = session.get(url, params=params)
        _check_rate(resp)
        if resp.status_code == 422:
            # Search API validation error (e.g. empty query); skip
            break
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            # Double-check the title actually mentions this number
            m = RE_TEP_IN_TITLE.search(item["title"])
            if m and int(m.group(1)) == tep_number:
                results.append({
                    "pr_number": item["number"],
                    "title": item["title"],
                    "state": item["state"],
                    "merged": item.get("pull_request", {}).get("merged_at") is not None,
                    "merged_at": item.get("pull_request", {}).get("merged_at"),
                    "closed_at": item.get("closed_at"),
                    "created_at": item.get("created_at"),
                    "html_url": item["html_url"],
                    "user": item.get("user", {}).get("login"),
                    "body_snippet": (item.get("body") or "")[:400],
                })
        # Pagination
        link = resp.headers.get("Link", "")
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
        url = next_url
        params = {}
        if next_url:
            time.sleep(0.5)  # search rate limit: 30 req/min
    return results


# ---------------------------------------------------------------------------
# Gap record builder
# ---------------------------------------------------------------------------

def _fate(prs: list[dict]) -> str:
    if not prs:
        return FATE_NEVER_ASSIGNED
    open_prs = [p for p in prs if p["state"] == "open"]
    if len(open_prs) > 1:
        return FATE_CONFLICT
    if open_prs:
        return FATE_OPEN_PR
    return FATE_CLOSED_NO_MERGE


def build_gap_record(tep_number: int, prs: list[dict],
                     renamed_from: int | None = None) -> dict:
    fate = FATE_RENUMBERED if renamed_from else _fate(prs)
    return {
        "tep_number": tep_number,
        "fate": fate,
        "renamed_from": renamed_from,
        "prs": prs,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Stub teps.jsonl record for open-PR TEPs
# ---------------------------------------------------------------------------

def _extract_authors_from_body(body: str) -> list[str]:
    """Best-effort: look for @handle mentions in the first 500 chars."""
    return re.findall(r"@([\w-]+)", body[:500])


def build_stub_tep_record(tep_number: int, prs: list[dict]) -> dict | None:
    """Build a minimal teps.jsonl record from open PR metadata."""
    open_prs = [p for p in prs if p["state"] == "open"]
    if not open_prs:
        return None
    # Use the most-recently-created open PR as canonical
    pr = sorted(open_prs, key=lambda p: p.get("created_at") or "", reverse=True)[0]
    # Extract a clean title: strip "TEP-NNNN: " prefix
    title = re.sub(
        rf"^(?:tep[:\s-]*)?0*{tep_number}[:\s-]*", "", pr["title"], flags=re.IGNORECASE
    ).strip(": ").strip()
    authors = _extract_authors_from_body(pr["body_snippet"])
    return {
        "tep_number": tep_number,
        "source_file": None,           # no .md file yet
        "title": title or pr["title"],
        "status": STATUS_PROPOSED,
        "authors": authors,
        "collaborators": [],
        "creation_date": (pr.get("created_at") or "")[:10],
        "last_updated": (pr.get("created_at") or "")[:10],
        "age_days": 0,
        "sections_present": [],
        "word_count_per_section": {},
        "impl_pr_links": [],
        "impl_pr_links_detail": [],
        # Extra context only present on stub records
        "stub": True,
        "proposal_pr_number": pr["pr_number"],
        "proposal_pr_url": pr["html_url"],
        "all_open_prs": [p["pr_number"] for p in open_prs],
    }


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> dict[int, dict]:
    existing: dict[int, dict] = {}
    if not path.exists():
        return existing
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                existing[rec["tep_number"]] = rec
            except (json.JSONDecodeError, KeyError):
                pass
    return existing


def _append_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, default=str) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan GitHub for missing TEP numbers and emit gap records"
    )
    parser.add_argument(
        "--teps-jsonl", default="raw/teps.jsonl",
        help="Path to the existing teps.jsonl (default: raw/teps.jsonl)",
    )
    parser.add_argument(
        "--gaps-out", default="raw/tep_gaps.jsonl",
        help="Output path for gap records (default: raw/tep_gaps.jsonl)",
    )
    parser.add_argument(
        "--max-tep", type=int, default=None,
        help="Highest TEP number to consider (default: max in teps.jsonl)",
    )
    parser.add_argument(
        "--rename", action="append", metavar="OLD:NEW", default=[],
        help="Apply a renumber override OLD->NEW before processing, e.g. --rename 190:171. "
             "Adds a renumbered gap record for OLD and treats NEW as the canonical number.",
    )
    parser.add_argument(
        "--token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub personal access token (default: $GITHUB_TOKEN or $GH_TOKEN)",
    )
    args = parser.parse_args(argv)

    if not args.token:
        print(
            "ERROR: No GitHub token found. Set GITHUB_TOKEN in .env or pass --token.",
            file=sys.stderr,
        )
        return 1

    teps_path = Path(args.teps_jsonl)
    gaps_path = Path(args.gaps_out)

    # Parse rename overrides: {old_number: new_number}
    renames: dict[int, int] = {}
    for spec in args.rename:
        try:
            old_s, new_s = spec.split(":")
            renames[int(old_s)] = int(new_s)
        except ValueError:
            print(f"ERROR: invalid --rename spec '{spec}' (expected OLD:NEW)", file=sys.stderr)
            return 1

    # Load existing teps records
    existing_teps = _load_jsonl(teps_path)
    existing_gaps = _load_jsonl(gaps_path)

    max_tep = args.max_tep or max(existing_teps.keys(), default=1)
    print(f"Scanning gap numbers in [1, {max_tep}] …")
    print(f"Existing teps records : {len(existing_teps)}")
    print(f"Existing gap records  : {len(existing_gaps)}")
    if renames:
        print(f"Rename overrides      : {renames}")

    # Build the set of numbers that already have a .md-backed record
    # (stub=True records don't count as "filled")
    filled = {n for n, r in existing_teps.items() if not r.get("stub")}

    # Build list of numbers to investigate
    # Include rename *targets* as potential gaps (they may not have a .md yet)
    rename_targets = set(renames.values())
    missing = sorted(
        (n for n in range(1, max_tep + 1) if n not in filled),
    )
    # Also include rename targets that may be above max_tep
    for t in rename_targets:
        if t > max_tep and t not in filled:
            missing.append(t)
    missing = sorted(set(missing))

    session = _session(args.token)
    new_gap_records: list[dict] = []
    new_stub_records: list[dict] = []
    new_rename_records: list[dict] = []

    for tep_number in missing:
        # --- Handle rename overrides (OLD number: emit renumbered record, no search) ---
        if tep_number in renames:
            new_num = renames[tep_number]
            print(f"  TEP-{tep_number:04d} → renamed to TEP-{new_num:04d} (override)")
            gap = build_gap_record(tep_number, [], renamed_from=None)
            gap["fate"] = FATE_RENUMBERED
            gap["renamed_to"] = new_num
            new_rename_records.append(gap)
            continue

        # --- Skip rename targets here; handled in the rename-target loop below ---
        if tep_number in rename_targets:
            continue

        # Skip if we already have a gap record for this number
        if tep_number in existing_gaps:
            print(f"  TEP-{tep_number:04d} — gap record already present, skipping")
            continue

        print(f"  TEP-{tep_number:04d} — searching GitHub …", end=" ", flush=True)
        prs = search_prs_for_tep(session, tep_number)
        time.sleep(2.2)  # search API: 30 req/min authenticated

        fate = _fate(prs)
        gap = build_gap_record(tep_number, prs)
        new_gap_records.append(gap)
        print(fate, f"({len(prs)} PR(s))")

        # For open-PR TEPs not already in teps.jsonl, build a stub record
        if fate in (FATE_OPEN_PR, FATE_CONFLICT) and tep_number not in existing_teps:
            stub = build_stub_tep_record(tep_number, prs)
            if stub:
                new_stub_records.append(stub)

    # --- Handle rename targets: search under the NEW number ---
    for old_num, new_num in renames.items():
        if new_num in filled:
            print(f"  TEP-{new_num:04d} (renamed from {old_num:04d}) — already in teps.jsonl")
            continue
        if new_num in existing_gaps:
            print(f"  TEP-{new_num:04d} (renamed from {old_num:04d}) — gap record already present")
            continue

        print(f"  TEP-{new_num:04d} (renamed from TEP-{old_num:04d}) — searching GitHub …",
              end=" ", flush=True)
        # Search under BOTH the old and new number since the PR title likely still has the old one
        prs_new = search_prs_for_tep(session, new_num)
        time.sleep(2.2)
        prs_old = search_prs_for_tep(session, old_num)
        time.sleep(2.2)
        # Merge, deduplicating by pr_number
        seen_pr = set()
        prs_combined = []
        for p in prs_new + prs_old:
            if p["pr_number"] not in seen_pr:
                seen_pr.add(p["pr_number"])
                prs_combined.append(p)

        fate = _fate(prs_combined)
        gap = build_gap_record(new_num, prs_combined, renamed_from=old_num)
        new_gap_records.append(gap)
        print(fate, f"({len(prs_combined)} PR(s))")

        if fate in (FATE_OPEN_PR, FATE_CONFLICT) and new_num not in existing_teps:
            stub = build_stub_tep_record(new_num, prs_combined)
            if stub:
                stub["renamed_from"] = old_num
                new_stub_records.append(stub)

    # --- Write outputs ---
    all_new_gaps = new_rename_records + new_gap_records
    if all_new_gaps:
        _append_jsonl(gaps_path, all_new_gaps)
        print(f"\nWrote {len(all_new_gaps)} gap record(s) to {gaps_path}")
    else:
        print("\nNo new gap records to write.")

    if new_stub_records:
        _append_jsonl(teps_path, new_stub_records)
        print(f"Wrote {len(new_stub_records)} stub record(s) to {teps_path}")
    else:
        print("No new stub records to write.")

    # --- Summary ---
    all_gaps = {**existing_gaps}
    for g in all_new_gaps:
        all_gaps[g["tep_number"]] = g

    fate_counts: dict[str, int] = {}
    for g in all_gaps.values():
        fate_counts[g["fate"]] = fate_counts.get(g["fate"], 0) + 1

    print(f"\n=== Gap Summary (all {len(all_gaps)} gap records) ===")
    for fate, count in sorted(fate_counts.items(), key=lambda x: -x[1]):
        print(f"  {fate:<20} {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
