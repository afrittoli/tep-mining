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
"""Generate an HTML gap report from raw/tep_gaps.jsonl and raw/teps.jsonl.

Usage:
    uv run scripts/gap_report.py
    uv run scripts/gap_report.py --gaps raw/tep_gaps.jsonl --teps raw/teps.jsonl --out reports/gap_report.html
"""

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Fate constants (must match scan_tep_gaps.py)
# ---------------------------------------------------------------------------

FATE_NEVER_ASSIGNED = "never_assigned"
FATE_CLOSED_NO_MERGE = "closed_no_merge"
FATE_OPEN_PR = "open_pr"
FATE_CONFLICT = "conflict"
FATE_RENUMBERED = "renumbered"

FATE_ORDER = [
    FATE_CONFLICT,
    FATE_OPEN_PR,
    FATE_CLOSED_NO_MERGE,
    FATE_NEVER_ASSIGNED,
    FATE_RENUMBERED,
]

FATE_BADGE = {
    FATE_NEVER_ASSIGNED: ("never assigned", "badge-skipped"),
    FATE_CLOSED_NO_MERGE: ("closed, no merge", "badge-closed"),
    FATE_OPEN_PR: ("open PR", "badge-open"),
    FATE_CONFLICT: ("conflict", "badge-conflict"),
    FATE_RENUMBERED: ("renumbered", "badge-renamed"),
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _badge(fate: str) -> str:
    label, css = FATE_BADGE.get(fate, (fate, "badge-skipped"))
    return f'<span class="badge {css}">{label}</span>'


def _pr_links(prs: list[dict]) -> str:
    if not prs:
        return "—"
    parts = []
    for p in prs:
        state = "merged" if p.get("merged") else p.get("state", "?")
        closed = (p.get("closed_at") or p.get("merged_at") or "")[:10]
        label = f"#{p['pr_number']} [{state}{', ' + closed if closed else ''}]"
        parts.append(f'<a href="{p["html_url"]}">{label}</a>')
    return " &nbsp; ".join(parts)


def _section(gaps: list[dict], fate: str) -> str:
    subset = [g for g in gaps if g["fate"] == fate]
    if not subset:
        return ""

    titles = {
        FATE_CONFLICT: "Number Conflicts — two open PRs claim the same number",
        FATE_OPEN_PR: "Open PRs — proposed but not yet merged",
        FATE_CLOSED_NO_MERGE: "Closed without merging — abandoned or superseded",
        FATE_NEVER_ASSIGNED: "Never assigned — no PR found",
        FATE_RENUMBERED: "Renumbered — old number retired, see new canonical number",
    }
    section_title = titles.get(fate, fate)

    rows = []
    for g in sorted(subset, key=lambda x: x["tep_number"]):
        n = g["tep_number"]
        prs = g.get("prs") or []
        extra = ""
        if fate == FATE_RENUMBERED:
            if g.get("renamed_from"):
                # New canonical number with PRs; show what old number it came from
                old_fmt = f"{int(g['renamed_from']):04d}"
                extra = f'<br><span class="note">renumbered from TEP-{old_fmt}</span>'
            elif g.get("renamed_to"):
                # Old number being retired; point to its successor
                new_fmt = f"{int(g['renamed_to']):04d}"
                extra = f'<br><span class="note">retired → see TEP-{new_fmt}</span>'
        elif fate == FATE_CONFLICT:
            extra = '<br><span class="note">One PR must be renumbered before merge</span>'

        # For closed PRs show the PR title as context
        suffix = ""
        if fate == FATE_CLOSED_NO_MERGE and prs:
            title_snippet = prs[0].get("title", "")
            suffix = f'<br><span class="note">{title_snippet}</span>'

        rows.append(
            f"<tr>"
            f"<td>TEP-{n:04d}</td>"
            f"<td>{_badge(fate)}</td>"
            f"<td>{_pr_links(prs)}{suffix}{extra}</td>"
            f"</tr>"
        )

    return f"""
  <h2>{section_title}</h2>
  <table>
    <thead><tr><th>TEP #</th><th>Status</th><th>PR(s) / Notes</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
"""


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------

CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 14px; line-height: 1.6;
    background: #ffffff; color: #1f2328;
    padding: 32px 16px;
  }
  .container { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .subtitle { color: #57606a; font-size: 13px; margin-bottom: 28px; }
  .summary-grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-bottom: 28px;
  }
  .card {
    background: #f7f8fa; border: 1px solid #e5e7eb;
    border-radius: 6px; padding: 14px 16px;
  }
  .card .num { font-size: 28px; font-weight: 700; color: #1f2328; }
  .card .label { font-size: 12px; color: #57606a; margin-top: 2px; }
  h2 {
    font-size: 15px; font-weight: 600;
    margin: 24px 0 10px;
    border-bottom: 1px solid #e5e7eb; padding-bottom: 6px;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th {
    background: #f7f8fa; text-align: left;
    padding: 7px 10px; font-weight: 600;
    border-bottom: 2px solid #e5e7eb;
    color: #57606a; font-size: 12px;
    text-transform: uppercase; letter-spacing: .03em;
  }
  tbody tr:nth-child(even) { background: #f7f8fa; }
  tbody td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
  .badge {
    display: inline-block; font-size: 11px;
    padding: 1px 7px; border-radius: 10px;
    font-weight: 500; white-space: nowrap;
  }
  .badge-closed   { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
  .badge-open     { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
  .badge-skipped  { background: #f7f8fa; color: #57606a; border: 1px solid #e5e7eb; }
  .badge-conflict { background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; }
  .badge-renamed  { background: #f5f3ff; color: #6d28d9; border: 1px solid #ddd6fe; }
  a { color: #3b82d4; text-decoration: none; }
  .note { font-size: 12px; color: #57606a; }
  .range-block {
    background: #f7f8fa; border: 1px solid #e5e7eb;
    border-radius: 6px; padding: 10px 14px;
    font-size: 13px; color: #57606a; margin-bottom: 8px;
  }
  .range-block span { font-weight: 600; color: #1f2328; }
  footer {
    margin-top: 40px; padding-top: 12px;
    border-top: 1px solid #e5e7eb;
    text-align: center; font-size: 12px; color: #57606a;
  }
"""


def build_report(gaps: list[dict], teps: list[dict]) -> str:
    total_range = max((g["tep_number"] for g in gaps), default=0)
    filled = sum(1 for t in teps if not t.get("stub"))
    stubs = sum(1 for t in teps if t.get("stub"))
    fate_counts = Counter(g["fate"] for g in gaps)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    summary_cards = f"""
  <div class="summary-grid">
    <div class="card"><div class="num">{filled}</div><div class="label">Merged TEP files</div></div>
    <div class="card"><div class="num">{stubs}</div><div class="label">Open PRs (stubs)</div></div>
    <div class="card"><div class="num">{len(gaps)}</div><div class="label">Gap records</div></div>
    <div class="card"><div class="num">{total_range}</div><div class="label">Highest TEP number</div></div>
  </div>
  <div class="range-block">
    <span>{filled}</span> merged files &nbsp;+&nbsp;
    <span>{fate_counts.get(FATE_CLOSED_NO_MERGE, 0)}</span> closed-no-merge &nbsp;+&nbsp;
    <span>{fate_counts.get(FATE_NEVER_ASSIGNED, 0)}</span> never assigned &nbsp;+&nbsp;
    <span>{fate_counts.get(FATE_CONFLICT, 0) + fate_counts.get(FATE_OPEN_PR, 0)}</span> open PRs
    &nbsp;+&nbsp;
    <span>{fate_counts.get(FATE_RENUMBERED, 0)}</span> renumbered
    &nbsp;=&nbsp; <span>{total_range}</span> total range
  </div>
"""

    sections = "\n".join(_section(gaps, fate) for fate in FATE_ORDER)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TEP Number Gap Report</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <h1>TEP Number Gap Report</h1>
  <p class="subtitle">Generated {generated} &mdash; source: <code>raw/tep_gaps.jsonl</code></p>
  {summary_cards}
  {sections}
  <footer>Made with IBM Bob</footer>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HTML gap report from raw/tep_gaps.jsonl")
    parser.add_argument("--gaps", default="raw/tep_gaps.jsonl")
    parser.add_argument("--teps", default="raw/teps.jsonl")
    parser.add_argument("--out", default="reports/gap_report.html")
    args = parser.parse_args(argv)

    gaps = _load_jsonl(Path(args.gaps))
    teps = _load_jsonl(Path(args.teps))

    if not gaps:
        print(f"ERROR: no gap records found in {args.gaps}", file=sys.stderr)
        print("Run 'make scan-gaps' first.", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(gaps, teps), encoding="utf-8")
    print(f"Written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
