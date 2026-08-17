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
"""Manage .claude/settings.json and .bob/settings.json together (parallel-classify-plan.md,
Sub-Task 1).

Both agents prompt for interactive approval on every shell command, file read, and file write
by default. Pre-approving exactly the operations the classify_review_comments.md /
integrate_classifications.md workflow uses removes those prompts during a parallel
classification run, while `safe` mode restores the locked-down default afterward. The two
files are always written together so they cannot drift out of sync with each other.

Usage:
    uv run scripts/manage_permissions.py --mode parallel  # pre-approve the classify workflow
    uv run scripts/manage_permissions.py --mode safe      # lock back down (no pre-approvals)
    uv run scripts/manage_permissions.py                  # status: print current state, no writes
"""

import argparse
import json
import sys
from pathlib import Path

CLAUDE_SETTINGS_PATH = Path(".claude/settings.json")
BOB_SETTINGS_PATH = Path(".bob/settings.json")

# Table from parallel-classify-plan.md, Sub-Task 1.
PARALLEL_CLAUDE_ALLOW = [
    "Bash(uv run python3 *)",
    "Bash(bash *)",
    "Bash(git *)",
    "Bash(make *)",
    "Bash(wc -l *)",
    "Bash(cat *)",
    "Bash(mkdir -p *)",
    "Read(*)",
    "Write(processed/tep*/**)",
]

PARALLEL_BOB_ALLOWED = [
    "run_shell_command(uv)",
    "run_shell_command(bash)",
    "run_shell_command(git)",
    "run_shell_command(make)",
    "run_shell_command(wc)",
    "run_shell_command(cat)",
    "run_shell_command(mkdir)",
    "write_to_file(processed/tep*)",
]


def _claude_settings(allow: list[str]) -> dict:
    return {"permissions": {"allow": allow}}


def _bob_settings(allowed: list[str]) -> dict:
    return {"tools": {"allowed": allowed}}


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_if_changed(path: Path, content: dict, label: str) -> None:
    existing = _read_json(path)
    if existing == content:
        print(f"{label} ({path}): already up to date")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    verb = "created" if existing is None else "updated"
    print(f"{label} ({path}): {verb}")


def _print_status(path: Path, label: str, allowed_key_path: tuple[str, str]) -> None:
    data = _read_json(path)
    if data is None:
        print(f"{label} ({path}): not present")
        return
    top, nested = allowed_key_path
    allowed = data.get(top, {}).get(nested, [])
    if not allowed:
        print(f"{label} ({path}): locked down (0 pre-approved operations)")
    else:
        print(f"{label} ({path}): {len(allowed)} pre-approved operation(s)")
        for entry in allowed:
            print(f"  - {entry}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage .claude/settings.json and .bob/settings.json together"
    )
    parser.add_argument(
        "--mode",
        choices=["parallel", "safe", "status"],
        default="status",
        help="parallel: pre-approve the classify workflow; safe: lock down; "
        "status (default): print current state, no writes",
    )
    args = parser.parse_args(argv)

    if args.mode == "status":
        _print_status(CLAUDE_SETTINGS_PATH, "Claude Code", ("permissions", "allow"))
        _print_status(BOB_SETTINGS_PATH, "Bob Shell", ("tools", "allowed"))
        return 0

    if args.mode == "parallel":
        claude_allow, bob_allowed = PARALLEL_CLAUDE_ALLOW, PARALLEL_BOB_ALLOWED
    else:
        claude_allow, bob_allowed = [], []

    _write_if_changed(CLAUDE_SETTINGS_PATH, _claude_settings(claude_allow), "Claude Code")
    _write_if_changed(BOB_SETTINGS_PATH, _bob_settings(bob_allowed), "Bob Shell")
    return 0


if __name__ == "__main__":
    sys.exit(main())
