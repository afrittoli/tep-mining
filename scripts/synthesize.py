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
"""Sub-Task 7: Join raw data into per-TEP records.

Reads every raw/ file plus processed/latest/coverage.json and produces one
record per TEP: frontmatter, divergences from the canonical template, gap
status (for unmerged TEPs), coverage stats, proposal-PR review signal, and
implementation PRs (linked + discovered). This is the join layer the data
explorer reads from — see reports/explorer.html.

Usage:
    uv run scripts/synthesize.py
"""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RE_HEADING = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_section_overrides(path: Path) -> dict[tuple[str, int, int], str]:
    """(repo, pr_number, comment_id) -> human-corrected section heading."""
    overrides: dict[tuple[str, int, int], str] = {}
    for rec in _load_jsonl(path):
        key = (str(rec["repo"]), int(rec["pr_number"]), int(rec["comment_id"]))
        overrides[key] = rec["override_section"]
    return overrides


def _load_pr_attribution_overrides(path: Path) -> dict[int, list[dict]]:
    """tep_number -> [{repo, pr_number, action: 'exclude'|'include', reason}, ...]."""
    overrides: dict[int, list[dict]] = {}
    for rec in _load_jsonl(path):
        overrides.setdefault(int(rec["tep_number"]), []).append(rec)
    return overrides


# ---------------------------------------------------------------------------
# Template / section structure
# ---------------------------------------------------------------------------


def _extract_headings(text: str) -> list[str]:
    """H2/H3 headings in document order, as '## Heading' / '### Heading' strings."""
    return [("#" * len(m.group(1))) + " " + m.group(2).strip() for m in RE_HEADING.finditer(text)]


def _heading_positions(text: str) -> list[tuple[int, str]]:
    """[(line_number, heading), ...] in document order. Lines are 1-indexed."""
    positions = []
    for m in RE_HEADING.finditer(text):
        line_number = text.count("\n", 0, m.start()) + 1
        heading = ("#" * len(m.group(1))) + " " + m.group(2).strip()
        positions.append((line_number, heading))
    return positions


def _nearest_heading(line: int | None, positions: list[tuple[int, str]]) -> str | None:
    """The last heading at or before `line`. None if line is null or precedes all headings."""
    if line is None:
        return None
    result: str | None = None
    for pos_line, heading in positions:
        if pos_line <= line:
            result = heading
        else:
            break
    return result


def _is_bot(login: str | None) -> bool:
    """GitHub Apps/bots (dependabot, github-actions, github-advanced-security, ...) all get a
    login ending in "[bot]" — the one signal GitHub itself guarantees, so no allowlist to
    maintain. There's no analytical value in a bot "implementing" or "reviewing" a TEP."""
    return login is not None and login.endswith("[bot]")


def _normalize_login(value: str) -> str:
    """TEP frontmatter authors are written as free-text '@handle' (see raw/teps.jsonl); GitHub
    API logins never carry the '@'. Case varies too (a few TEPs use inconsistent casing)."""
    return value.lstrip("@").strip().casefold()


def _title_confirms_tep(title: str | None, tep_number: int) -> bool:
    """True if `title` names this TEP at/near the start (optionally wrapped in brackets, e.g.
    '[TEP-0124] ...' or 'TEP-0052: ...' — both real conventions seen in this corpus). This is
    the strongest signal a search hit is genuinely about the TEP, not a coincidental mention
    buried in a vendored changelog or dependency-bump body."""
    if not title:
        return False
    return bool(re.match(rf"^\W*TEP-0*{tep_number}\b", title, re.IGNORECASE))


def _divergences(tep_sections: list[str], template_sections: list[str]) -> dict:
    tep_set = set(tep_sections)
    template_set = set(template_sections)
    return {
        "missing_from_tep": [s for s in template_sections if s not in tep_set],
        "extra_in_tep": [s for s in tep_sections if s not in template_set],
    }


# ---------------------------------------------------------------------------
# Proposal PR (review signal)
# ---------------------------------------------------------------------------


def _proposal_pr_summary(
    pr_numbers: list[int],
    community_prs_by_number: dict[int, dict],
    review_comments: list[dict],
    heading_positions: list[tuple[int, str]],
    overrides: dict[tuple[str, int, int], str],
) -> dict:
    prs = [community_prs_by_number[n] for n in pr_numbers if n in community_prs_by_number]
    pr_authors_by_number = {
        n: community_prs_by_number[n].get("author")
        for n in pr_numbers
        if n in community_prs_by_number
    }

    comments_by_section: dict[str, int] = {}
    comments: list[dict] = []
    unmapped = 0
    dates: set[str] = set()
    for comment in review_comments:
        if comment["pr_number"] not in pr_numbers:
            continue
        if _is_bot(comment.get("author")):
            continue  # no analytical value in a bot's own review comments
        dates.add(str(comment["created_at"])[:10])
        override_key = ("community", int(comment["pr_number"]), int(comment["comment_id"]))
        is_override = override_key in overrides
        heuristic_section = _nearest_heading(comment.get("line"), heading_positions)
        section = overrides.get(override_key) or heuristic_section
        if section is None:
            unmapped += 1
        else:
            comments_by_section[section] = comments_by_section.get(section, 0) + 1
        author = comment.get("author")
        is_self_comment = bool(author) and author == pr_authors_by_number.get(comment["pr_number"])
        comments.append(
            {
                "pr_number": comment["pr_number"],
                "comment_id": comment["comment_id"],
                "author": author,
                "body": comment.get("body"),
                "path": comment.get("path"),
                "line": comment.get("line"),
                "created_at": comment.get("created_at"),
                "section": section,
                "heuristic_section": heuristic_section,
                "is_override": is_override,
                "is_self_comment": is_self_comment,
            }
        )

    reviewer_logins = sorted({login for pr in prs for login in pr.get("reviewer_logins", [])})

    return {
        "pr_numbers": pr_numbers,
        "prs": [
            {
                "pr_number": pr["pr_number"],
                "title": pr["title"],
                "created_at": pr["created_at"],
                "merged_at": pr["merged_at"],
                "reviewer_logins": pr["reviewer_logins"],
                "review_decision": pr["review_decision"],
            }
            for pr in prs
        ],
        "reviewer_logins": reviewer_logins,
        "review_comment_count": sum(comments_by_section.values()) + unmapped,
        "review_rounds_approx": len(dates),
        "comments_by_section": comments_by_section,
        "comments_unmapped": unmapped,
        "comments": comments,
    }


# ---------------------------------------------------------------------------
# Implementation PRs (linked + discovered)
# ---------------------------------------------------------------------------


def _bot_authored(pair: tuple[str, int], impl_prs_by_key: dict[tuple[str, int], dict]) -> bool:
    record = impl_prs_by_key.get(pair)
    return record is not None and _is_bot(record.get("author"))


def _search_confidence(record: dict | None, tep_number: int, tep_authors: set[str]) -> str:
    """'confirmed' if the title itself names this TEP, or (code repos only) the PR's own
    author is a listed TEP author — either signal alone is enough there. 'candidate'
    otherwise: the search text matched somewhere (title/body), but nothing ties the PR
    specifically to this TEP's own work. Two concrete failure modes this exists for: a
    dependency-bump PR in a downstream repo that happens to vendor in a commit mentioning the
    TEP, opened by neither a TEP author nor naming the TEP in its own title; and a `community`
    PR that's actually a *different* TEP's own proposal/doc PR, opened by someone who also
    happens to be a listed author of *this* TEP (common for closely related TEPs sharing an
    author) — for `community`, only the title can confirm, since authorship there says
    nothing about which TEP the PR is actually about. A PR nothing has fetched yet (or a
    genuine 404) can't be evaluated either way, so it defaults to 'candidate' — the safe,
    conservative bucket.
    """
    if record is None or record.get("status") == 404:
        return "candidate"
    if _title_confirms_tep(record.get("title"), tep_number):
        return "confirmed"
    if record.get("repo") == "community":
        return "candidate"
    author = record.get("author")
    if author and _normalize_login(author) in tep_authors:
        return "confirmed"
    return "candidate"


def _impl_pr_comments(comments_raw: list[dict], pr_author: str | None) -> list[dict]:
    """Sorted review comments for one impl PR, each flagged is_self_comment the same way
    proposal-PR comments are (bot comments are filtered out before this ever sees them, same
    as proposal-PR comments) — still collected and counted, just something the explorer can
    group/collapse rather than showing as if it were outside reviewer feedback."""
    comments = [
        {
            "comment_id": c["comment_id"],
            "author": c.get("author"),
            "body": c.get("body"),
            "path": c.get("path"),
            "line": c.get("line"),
            "created_at": c.get("created_at"),
            "is_self_comment": bool(c.get("author")) and c.get("author") == pr_author,
        }
        for c in comments_raw
    ]
    comments.sort(key=lambda c: c["created_at"] or "")
    return comments


def _impl_prs_summary(
    linked_evidence: dict[tuple[str, int], dict],
    discovered_evidence: dict[tuple[str, int], str | None],
    pr_overrides: list[dict],
    impl_prs_by_key: dict[tuple[str, int], dict],
    impl_reviews_by_key: dict[tuple[str, int], list[dict]],
    tep_number: int,
    tep_authors: set[str],
) -> dict:
    """Build the TEP's implementation-PR list, applying manual exclude/include overrides
    on top of the algorithmic link/discovery attribution. `evidence` on each item answers
    "why do we think this PR belongs to this TEP" — the linked URL+format, the search
    snippet that matched, or the human's stated reason for a manual inclusion.

    A PR the TEP author explicitly linked in their own document is trusted outright — the
    linking itself is the confirmation, regardless of who opened the linked PR (a TEP author
    commonly links a contributor's implementation). A search-discovered PR gets no such
    free pass: unless its title names the TEP or its author is a listed TEP author, it's
    parked in `candidates` — visible, but excluded from every count until a human confirms it
    (via an "include" override) or dismisses it (via "exclude", same as any other PR).
    Bot-authored PRs (dependabot, etc.) are filtered out entirely, linked or discovered alike —
    there's no human judgment call to make about those.
    """
    excluded_pairs = {(o["repo"], o["pr_number"]) for o in pr_overrides if o["action"] == "exclude"}
    include_reasons = {
        (o["repo"], o["pr_number"]): o.get("reason")
        for o in pr_overrides
        if o["action"] == "include"
    }

    bot_pairs = {
        pair
        for pair in set(linked_evidence) | set(discovered_evidence)
        if _bot_authored(pair, impl_prs_by_key)
    }

    linked_pairs = set(linked_evidence) - excluded_pairs - bot_pairs

    search_pairs = set(discovered_evidence) - excluded_pairs - bot_pairs
    confirmed_search_pairs = {
        pair
        for pair in search_pairs
        if _search_confidence(impl_prs_by_key.get(pair), tep_number, tep_authors) == "confirmed"
    }
    candidate_search_pairs = search_pairs - confirmed_search_pairs - set(include_reasons)

    discovered_pairs = confirmed_search_pairs
    manual_pairs = set(include_reasons) - linked_pairs - discovered_pairs - excluded_pairs
    all_pairs = linked_pairs | discovered_pairs | manual_pairs

    def _attribution(pair: tuple[str, int]) -> tuple[str, object]:
        if pair in linked_pairs:
            return "tep_file_link", linked_evidence.get(pair)
        if pair in discovered_pairs:
            return "search", discovered_evidence.get(pair)
        return "manual_include", include_reasons.get(pair)

    items = []
    by_repo: dict[str, int] = {}
    for repo, pr_number in sorted(all_pairs):
        attribution_source, evidence = _attribution((repo, pr_number))
        record = impl_prs_by_key.get((repo, pr_number))
        by_repo[repo] = by_repo.get(repo, 0) + 1
        comments = _impl_pr_comments(
            impl_reviews_by_key.get((repo, pr_number), []),
            record.get("author") if record else None,
        )
        base = {
            "repo": repo,
            "pr_number": pr_number,
            "attribution_source": attribution_source,
            "evidence": evidence,
            "review_comment_count": len(comments),
            "comments": comments,
        }
        if record is None or record.get("status") == 404:
            # Genuine 404 (fetched, GitHub says gone) vs. pending_fetch (a manual "include"
            # naming a PR nothing has fetched yet — run apply_pr_overrides.py) look the same
            # to a human unless distinguished explicitly.
            items.append(
                {
                    **base,
                    "title": None,
                    "review_decision": None,
                    "discovered_via": (record or {}).get("discovered_via"),
                    "status": "not_found" if record is not None else "pending_fetch",
                    "additions": None,
                    "deletions": None,
                    "files_changed": None,
                    "review_comment_count": 0,
                    "comments": [],
                }
            )
            continue
        items.append(
            {
                **base,
                "title": record["title"],
                "review_decision": record["review_decision"],
                "discovered_via": record["discovered_via"],
                "status": None,
                "additions": record["additions"],
                "deletions": record["deletions"],
                "files_changed": record["files_changed"],
            }
        )

    excluded_items = []
    for repo, pr_number in sorted(
        excluded_pairs & (set(linked_evidence) | set(discovered_evidence))
    ):
        reason = next(
            (
                o.get("reason")
                for o in pr_overrides
                if o["action"] == "exclude" and (o["repo"], o["pr_number"]) == (repo, pr_number)
            ),
            None,
        )
        excluded_items.append(
            {
                "repo": repo,
                "pr_number": pr_number,
                "was_attribution_source": "tep_file_link"
                if (repo, pr_number) in linked_evidence
                else "search",
                "reason": reason,
            }
        )

    candidates = []
    for repo, pr_number in sorted(candidate_search_pairs):
        record = impl_prs_by_key.get((repo, pr_number))
        author = record.get("author") if record else None
        why = (
            f"opened by {author}, not a listed TEP author, and the title doesn't start "
            f"with 'TEP-{tep_number:04d}'"
            if author
            else f"title doesn't start with 'TEP-{tep_number:04d}', and the PR's author isn't "
            "known yet"
        )
        candidates.append(
            {
                "repo": repo,
                "pr_number": pr_number,
                "evidence": discovered_evidence.get((repo, pr_number)),
                "why_candidate": why,
                "title": record.get("title") if record else None,
                "author": author,
                "status": (
                    "not_found"
                    if record is not None and record.get("status") == 404
                    else ("pending_fetch" if record is None else None)
                ),
                "review_decision": record.get("review_decision") if record else None,
                "additions": record.get("additions") if record else None,
                "deletions": record.get("deletions") if record else None,
                "files_changed": record.get("files_changed") if record else None,
            }
        )

    return {
        "linked_count": len(linked_pairs),
        "discovered_count": len(discovered_pairs),
        "manual_count": len(manual_pairs),
        "candidate_count": len(candidate_search_pairs),
        "bot_filtered_count": len(bot_pairs),
        "total_count": len(all_pairs),
        "review_comment_count": sum(item["review_comment_count"] for item in items),
        "by_repo": by_repo,
        "items": items,
        "excluded": excluded_items,
        "candidates": candidates,
    }


def _consistency_flags(status: str | None, impl_prs: dict) -> list[dict]:
    """Signals worth a human's attention when reviewing the data — not proof of an error, but
    exactly the kind of thing that's cheap to compute and expensive to notice by hand. Starting
    with the sharpest one: a TEP marked implemented should have *something* to show for it."""
    if status != "implemented" or impl_prs["total_count"] != 0:
        return []
    if impl_prs["candidate_count"] > 0:
        return [
            {
                "code": "implemented_only_candidates",
                "message": (
                    f"Marked implemented, but the {impl_prs['candidate_count']} impl PR(s) "
                    "found are still unconfirmed candidates"
                ),
            }
        ]
    return [
        {
            "code": "implemented_no_prs",
            "message": "Marked implemented, but no implementation PRs were found at all",
        }
    ]


# ---------------------------------------------------------------------------
# Per-TEP record
# ---------------------------------------------------------------------------


def build_tep_record(
    tep: dict,
    template_sections: list[str],
    tep_pr_map: dict,
    community_prs_by_number: dict[int, dict],
    community_pr_reviews: list[dict],
    impl_prs_by_key: dict[tuple[str, int], dict],
    impl_reviews_by_key: dict[tuple[str, int], list[dict]],
    discoveries: dict,
    gaps_by_number: dict[int, dict],
    coverage_by_number: dict[int, dict],
    section_overrides: dict[tuple[str, int, int], str],
    pr_overrides_by_tep: dict[int, list[dict]],
    heading_positions: list[tuple[int, str]],
) -> dict:
    tep_number = int(tep["tep_number"])
    sections_present = tep.get("sections_present") or []

    pr_numbers = sorted(int(n) for n in tep_pr_map.get(str(tep_number), []))
    linked_evidence = {
        (link["repo"], link["pr_number"]): {"url": link.get("url"), "format": link.get("format")}
        for link in tep.get("impl_pr_links_detail", [])
    }
    discovered_evidence = {
        (entry["repo"], entry["pr_number"]): entry.get("evidence")
        for entry in discoveries.get(str(tep_number), [])
    }
    tep_authors = {_normalize_login(a) for a in tep.get("authors", []) if a}

    status = tep.get("status")
    impl_prs = _impl_prs_summary(
        linked_evidence,
        discovered_evidence,
        pr_overrides_by_tep.get(tep_number, []),
        impl_prs_by_key,
        impl_reviews_by_key,
        tep_number,
        tep_authors,
    )

    return {
        "tep_number": tep_number,
        "title": tep.get("title"),
        "status": status,
        "authors": tep.get("authors", []),
        "collaborators": tep.get("collaborators", []),
        "creation_date": tep.get("creation_date"),
        "last_updated": tep.get("last_updated"),
        "age_days": tep.get("age_days"),
        "source_file": tep.get("source_file"),
        "stub": bool(tep.get("stub", False)),
        "sections_present": sections_present,
        "divergences_from_template": (
            _divergences(sections_present, template_sections) if sections_present else None
        ),
        "gap": gaps_by_number.get(tep_number),
        "coverage": coverage_by_number.get(tep_number),
        "flags": _consistency_flags(status, impl_prs),
        "proposal_pr": _proposal_pr_summary(
            pr_numbers,
            community_prs_by_number,
            community_pr_reviews,
            heading_positions,
            section_overrides,
        ),
        "impl_prs": impl_prs,
    }


# ---------------------------------------------------------------------------
# processed/ layer — dated snapshot + `latest` symlink
# ---------------------------------------------------------------------------


def _write_snapshot(records: list[dict], processed_dir: Path) -> Path:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    run_dir = processed_dir / date_str
    run_dir.mkdir(parents=True, exist_ok=True)

    out_path = run_dir / "per_tep_records.json"
    out_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    latest_link = processed_dir / "latest"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(date_str, target_is_directory=True)

    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Join raw data into per-TEP records")
    parser.add_argument("--teps-jsonl", default="raw/teps.jsonl")
    parser.add_argument("--tep-pr-map", default="raw/tep_pr_map.json")
    parser.add_argument("--community-prs", default="raw/community_prs.jsonl")
    parser.add_argument("--community-reviews", default="raw/community_pr_reviews.jsonl")
    parser.add_argument("--impl-prs", default="raw/impl_prs.jsonl")
    parser.add_argument("--impl-reviews", default="raw/impl_pr_reviews.jsonl")
    parser.add_argument("--discoveries", default="raw/impl_pr_discoveries.json")
    parser.add_argument("--gaps", default="raw/tep_gaps.jsonl")
    parser.add_argument("--coverage", default="processed/latest/coverage.json")
    parser.add_argument("--overrides", default="overrides/section_overrides.jsonl")
    parser.add_argument("--pr-overrides", default="overrides/pr_attribution_overrides.jsonl")
    parser.add_argument(
        "--teps-dir",
        default=(os.environ.get("COMMUNITY_REPO_PATH", "") + "/teps") or None,
        help="Path to tektoncd/community/teps/ (for the canonical template and TEP file contents)",
    )
    parser.add_argument("--processed-dir", default="processed")
    args = parser.parse_args(argv)

    teps = _load_jsonl(Path(args.teps_jsonl))
    if not teps:
        print(f"ERROR: no TEP records found in {args.teps_jsonl}", file=sys.stderr)
        return 1

    teps_dir = Path(args.teps_dir).expanduser().resolve() if args.teps_dir else None
    if not teps_dir or not teps_dir.is_dir():
        print(f"ERROR: --teps-dir not found: {teps_dir}", file=sys.stderr)
        return 1

    template_path = teps_dir / "tools" / "tep-template.md.template"
    template_sections = (
        _extract_headings(template_path.read_text(encoding="utf-8", errors="replace"))
        if template_path.exists()
        else []
    )
    if not template_sections:
        print(f"WARNING: no template sections found at {template_path}", file=sys.stderr)

    tep_pr_map = _load_json(Path(args.tep_pr_map))
    community_prs_by_number = {r["pr_number"]: r for r in _load_jsonl(Path(args.community_prs))}
    community_pr_reviews = _load_jsonl(Path(args.community_reviews))
    impl_prs_by_key = {(r["repo"], r["pr_number"]): r for r in _load_jsonl(Path(args.impl_prs))}
    impl_reviews_by_key: dict[tuple[str, int], list[dict]] = {}
    for r in _load_jsonl(Path(args.impl_reviews)):
        if _is_bot(r.get("author")):
            continue
        key = (r["repo"], r["pr_number"])
        impl_reviews_by_key.setdefault(key, []).append(r)
    discoveries = _load_json(Path(args.discoveries))
    gaps_by_number = {int(r["tep_number"]): r for r in _load_jsonl(Path(args.gaps))}
    coverage_path = Path(args.coverage)
    coverage_records = json.loads(coverage_path.read_text()) if coverage_path.exists() else []
    coverage_by_number = {int(r["tep_number"]): r for r in coverage_records}
    section_overrides = _load_section_overrides(Path(args.overrides))
    pr_overrides_by_tep = _load_pr_attribution_overrides(Path(args.pr_overrides))

    records = []
    for tep in teps:
        source_file = tep.get("source_file")
        heading_positions: list[tuple[int, str]] = []
        if source_file:
            tep_path = teps_dir / source_file
            if tep_path.exists():
                heading_positions = _heading_positions(
                    tep_path.read_text(encoding="utf-8", errors="replace")
                )

        records.append(
            build_tep_record(
                tep,
                template_sections,
                tep_pr_map,
                community_prs_by_number,
                community_pr_reviews,
                impl_prs_by_key,
                impl_reviews_by_key,
                discoveries,
                gaps_by_number,
                coverage_by_number,
                section_overrides,
                pr_overrides_by_tep,
                heading_positions,
            )
        )

    records.sort(key=lambda r: r["tep_number"])
    out_path = _write_snapshot(records, Path(args.processed_dir))

    with_impl_prs = sum(1 for r in records if r["impl_prs"]["total_count"] > 0)
    with_review_comments = sum(1 for r in records if r["proposal_pr"]["review_comment_count"] > 0)
    print("\n=== Synthesis Summary ===")
    print(f"TEP records          : {len(records)}")
    print(f"Template sections    : {len(template_sections)}")
    print(f"With implementation PRs: {with_impl_prs}")
    print(f"With review comments  : {with_review_comments}")
    print(f"Section overrides applied: {len(section_overrides)}")
    pr_override_count = sum(len(v) for v in pr_overrides_by_tep.values())
    print(f"PR attribution overrides : {pr_override_count}")
    total_candidates = sum(r["impl_prs"]["candidate_count"] for r in records)
    total_bot_filtered = sum(r["impl_prs"]["bot_filtered_count"] for r in records)
    print(f"Candidate impl PRs (unconfirmed): {total_candidates}")
    print(f"Bot-authored PRs filtered : {total_bot_filtered}")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
