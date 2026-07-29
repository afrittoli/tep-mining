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
"""Fetch TEP proposal PR metadata and review comments from tektoncd/community."""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

COMMUNITY_REPO = "tektoncd/community"
GITHUB_API = "https://api.github.com"
RATE_LIMIT_THRESHOLD = 10
RATE_LIMIT_LOG_STEP = 100


def _session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"
    session.headers["Authorization"] = f"Bearer {token}"
    # Hundreds of requests hit occasional transient connection drops and read timeouts; retry
    # those at the connection-pool level rather than failing the whole run (see the identical
    # fix in fetch_impl_prs.py's _session(), added after the same failure mode there).
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _check_rate(response: requests.Response, last_logged_remaining: int | None) -> int | None:
    remaining = int(response.headers.get("X-RateLimit-Remaining", 999))
    should_log = (
        last_logged_remaining is None
        or remaining <= RATE_LIMIT_THRESHOLD
        or remaining // RATE_LIMIT_LOG_STEP < last_logged_remaining // RATE_LIMIT_LOG_STEP
    )
    if should_log:
        print(f"[rate-limit] remaining={remaining}", flush=True)
        last_logged_remaining = remaining
    if remaining <= RATE_LIMIT_THRESHOLD:
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        wait = max(0, reset_ts - int(time.time())) + 2
        print(f"[rate-limit] sleeping {wait}s until reset", flush=True)
        time.sleep(wait)
    return last_logged_remaining


def _get_paginated(
    session: requests.Session,
    url: str,
    last_logged_remaining: int | None,
) -> tuple[list[dict], int | None]:
    items: list[dict] = []
    next_url: str | None = url
    while next_url:
        response = session.get(next_url, timeout=30)
        last_logged_remaining = _check_rate(response, last_logged_remaining)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)
        next_url = None
        link_header = response.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
                break
    return items, last_logged_remaining


def _load_json(path: Path) -> dict[str, list[int]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing_prs(path: Path) -> set[int]:
    if not path.exists():
        return set()
    existing: set[int] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            existing.add(int(record["pr_number"]))
    return existing


def _load_existing_review_comments(path: Path) -> set[tuple[int, int]]:
    if not path.exists():
        return set()
    existing: set[tuple[int, int]] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            existing.add((int(record["pr_number"]), int(record["comment_id"])))
    return existing


def _selected_pr_numbers(pr_map: dict[str, list[int]], all_teps: bool, sample: str) -> list[int]:
    if all_teps or not sample:
        selected_teps = {int(tep_number) for tep_number in pr_map}
    else:
        selected_teps = {int(item.strip()) for item in sample.split(",") if item.strip()}
    pr_numbers: set[int] = set()
    for tep_number in selected_teps:
        pr_numbers.update(int(pr_number) for pr_number in pr_map.get(str(tep_number), []))
    return sorted(pr_numbers)


def _user_login(obj: dict, field: str = "user") -> str | None:
    user = obj.get(field)
    if not isinstance(user, dict):
        return None
    login = user.get("login")
    return str(login) if login else None


def _pr_record(pr: dict, reviews: list[dict]) -> dict:
    reviewer_logins = sorted({login for review in reviews if (login := _user_login(review))})
    review_decision = "COMMENTED"
    for decision in ["CHANGES_REQUESTED", "APPROVED", "DISMISSED", "COMMENTED"]:
        if any(review.get("state") == decision for review in reviews):
            review_decision = decision
            break
    return {
        "pr_number": int(pr["number"]),
        "author": _user_login(pr),
        "title": str(pr.get("title") or ""),
        "body": str(pr.get("body") or ""),
        "labels": [
            str(label.get("name", "")) for label in pr.get("labels", []) if label.get("name")
        ],
        "created_at": pr.get("created_at"),
        "merged_at": pr.get("merged_at"),
        "state": pr.get("state"),
        "reviewer_logins": reviewer_logins,
        "review_decision": review_decision,
    }


def _review_comment_records(pr_number: int, comments: list[dict]) -> list[dict]:
    return [
        {
            "pr_number": pr_number,
            "comment_id": int(comment["id"]),
            "body": str(comment.get("body") or ""),
            "path": comment.get("path"),
            "line": comment.get("line"),
            "author": _user_login(comment),
            "created_at": comment.get("created_at"),
        }
        for comment in comments
    ]


def _append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _build_report(
    pr_records: list[dict], review_records: list[dict], selected_pr_count: int
) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    review_comments_by_pr: dict[int, int] = {}
    for review in review_records:
        pr_number = int(review["pr_number"])
        review_comments_by_pr[pr_number] = review_comments_by_pr.get(pr_number, 0) + 1

    pr_rows = []
    for record in pr_records:
        pr_number = int(record["pr_number"])
        pr_rows.append(
            "<tr>"
            f'<td><a href="https://github.com/{COMMUNITY_REPO}/pull/{pr_number}">#{pr_number}</a></td>'
            f"<td>{record['title']}</td>"
            f"<td>{record['review_decision']}</td>"
            f"<td>{', '.join(record['reviewer_logins']) or '—'}</td>"
            f"<td>{review_comments_by_pr.get(pr_number, 0)}</td>"
            "</tr>"
        )

    recent_review_rows = []
    for record in review_records[:100]:
        pr_number = int(record["pr_number"])
        recent_review_rows.append(
            "<tr>"
            f'<td><a href="https://github.com/{COMMUNITY_REPO}/pull/{pr_number}">#{pr_number}</a></td>'
            f"<td>{record['author'] or '—'}</td>"
            f"<td>{record['path'] or '—'}</td>"
            f"<td>{record['line'] if record['line'] is not None else '—'}</td>"
            f"<td>{str(record['body']).replace('<', '&lt;').replace('>', '&gt;')}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>TEP Proposal PR Review Report</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, \"Segoe UI\", system-ui, sans-serif; font-size: 14px; line-height: 1.6; background: #ffffff; color: #1f2328; padding: 32px 16px; }}
  .container {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }}
  .subtitle {{ color: #57606a; font-size: 13px; margin-bottom: 20px; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 14px 16px; }}
  .card .num {{ font-size: 28px; font-weight: 700; color: #1f2328; }}
  .card .label {{ font-size: 12px; color: #57606a; margin-top: 2px; }}
  details {{ margin-top: 16px; border: 1px solid #e5e7eb; border-radius: 6px; background: #ffffff; }}
  summary {{ cursor: pointer; list-style: none; padding: 12px 14px; font-weight: 600; background: #f7f8fa; border-bottom: 1px solid #e5e7eb; }}
  summary::-webkit-details-marker {{ display: none; }}
  .details-body {{ padding: 0 0 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ background: #f7f8fa; text-align: left; padding: 7px 10px; font-weight: 600; border-bottom: 2px solid #e5e7eb; color: #57606a; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }}
  tbody tr:nth-child(even) {{ background: #f7f8fa; }}
  tbody td {{ padding: 6px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  a {{ color: #3b82d4; text-decoration: none; }}
  footer {{ margin-top: 40px; padding-top: 12px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 12px; color: #57606a; }}
</style>
</head>
<body>
<div class=\"container\">
  <h1>TEP Proposal PR Review Report</h1>
  <p class=\"subtitle\">Generated {generated} &mdash; source: <code>raw/community_prs.jsonl</code> and <code>raw/community_pr_reviews.jsonl</code></p>
  <div class=\"summary-grid\">
    <div class=\"card\"><div class=\"num\">{selected_pr_count}</div><div class=\"label\">Selected PRs</div></div>
    <div class=\"card\"><div class=\"num\">{len(pr_records)}</div><div class=\"label\">Fetched PR records</div></div>
    <div class=\"card\"><div class=\"num\">{len(review_records)}</div><div class=\"label\">Fetched review comments</div></div>
    <div class=\"card\"><div class=\"num\">{len({review.get("author") for review in review_records if review.get("author")})}</div><div class=\"label\">Distinct comment authors</div></div>
  </div>
  <details open>
    <summary>PR records</summary>
    <div class=\"details-body\">
      <table>
        <thead><tr><th>PR</th><th>Title</th><th>Review decision</th><th>Reviewers</th><th>Comment count</th></tr></thead>
        <tbody>{"".join(pr_rows)}</tbody>
      </table>
    </div>
  </details>
  <details>
    <summary>Review comments (first 100)</summary>
    <div class=\"details-body\">
      <table>
        <thead><tr><th>PR</th><th>Author</th><th>Path</th><th>Line</th><th>Body</th></tr></thead>
        <tbody>{"".join(recent_review_rows)}</tbody>
      </table>
    </div>
  </details>
  <footer>Made with IBM Bob</footer>
</div>
</body>
</html>
"""


def _write_report(
    path: Path, pr_records: list[dict], review_records: list[dict], selected_pr_count: int
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _build_report(pr_records, review_records, selected_pr_count),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch TEP proposal PR review threads from tektoncd/community"
    )
    parser.add_argument("--pr-map", default="raw/tep_pr_map.json")
    parser.add_argument("--sample", default="")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--output-prs", default="raw/community_prs.jsonl")
    parser.add_argument("--output-reviews", default="raw/community_pr_reviews.jsonl")
    parser.add_argument("--report", default="reports/tep_pr_reviews.html")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token (default: $GITHUB_TOKEN)",
    )
    args = parser.parse_args(argv)

    if not args.token:
        print(
            "ERROR: No GitHub token found. Set GITHUB_TOKEN in .env or pass --token.",
            file=sys.stderr,
        )
        return 1

    pr_map = _load_json(Path(args.pr_map))
    if not pr_map:
        print(f"ERROR: no PR map found in {args.pr_map}", file=sys.stderr)
        return 1

    selected_prs = _selected_pr_numbers(pr_map, args.all, args.sample)
    existing_prs = _load_existing_prs(Path(args.output_prs))
    existing_comments = _load_existing_review_comments(Path(args.output_reviews))
    session = _session(args.token)

    print(f"[progress] selected {len(selected_prs)} PR(s)", flush=True)

    last_logged_remaining: int | None = None
    for index, pr_number in enumerate(selected_prs, start=1):
        print(f"[progress] fetching PR #{pr_number} ({index}/{len(selected_prs)})", flush=True)
        pr_items, last_logged_remaining = _get_paginated(
            session,
            f"{GITHUB_API}/repos/{COMMUNITY_REPO}/pulls/{pr_number}",
            last_logged_remaining,
        )
        reviews, last_logged_remaining = _get_paginated(
            session,
            f"{GITHUB_API}/repos/{COMMUNITY_REPO}/pulls/{pr_number}/reviews",
            last_logged_remaining,
        )
        comments, last_logged_remaining = _get_paginated(
            session,
            f"{GITHUB_API}/repos/{COMMUNITY_REPO}/pulls/{pr_number}/comments",
            last_logged_remaining,
        )
        pr = pr_items[0]

        pr_records_to_write: list[dict] = []
        review_records_to_write: list[dict] = []

        if pr_number not in existing_prs:
            pr_records_to_write.append(_pr_record(pr, reviews))
            existing_prs.add(pr_number)

        for comment_record in _review_comment_records(pr_number, comments):
            key = (pr_number, comment_record["comment_id"])
            if key not in existing_comments:
                review_records_to_write.append(comment_record)
                existing_comments.add(key)

        _append_jsonl(Path(args.output_prs), pr_records_to_write)
        _append_jsonl(Path(args.output_reviews), review_records_to_write)
        print(
            f"[progress] PR #{pr_number}: reviews={len(reviews)} comments={len(comments)} new_pr_records={len(pr_records_to_write)} new_comment_records={len(review_records_to_write)}",
            flush=True,
        )

    pr_records = []
    if Path(args.output_prs).exists():
        with Path(args.output_prs).open(encoding="utf-8") as handle:
            pr_records = [json.loads(line) for line in handle if line.strip()]
    review_records = []
    if Path(args.output_reviews).exists():
        with Path(args.output_reviews).open(encoding="utf-8") as handle:
            review_records = [json.loads(line) for line in handle if line.strip()]

    _write_report(Path(args.report), pr_records, review_records, len(selected_prs))

    print(f"Wrote {len(pr_records)} total PR record(s) to {args.output_prs}")
    print(f"Wrote {len(review_records)} total review comment record(s) to {args.output_reviews}")
    print(f"Written: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
