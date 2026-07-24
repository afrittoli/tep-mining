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
"""Generate an HTML report for TEP proposal PR mapping results.

Usage:
    uv run scripts/pr_map_report.py
    uv run scripts/pr_map_report.py --map raw/tep_pr_map.json --teps raw/teps.jsonl --out reports/pr_map_report.html
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RENAMED_TEPS = {190: 171, 191: 172, 192: 173}


def _load_json(path: Path) -> dict[str, list[int]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _pr_links(pr_numbers: list[int]) -> str:
    if not pr_numbers:
        return "—"
    return " &nbsp; ".join(
        f'<a href="https://github.com/tektoncd/community/pull/{pr_number}">#{pr_number}</a>'
        for pr_number in pr_numbers
    )


def _explain_missing(record: dict) -> str:
    tep_number = int(record["tep_number"])
    if record.get("stub"):
        proposal_pr = record.get("proposal_pr_number")
        if proposal_pr:
            return f"Open proposal PR stub from community PR #{proposal_pr}."
        return "Open proposal stub record with no merged PR yet."
    if tep_number in RENAMED_TEPS:
        return f"Renumbered TEP. Canonical number is TEP-{RENAMED_TEPS[tep_number]:04d}."
    if record.get("source_file") == "0030-workspace-paths.md":
        return (
            "Historical direct-to-main exception. The file was introduced by commit "
            "0fd7f35761f7abee2bdff139cf30ea8d62903f03 with no associated GitHub PR."
        )
    if tep_number == 192:
        return "Open PR / renumber case. The active proposal is tracked under TEP-0173."
    return "No mined PRs found; requires manual investigation."


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
  .subtitle { color: #57606a; font-size: 13px; margin-bottom: 20px; }
  .summary-grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-bottom: 24px;
  }
  .card {
    background: #f7f8fa; border: 1px solid #e5e7eb;
    border-radius: 6px; padding: 14px 16px;
  }
  .card .num { font-size: 28px; font-weight: 700; color: #1f2328; }
  .card .label { font-size: 12px; color: #57606a; margin-top: 2px; }
  .panel {
    background: #f7f8fa; border: 1px solid #e5e7eb;
    border-radius: 6px; padding: 14px 16px; margin-bottom: 20px;
  }
  .panel h2 {
    font-size: 15px; font-weight: 600; margin-bottom: 8px;
  }
  .panel p, .panel li { font-size: 13px; color: #1f2328; }
  .panel ul { padding-left: 18px; }
  .panel li + li { margin-top: 6px; }
  details {
    margin-top: 16px;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: #ffffff;
  }
  summary {
    cursor: pointer;
    list-style: none;
    padding: 12px 14px;
    font-weight: 600;
    background: #f7f8fa;
    border-bottom: 1px solid #e5e7eb;
  }
  summary::-webkit-details-marker { display: none; }
  .details-body { padding: 0 0 4px; }
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
  .badge-match { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
  .badge-compare { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
  .badge-missing { background: #f7f8fa; color: #57606a; border: 1px solid #e5e7eb; }
  a { color: #3b82d4; text-decoration: none; }
  .note { font-size: 12px; color: #57606a; }
  .compare-type { display: block; margin-top: 4px; }
  footer {
    margin-top: 40px; padding-top: 12px;
    border-top: 1px solid #e5e7eb;
    text-align: center; font-size: 12px; color: #57606a;
  }
"""


def build_report(pr_map: dict[str, list[int]], teps: list[dict]) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    mapped_teps = {int(key): value for key, value in pr_map.items()}

    rows_mapped: list[str] = []
    rows_missing: list[str] = []
    mapped = 0
    missing = 0

    for record in sorted(teps, key=lambda item: item["tep_number"]):
        tep_number = int(record["tep_number"])
        mapped_prs = mapped_teps.get(tep_number, [])
        title = str(record.get("title") or "")
        note = "open proposal stub" if record.get("stub") else "markdown-backed TEP"

        if mapped_prs:
            mapped += 1
            rows_mapped.append(
                "<tr>"
                f'<td>TEP-{tep_number:04d}<br><span class="note">{title}</span></td>'
                f'<td><span class="badge badge-match">mapped</span><span class="note compare-type">{note}</span></td>'
                f"<td>{_pr_links(mapped_prs)}</td>"
                "</tr>"
            )
        else:
            missing += 1
            rows_missing.append(
                "<tr>"
                f'<td>TEP-{tep_number:04d}<br><span class="note">{title}</span></td>'
                f'<td><span class="badge badge-missing">missing</span><span class="note compare-type">{_explain_missing(record)}</span></td>'
                "</tr>"
            )

    summary_cards = f"""
  <div class=\"summary-grid\">
    <div class=\"card\"><div class=\"num\">{mapped}</div><div class=\"label\">TEPs with mined PR associations</div></div>
    <div class=\"card\"><div class=\"num\">{missing}</div><div class=\"label\">TEPs without mined PR associations</div></div>
    <div class=\"card\"><div class=\"num\">{sum(1 for t in teps if t.get("stub"))}</div><div class=\"label\">Open proposal stubs</div></div>
    <div class=\"card\"><div class=\"num\">{len(mapped_teps)}</div><div class=\"label\">Mapped TEP entries</div></div>
  </div>
"""

    legend = """
  <div class=\"panel\">
    <h2>How to read this report</h2>
    <ul>
      <li><strong>Mined PR associations</strong> come from <code>raw/community_pr_cache.jsonl</code> plus open proposal PR hints stored in <code>raw/teps.jsonl</code> for stub records.</li>
      <li>The mining logic associates <code>tektoncd/community</code> PRs to TEPs using changed files first, then TEP mentions in PR title/body when needed.</li>
      <li><strong>Mapped</strong> means the report found one or more associated community PRs for that TEP.</li>
      <li><strong>Missing</strong> means no associated community PR was mined for that TEP. When known, the report explains whether the case is historical, renumber-related, or otherwise exceptional.</li>
    </ul>
  </div>
"""

    mapped_section = ""
    if rows_mapped:
        mapped_section = f"""
  <details open>
    <summary>TEPs with mined PR associations ({mapped})</summary>
    <div class=\"details-body\">
      <table>
        <thead><tr><th>TEP</th><th>Status</th><th>Mined PRs</th></tr></thead>
        <tbody>{"".join(rows_mapped)}</tbody>
      </table>
    </div>
  </details>
"""

    missing_section = ""
    if rows_missing:
        missing_section = f"""
  <details>
    <summary>TEPs without mined PR associations ({missing})</summary>
    <div class=\"details-body\">
      <table>
        <thead><tr><th>TEP</th><th>Status</th></tr></thead>
        <tbody>{"".join(rows_missing)}</tbody>
      </table>
    </div>
  </details>
"""

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<title>TEP Proposal PR Mapping Report</title>
<style>{CSS}</style>
</head>
<body>
<div class=\"container\">
  <h1>TEP Proposal PR Mapping Report</h1>
  <p class=\"subtitle\">Generated {generated} &mdash; source: <code>raw/tep_pr_map.json</code></p>
  {summary_cards}
  {legend}
  {mapped_section}
  {missing_section}
  <footer>Made with IBM Bob</footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report for raw/tep_pr_map.json")
    parser.add_argument("--map", default="raw/tep_pr_map.json")
    parser.add_argument("--teps", default="raw/teps.jsonl")
    parser.add_argument("--out", default="reports/pr_map_report.html")
    args = parser.parse_args(argv)

    pr_map = _load_json(Path(args.map))
    teps = _load_jsonl(Path(args.teps))

    if not pr_map:
        print(f"ERROR: no PR mapping found in {args.map}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(pr_map, teps), encoding="utf-8")
    print(f"Written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
