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
"""Build a tabbed index page over every generated report in reports/.

Each report keeps its own standalone HTML file (so it still works when
opened directly); the index just embeds each one in an iframe behind a tab
so they can all be browsed from a single page. Reports are discovered by
scanning reports/*.html — nothing to update when a new report is added.

Usage:
    uv run scripts/build_report_index.py
    uv run scripts/build_report_index.py --reports-dir reports --out reports/index.html
"""

import argparse
import re
import sys
from pathlib import Path

RE_TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)

CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 14px; color: #1f2328; background: #ffffff;
    display: flex; flex-direction: column;
  }
  header { padding: 20px 24px 0; }
  h1 { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
  .subtitle { color: #57606a; font-size: 13px; margin-bottom: 16px; }
  .tabs {
    display: flex; gap: 4px; padding: 0 20px;
    border-bottom: 1px solid #e5e7eb; flex-wrap: wrap;
  }
  .tab {
    appearance: none; border: 1px solid transparent; border-bottom: none;
    background: transparent; cursor: pointer;
    padding: 9px 16px; font-size: 13px; font-weight: 500; color: #57606a;
    border-radius: 6px 6px 0 0;
  }
  .tab:hover { background: #f7f8fa; color: #1f2328; }
  .tab.active {
    background: #ffffff; color: #1f2328;
    border-color: #e5e7eb; border-bottom: 1px solid #ffffff;
    margin-bottom: -1px;
  }
  .panels { flex: 1; position: relative; }
  iframe {
    position: absolute; inset: 0; width: 100%; height: 100%;
    border: 0; display: none;
  }
  iframe.active { display: block; }
  .empty { padding: 40px 24px; color: #57606a; }
"""

JS = """
function showTab(id) {
  document.querySelectorAll('.tab').forEach(function (el) {
    el.classList.toggle('active', el.dataset.target === id);
  });
  document.querySelectorAll('iframe').forEach(function (el) {
    el.classList.toggle('active', el.id === id);
  });
  window.location.hash = id;
}
window.addEventListener('DOMContentLoaded', function () {
  var initial = window.location.hash.replace('#', '');
  var tabs = document.querySelectorAll('.tab');
  if (!initial || !document.getElementById(initial)) {
    initial = tabs.length ? tabs[0].dataset.target : '';
  }
  if (initial) showTab(initial);
});
"""


def _label(report_path: Path) -> str:
    text = report_path.read_text(encoding="utf-8", errors="replace")
    match = RE_TITLE.search(text)
    if match and match.group(1).strip():
        return match.group(1).strip()
    return report_path.stem.replace("_", " ").replace("-", " ").title()


def build_index(reports_dir: Path, self_name: str) -> str:
    report_files = sorted(p for p in reports_dir.glob("*.html") if p.name != self_name)

    if not report_files:
        body = '<div class="empty">No reports found in reports/. Run a fetch/report target first.</div>'
        tabs_html = ""
    else:
        tabs = []
        iframes = []
        for i, path in enumerate(report_files):
            tab_id = path.stem
            label = _label(path)
            tabs.append(
                f'<button class="tab{" active" if i == 0 else ""}" '
                f'data-target="{tab_id}" onclick="showTab(\'{tab_id}\')">{label}</button>'
            )
            iframes.append(
                f'<iframe id="{tab_id}" class="{"active" if i == 0 else ""}" '
                f'src="{path.name}" title="{label}"></iframe>'
            )
        tabs_html = f'<div class="tabs">{"".join(tabs)}</div>'
        body = f'<div class="panels">{"".join(iframes)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>tep-mining Reports</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>tep-mining Reports</h1>
  <p class="subtitle">{len(report_files)} report(s) from reports/*.html</p>
</header>
{tabs_html}
{body}
<script>{JS}</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a tabbed index over reports/*.html")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--out", default="reports/index.html")
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir)
    out_path = Path(args.out)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_path.write_text(build_index(reports_dir, out_path.name), encoding="utf-8")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
