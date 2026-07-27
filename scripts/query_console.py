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
"""Interactive DuckDB session over every raw/processed JSONL file, for ad-hoc
SQL exploration during synthesis review (Sub-Task 7, Todo item 3).

Usage:
    uv run scripts/query_console.py
"""

import atexit
import sys
from pathlib import Path

import duckdb

# name -> (path, format). newline_delimited for JSONL, auto for a single JSON
# array/object (processed/ snapshots and raw/tep_pr_map.json aren't JSONL).
VIEWS: dict[str, tuple[str, str]] = {
    "teps": ("raw/teps.jsonl", "newline_delimited"),
    "community_prs": ("raw/community_prs.jsonl", "newline_delimited"),
    "community_pr_reviews": ("raw/community_pr_reviews.jsonl", "newline_delimited"),
    "community_pr_cache": ("raw/community_pr_cache.jsonl", "newline_delimited"),
    "impl_prs": ("raw/impl_prs.jsonl", "newline_delimited"),
    "impl_pr_reviews": ("raw/impl_pr_reviews.jsonl", "newline_delimited"),
    "tep_gaps": ("raw/tep_gaps.jsonl", "newline_delimited"),
    "tep_pr_map": ("raw/tep_pr_map.json", "auto"),
    "impl_pr_discoveries": ("raw/impl_pr_discoveries.json", "auto"),
    "coverage": ("processed/latest/coverage.json", "auto"),
    "per_tep_records": ("processed/latest/per_tep_records.json", "auto"),
}


def main(argv: list[str] | None = None) -> int:
    con = duckdb.connect()
    loaded = []
    for name, (path, fmt) in VIEWS.items():
        if not Path(path).exists():
            continue
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_json_auto('{path}', format='{fmt}')")
        loaded.append(name)

    print(f"Tables: {', '.join(loaded)}")
    print("Type SQL queries, or .quit to exit.")

    hist = Path.home() / ".duckdb_history"
    try:
        import readline

        try:
            readline.read_history_file(hist)
        except FileNotFoundError:
            pass
        atexit.register(readline.write_history_file, hist)
    except ImportError:
        pass

    while True:
        try:
            query = input("duckdb> ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip() in (".quit", ".exit", "quit", "exit"):
            break
        if query.strip():
            try:
                con.sql(query).show()
            except Exception as exc:
                print(f"Error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
