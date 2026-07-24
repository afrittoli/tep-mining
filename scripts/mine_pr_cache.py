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
"""Mine merged GitHub PR metadata into a resumable JSONL cache."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"


def _session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"
    session.headers["Authorization"] = f"Bearer {token}"
    return session


def _check_rate(resp: requests.Response, threshold: int = 5) -> None:
    remaining = int(resp.headers.get("X-RateLimit-Remaining", 999))
    if remaining <= threshold:
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait = max(0, reset_ts - int(time.time())) + 2
        print(f"[rate-limit] remaining={remaining}, sleeping {wait}s ...", flush=True)
        time.sleep(wait)


def _load_cache(path: Path) -> dict[int, dict]:
    records: dict[int, dict] = {}
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            records[int(record["pr_number"])] = record
    return records


def _write_cache(path: Path, records: dict[int, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for pr_number in sorted(records):
            handle.write(json.dumps(records[pr_number], sort_keys=True) + "\n")


def _list_closed_prs(session: requests.Session, repo: str) -> list[dict]:
    prs: list[dict] = []
    page = 1
    while True:
        params: dict[str, str | int] = {
            "state": "closed",
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }
        response = session.get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            params=params,
            timeout=30,
        )
        _check_rate(response)
        response.raise_for_status()
        items = response.json()
        if not items:
            print(f"[progress] fetched {page - 1} PR list page(s); total PRs seen: {len(prs)}")
            break
        prs.extend(items)
        print(f"[progress] fetched PR list page {page}; total PRs seen: {len(prs)}", flush=True)
        page += 1
    return prs


def _get_pr_files(session: requests.Session, repo: str, pr_number: int) -> list[str]:
    files: list[str] = []
    page = 1
    while True:
        params: dict[str, int] = {"per_page": 100, "page": page}
        response = session.get(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files",
            params=params,
            timeout=30,
        )
        _check_rate(response)
        response.raise_for_status()
        items = response.json()
        if not items:
            break
        files.extend(str(item.get("filename", "")) for item in items)
        page += 1
    return files


def _build_record(pr: dict, files: list[str]) -> dict:
    return {
        "pr_number": int(pr["number"]),
        "title": str(pr.get("title") or ""),
        "body": str(pr.get("body") or ""),
        "state": str(pr.get("state") or ""),
        "merged_at": pr.get("merged_at"),
        "updated_at": pr.get("updated_at"),
        "html_url": pr.get("html_url"),
        "labels": [
            str(label.get("name", "")) for label in pr.get("labels", []) if label.get("name")
        ],
        "files": files,
    }


def mine_pr_cache(session: requests.Session, repo: str, cache_path: Path) -> dict[int, dict]:
    cache = _load_cache(cache_path)
    closed_prs = _list_closed_prs(session, repo)
    merged_prs = [pr for pr in closed_prs if pr.get("merged_at")]

    print(
        f"[progress] starting cache refresh for {repo}; merged PRs to inspect: {len(merged_prs)}",
        flush=True,
    )

    refreshed = 0
    skipped = 0
    for index, pr in enumerate(merged_prs, start=1):
        pr_number = int(pr["number"])
        updated_at = pr.get("updated_at")
        cached = cache.get(pr_number)
        if cached and cached.get("updated_at") == updated_at and cached.get("files"):
            skipped += 1
            if skipped % 50 == 0:
                print(
                    f"[progress] reused cached data for {skipped} PR(s); latest PR #{pr_number}",
                    flush=True,
                )
            continue

        print(
            f"[progress] fetching PR #{pr_number} ({index}/{len(merged_prs)} merged PRs)",
            flush=True,
        )
        files = _get_pr_files(session, repo, pr_number)
        cache[pr_number] = _build_record(pr, files)
        refreshed += 1
        if refreshed % 25 == 0:
            _write_cache(cache_path, cache)
            print(
                f"[progress] checkpointed cache after {refreshed} refreshed PR(s)",
                flush=True,
            )

    _write_cache(cache_path, cache)
    print(
        f"[progress] cache complete: refreshed={refreshed}, reused={skipped}, total_cached={len(cache)}",
        flush=True,
    )
    return cache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mine merged GitHub PR metadata into a resumable JSONL cache"
    )
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name form")
    parser.add_argument(
        "--cache",
        required=True,
        help="Output JSONL cache path",
    )
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

    print(f"[progress] GitHub token found; starting cache mining for {args.repo}", flush=True)
    mine_pr_cache(_session(args.token), args.repo, Path(args.cache))
    return 0


if __name__ == "__main__":
    sys.exit(main())
