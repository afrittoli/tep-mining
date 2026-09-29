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
"""Render the report_full.json comparison data scripts/compare_taxonomy_rebaseline.py produces
into a self-contained HTML report: a stat strip, a collapsed list of mechanical differences the
taxonomy revision itself explains, and full comment-text cards for every real judgment call
between the two passes.

Usage:
    uv run scripts/render_taxonomy_rebaseline.py --tep 52 \
        --data processed/tep52/report_full.json \
        --out /tmp/tep52_report.html
"""

import argparse
import html
import json
from pathlib import Path

Tag = tuple[str, str]

_TAG_CLASS = {"area": "t-area", "principle": "t-principle", "nature": "t-nature"}


def _chip(facet: str, value: str, extra_class: str = "") -> str:
    cls = f"chip {_TAG_CLASS[facet]} {extra_class}".strip()
    return f'<span class="{cls}"><b>{html.escape(facet)}</b>{html.escape(value)}</span>'


def _github_url(meta: dict, cid: int) -> str | None:
    repo = meta.get("repo", "")
    pr = meta.get("pr_number")
    if not repo or not pr or "(" in repo:
        # multi-PR footer labels like "pipeline (16 PRs)" carry no single PR to link to
        return None
    return f"https://github.com/tektoncd/{repo}/pull/{pr}#discussion_r{cid}"


def _cid_html(meta: dict, cid: int, arrow: bool = False) -> str:
    url = _github_url(meta, cid)
    if not url:
        return f'<span class="cid">#{cid}</span>'
    suffix = " &#8599;" if arrow else ""
    return f'<a class="cid" href="{url}" target="_blank" rel="noopener">#{cid}{suffix}</a>'


def _judgment_card(j: dict) -> str:
    m = j["meta"]
    loc = f" &middot; {html.escape(m['loc'])}" if m.get("loc") else ""
    body = html.escape(m["body"]).replace("\n", "<br>")
    missing_keys = {tuple(fv) for fv in j["missing"]}
    extra_keys = {tuple(fv) for fv in j["extra"]}

    def render_side(tags: list[list[str]], flagged: set[Tag]) -> str:
        chips = [_chip(f, v, "tag-flag" if (f, v) in flagged else "tag-agree") for f, v in tags]
        return "".join(chips) if chips else '<span class="chip-empty">none</span>'

    old_html = render_side(j["old"], missing_keys)
    new_html = render_side(j["new"], extra_keys)
    return f"""<article class="jcard" id="c{j["cid"]}">
  <header class="jcard-head">
    {_cid_html(m, j["cid"], arrow=True)}
    <span class="loc">{m["repo"]}#{m["pr_number"]}{loc} &middot; {html.escape(m["author"])}</span>
  </header>
  <p class="jcard-body">{body}</p>
  <div class="jcard-tags">
    <div class="tagcol"><h4>Original taxonomy</h4><div class="chips">{old_html}</div></div>
    <div class="tagcol"><h4>New taxonomy</h4><div class="chips">{new_html}</div></div>
  </div>
</article>"""


def _audit_card(a: dict) -> str:
    m = a["meta"]
    loc = f" &middot; {html.escape(m['loc'])}" if m.get("loc") else ""
    body = html.escape(m.get("body", "")).replace("\n", "<br>")
    chip = _chip(a["facet"], a["value"])
    return f"""<article class="acard">
  <header class="jcard-head">
    {_cid_html(m, a["comment_id"], arrow=True)}
    <span class="loc">{m.get("repo", "")}#{m.get("pr_number", "")}{loc} &middot; {html.escape(m.get("author", "unknown"))}</span>
  </header>
  <p class="jcard-body">{body}</p>
  <div class="audit-found">{chip}<span class="audit-conf">confidence {a["confidence"]:.2f}</span></div>
  <p class="audit-evidence">{html.escape(a["evidence"])}</p>
</article>"""


def _proposal_group(candidate_value: str, rows: list[dict]) -> str:
    first = rows[0]
    examples = []
    for p in rows:
        m = p["meta"]
        examples.append(
            f'<div class="proposal-example">'
            f"{_cid_html(m, p['comment_id'], arrow=True)} "
            f'<span class="proposal-fragment">&ldquo;{html.escape(p["fragment"])}&rdquo;</span>'
            f"</div>"
        )
    return f"""<article class="acard pcard">
  <div class="proposal-head"><b>{html.escape(first["candidate_facet"])}</b>{html.escape(candidate_value)}<span class="count-badge">{len(rows)} example{"s" if len(rows) != 1 else ""}</span></div>
  <p class="proposal-desc">{html.escape(first["candidate_description"])}</p>
  {"".join(examples)}
</article>"""


def _expected_row(e: dict) -> str:
    m = e["meta"]
    tags = ", ".join(f"{f}:{v}" for f, v in e["extra"])
    body = m.get("body", "")
    snippet = html.escape(body[:70].replace("\n", " ")) + ("…" if len(body) > 70 else "")
    return (
        f"<li>{_cid_html(m, e['cid'])} "
        f'<span class="ex-snippet">{snippet}</span> '
        f'<span class="ex-tags">+{html.escape(tags)}</span></li>'
    )


def render(tep: int, data: dict) -> str:
    judgment = data["judgment"]
    expected = data["expected"]
    v2_audit = data.get("v2_audit", [])
    v2_proposals = data.get("v2_proposals", [])
    s = data["summary"]
    old_total, new_total, agree = s["old_total"], s["new_total"], s["agree"]
    precision = agree / new_total if new_total else 0.0
    recall = agree / old_total if old_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    judgment_html = "\n".join(_judgment_card(j) for j in judgment)
    expected_html = "\n".join(_expected_row(e) for e in expected)
    audit_html = "\n".join(_audit_card(a) for a in v2_audit)
    proposal_groups: dict[str, list[dict]] = {}
    for p in v2_proposals:
        proposal_groups.setdefault(p["candidate_value"], []).append(p)
    proposals_html = "\n".join(_proposal_group(cv, rows) for cv, rows in proposal_groups.items())
    audit_section = ""
    if v2_audit or v2_proposals:
        audit_section = f"""
  <section>
    <h2>Audit findings</h2>
    <p class="section-note">A second, separate pass over the rebaseline's own no-principle comments (prompts/audit_classification_coverage.md), not a comparison against the old ground truth - these are gaps within the new pass alone.</p>
    {f'<h3 class="audit-subhead">Missed matches <span class="count-badge">{len(v2_audit)}</span></h3><div class="jcards">{audit_html}</div>' if v2_audit else ""}
    {f'<h3 class="audit-subhead">Taxonomy gaps <span class="count-badge">{len(proposal_groups)}</span></h3><div class="jcards">{proposals_html}</div>' if v2_proposals else ""}
  </section>"""

    return f"""<title>TEP-{tep} Taxonomy Rebaseline</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&family=Source+Sans+3:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper: #f3f1ec;
    --surface: #ffffff;
    --ink: #211f1a;
    --ink-dim: #726c5c;
    --line: #ddd8ca;
    --accent: #2d5c56;
    --accent-dim: #4f8078;
    --match: #3f7d4f;
    --match-bg: #e7f2e9;
    --old-only: #a63d33;
    --old-only-bg: #f8e9e7;
    --new-only: #9c6b1f;
    --new-only-bg: #f6eedc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --paper: #15140f;
      --surface: #1c1a15;
      --ink: #eae7de;
      --ink-dim: #a39a86;
      --line: #332f22;
      --accent: #7fbdb3;
      --accent-dim: #5f978e;
      --match: #7ad696;
      --match-bg: #16301f;
      --old-only: #e8897c;
      --old-only-bg: #33201b;
      --new-only: #e6ae54;
      --new-only-bg: #332a13;
      color-scheme: dark;
    }}
  }}
  :root[data-theme="dark"] {{
    --paper: #15140f;
    --surface: #1c1a15;
    --ink: #eae7de;
    --ink-dim: #a39a86;
    --line: #332f22;
    --accent: #7fbdb3;
    --accent-dim: #5f978e;
    --match: #7ad696;
    --match-bg: #16301f;
    --old-only: #e8897c;
    --old-only-bg: #33201b;
    --new-only: #e6ae54;
    --new-only-bg: #332a13;
    color-scheme: dark;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: "Source Sans 3", -apple-system, sans-serif;
    font-size: 16px;
    line-height: 1.55;
    padding-inline: 16px;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding-block: 3rem 6rem; }}

  h1, h2, h3, h4 {{ font-family: "Source Serif 4", Georgia, serif; text-wrap: balance; margin: 0; }}
  h1 {{ font-size: 2rem; font-weight: 700; letter-spacing: -0.01em; }}
  .subtitle {{ color: var(--ink-dim); font-size: 1rem; margin-top: 0.5rem; max-width: 60ch; }}
  .meta-line {{ font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: var(--ink-dim); margin-top: 1rem; }}

  .stats {{ display: flex; flex-wrap: wrap; gap: 0.7rem; margin: 2rem 0; }}
  .stat {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem 1rem; flex: 1 1 100px; }}
  .stat .label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-dim); }}
  .stat .value {{ font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; font-size: 1.4rem; color: var(--accent); margin-top: 0.2rem; }}

  section {{ margin-top: 3rem; }}
  section > h2 {{ font-size: 1.35rem; margin-bottom: 0.5rem; }}
  .section-note {{ color: var(--ink-dim); font-size: 0.92rem; max-width: 62ch; margin-bottom: 1.5rem; }}

  .agree-note {{
    border-left: 3px solid var(--match);
    background: var(--match-bg);
    border-radius: 0 8px 8px 0;
    padding: 0.9rem 1.1rem;
    font-size: 0.92rem;
  }}
  .agree-note b {{ font-family: "IBM Plex Mono", monospace; color: var(--match); }}

  details.expected-details {{ margin: 0; }}
  details.expected-details summary {{
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }}
  details.expected-details summary::-webkit-details-marker {{ display: none; }}
  details.expected-details summary::before {{
    content: "▸";
    color: var(--ink-dim);
    font-size: 0.85rem;
    transition: transform 0.15s ease;
  }}
  details.expected-details[open] summary::before {{ transform: rotate(90deg); }}
  details.expected-details summary h2 {{ display: inline; }}
  .count-badge {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.78rem;
    font-weight: 400;
    color: var(--ink-dim);
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.1rem 0.55rem;
    margin-left: 0.5rem;
  }}
  details.expected-details .section-note {{ margin-top: 0.8rem; }}
  details.expected-details ul.expected-list {{ margin-top: 1rem; }}

  ul.expected-list {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }}
  ul.expected-list li {{
    font-size: 0.86rem;
    padding: 0.5rem 0.8rem;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 6px;
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    align-items: baseline;
  }}
  .cid {{ font-family: "IBM Plex Mono", monospace; color: var(--accent-dim); font-size: 0.82rem; flex-shrink: 0; }}
  a.cid {{ text-decoration: none; }}
  a.cid:hover {{ text-decoration: underline; }}
  .jcard-head a.cid {{ font-size: 0.78rem; }}
  .ex-snippet {{ color: var(--ink-dim); flex: 1 1 240px; }}
  .ex-tags {{ font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: var(--new-only); }}

  .jcards {{ display: flex; flex-direction: column; gap: 1.1rem; }}
  .jcard {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1.2rem 1.35rem; }}
  .jcard-head {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.4rem; font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: var(--ink-dim); margin-bottom: 0.7rem; }}
  .jcard-body {{ margin: 0 0 1.1rem; font-size: 0.95rem; max-width: 66ch; }}
  .jcard-tags {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; }}
  @media (max-width: 560px) {{ .jcard-tags {{ grid-template-columns: 1fr; }} }}
  .tagcol h4 {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dim); margin-bottom: 0.5rem; }}
  .chips {{ display: flex; flex-direction: column; gap: 0.4rem; }}
  .chip {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.8rem;
    padding: 0.35rem 0.6rem;
    border-radius: 6px;
    border: 1px solid var(--line);
    display: flex;
    gap: 0.5rem;
  }}
  .chip b {{ font-weight: 500; color: var(--ink-dim); font-style: normal; min-width: 4.8em; }}
  .chip-empty {{ font-size: 0.82rem; color: var(--ink-dim); font-style: italic; }}
  .tag-agree {{ background: var(--match-bg); border-color: color-mix(in srgb, var(--match) 35%, var(--line)); }}
  .jcard-tags .tagcol:first-child .tag-flag {{ background: var(--old-only-bg); border-color: color-mix(in srgb, var(--old-only) 35%, var(--line)); }}
  .jcard-tags .tagcol:last-child .tag-flag {{ background: var(--new-only-bg); border-color: color-mix(in srgb, var(--new-only) 35%, var(--line)); }}

  .audit-subhead {{ font-size: 1.05rem; margin: 1.8rem 0 0.8rem; display: flex; align-items: baseline; gap: 0.5rem; }}
  .audit-subhead:first-of-type {{ margin-top: 0; }}

  .acard {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 1.2rem 1.35rem; }}
  .audit-found {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }}
  .audit-found .chip {{ background: var(--new-only-bg); border-color: color-mix(in srgb, var(--new-only) 35%, var(--line)); }}
  .audit-conf {{ font-family: "IBM Plex Mono", monospace; font-size: 0.78rem; color: var(--ink-dim); }}
  .audit-evidence {{ font-size: 0.86rem; color: var(--ink-dim); font-style: italic; margin: 0; }}

  .pcard {{ border-left: 3px solid var(--accent); }}
  .proposal-head {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.9rem;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }}
  .proposal-head b {{ color: var(--ink-dim); font-weight: 500; }}
  .proposal-desc {{ font-size: 0.92rem; margin: 0 0 0.9rem; max-width: 62ch; }}
  .proposal-example {{
    font-size: 0.86rem;
    padding: 0.5rem 0.7rem;
    background: var(--paper);
    border-radius: 6px;
    margin-bottom: 0.4rem;
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }}
  .proposal-example .proposal-fragment {{ color: var(--ink-dim); font-style: italic; }}

  footer {{ margin-top: 4rem; font-size: 0.8rem; color: var(--ink-dim); }}
</style>

<div class="wrap">
  <h1>TEP-{tep} Taxonomy Rebaseline</h1>
  <p class="subtitle">A second, independent classification pass over TEP-{tep}'s {s["total_comments"]} review comments, built against the revised area/principle/nature taxonomy, compared to the original agent-produced ground truth.</p>
  <p class="meta-line">processed/tep{tep}/agent_classify_v2.jsonl &middot; conventions/seed-taxonomy.yaml on feature/tiered-classification</p>

  <div class="stats">
    <div class="stat"><div class="label">Old tags</div><div class="value">{old_total}</div></div>
    <div class="stat"><div class="label">New tags</div><div class="value">{new_total}</div></div>
    <div class="stat"><div class="label">Agree</div><div class="value">{agree}</div></div>
    <div class="stat"><div class="label">Precision</div><div class="value">{precision:.2f}</div></div>
    <div class="stat"><div class="label">Recall</div><div class="value">{recall:.2f}</div></div>
    <div class="stat"><div class="label">F1</div><div class="value">{f1:.2f}</div></div>
  </div>

  <p class="agree-note"><b>{s["clean_agree"]} comments</b> got the exact same tags both times, after accounting for the taxonomy's own changes (the <code>artifact</code>&rarr;<code>area</code> rename, the six values moved into <code>principle</code>, <code>pr-size</code> dropped, <code>structure</code>&rarr;<code>formatting</code>). Not shown below &mdash; nothing to review there.</p>

  <section>
    <details class="expected-details">
      <summary><h2>Expected from the taxonomy change<span class="count-badge">{len(expected)}</span></h2></summary>
      <p class="section-note">Every other tag on these comments is unchanged. Each one picked up a tag the old pass structurally couldn't have produced: <code>nature: none</code> didn't exist before (acknowledgments just got zero tags), or a <code>nature</code>/<code>area</code> value filled in for the first time now that both are near-mandatory. Nothing here changes what the comment was already tagged with, so there's nothing to review below &mdash; expand only if you want to see the list.</p>
      <ul class="expected-list">
        {expected_html}
      </ul>
    </details>
  </section>

  <section>
    <h2>Judgment calls</h2>
    <p class="section-note">{len(judgment)} comments where the two passes read the same text differently &mdash; a different principle chosen, a formatting/content split, or a tag added or dropped outright. Comment text included so each can be checked in context.</p>
    <div class="jcards">
      {judgment_html}
    </div>
  </section>
  {audit_section}

  <footer>TEP-{tep} &middot; {", ".join(s["repos"])}</footer>
</div>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    data = json.loads(args.data.read_text())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(args.tep, data))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
