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
"""Render a comment-by-comment, side-by-side HTML comparison of one scripts/classify_llm.py
candidate output against ground truth - a qualitative companion to
scripts/compare_classifications.py's aggregate precision/recall/F1.

Each comment gets a card: its body (so a match/miss can be judged in context, not just as a
bare (facet, value) tuple), then ground truth's tags next to the candidate's tags, each tag
marked matched/missing/extra. Cards are sorted by a "significance" score (ground truth tag
count weighted above disagreement count) so the richest and most-disputed comments surface
first - most real review comments carry zero tags on either side and aren't worth scrolling
past to find the interesting cases.

Usage:
    uv run scripts/render_comment_comparison.py --tep 52 \
        --ground-truth processed/tep52/agent_classify.jsonl \
        --include-audit processed/tep52/agent_audit.jsonl \
        --candidate processed/tep52/classify_llm_ollama_none_granite4-small-h_batch3_temp0.0_fewshot_facetsplit.jsonl \
        --out /tmp/comparison.html
"""

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify_llm import _comments_for, _load_tep_record  # noqa: E402

Tag = tuple[int, str, str]


def _load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _by_comment(rows: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in rows:
        out.setdefault(r["comment_id"], []).append(r)
    return out


def _tag_chip(row: dict, status: str) -> str:
    conf = row.get("confidence")
    conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else "?"
    evidence = html.escape(row.get("evidence", ""))
    return f"""<li class="tag tag-{status}">
      <div class="tag-head">
        <span class="tag-facet">{html.escape(row["facet"])}</span>
        <span class="tag-value">{html.escape(row["value"])}</span>
        <span class="tag-conf">{conf_str}</span>
      </div>
      <p class="tag-evidence">{evidence}</p>
    </li>"""


def _render_comment_card(cid: int, meta: dict, gt: list[dict], cand: list[dict]) -> str:
    gt_keys = {(r["facet"], r["value"]) for r in gt}
    cand_keys = {(r["facet"], r["value"]) for r in cand}

    gt_chips = [
        _tag_chip(r, "match" if (r["facet"], r["value"]) in cand_keys else "missing") for r in gt
    ]
    cand_chips = [
        _tag_chip(r, "match" if (r["facet"], r["value"]) in gt_keys else "extra") for r in cand
    ]

    body = meta.get("body", "")
    body_html = html.escape(body).replace("\n", "<br>")
    author = html.escape(meta.get("author") or "unknown")
    loc = html.escape(meta.get("section") or meta.get("path") or "")
    repo = html.escape(meta.get("repo", ""))
    pr = meta.get("pr_number", "")

    n_missing = len(gt) - sum(1 for r in gt if (r["facet"], r["value"]) in cand_keys)
    n_extra = len(cand) - sum(1 for r in cand if (r["facet"], r["value"]) in gt_keys)
    n_match = len(gt) - n_missing
    if not gt and not cand:
        verdict = "empty"
    elif n_missing == 0 and n_extra == 0:
        verdict = "clean"
    else:
        verdict = "diff"

    return f"""<article class="card card-{verdict}">
    <header class="card-head">
      <div class="card-meta">
        <span class="comment-id">#{cid}</span>
        <span class="dot">&middot;</span>
        <span class="repo">{repo}/pr{pr}</span>
        {f'<span class="dot">&middot;</span><span class="loc">{loc}</span>' if loc else ""}
        <span class="dot">&middot;</span>
        <span class="author">{author}</span>
      </div>
      <div class="card-score">
        <span class="score-match">{n_match} match</span>
        {f'<span class="score-missing">{n_missing} missing</span>' if n_missing else ""}
        {f'<span class="score-extra">{n_extra} extra</span>' if n_extra else ""}
      </div>
    </header>
    <p class="card-body">{body_html}</p>
    <div class="card-columns">
      <div class="col">
        <h3>Ground truth <span class="col-count">{len(gt)}</span></h3>
        <ul class="tags">{"".join(gt_chips) or '<li class="tag-empty">no tags</li>'}</ul>
      </div>
      <div class="col">
        <h3>Granite <span class="col-count">{len(cand)}</span></h3>
        <ul class="tags">{"".join(cand_chips) or '<li class="tag-empty">no tags</li>'}</ul>
      </div>
    </div>
  </article>"""


def render(
    tep: int,
    gt_rows: list[dict],
    cand_rows: list[dict],
    comments_meta: dict[int, dict],
    title: str,
    subtitle: str,
) -> str:
    gt_by_id = _by_comment(gt_rows)
    cand_by_id = _by_comment(cand_rows)
    all_ids = set(gt_by_id) | set(cand_by_id)

    gt_set: set[Tag] = {(r["comment_id"], r["facet"], r["value"]) for r in gt_rows}
    cand_set: set[Tag] = {(r["comment_id"], r["facet"], r["value"]) for r in cand_rows}
    tp = len(gt_set & cand_set)
    precision = tp / len(cand_set) if cand_set else 0.0
    recall = tp / len(gt_set) if gt_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    scored = []
    for cid in all_ids:
        gt = gt_by_id.get(cid, [])
        cand = cand_by_id.get(cid, [])
        gt_keys = {(r["facet"], r["value"]) for r in gt}
        cand_keys = {(r["facet"], r["value"]) for r in cand}
        missing = len(gt_keys - cand_keys)
        extra = len(cand_keys - gt_keys)
        significance = 2 * len(gt) + missing + extra
        scored.append((significance, cid, gt, cand))
    scored.sort(key=lambda t: (-t[0], t[1]))

    cards = []
    skipped_empty = 0
    for significance, cid, gt, cand in scored:
        if significance == 0:
            skipped_empty += 1
            continue
        meta = comments_meta.get(cid, {})
        cards.append(_render_comment_card(cid, meta, gt, cand))

    cards_html = "\n".join(cards)

    return f"""<title>Granite vs Ground Truth</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@600;700;800&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --ground: #f4f6f9;
    --surface: #ffffff;
    --surface-2: #eef1f6;
    --ink: #1c222c;
    --ink-dim: #5b6472;
    --border: #dde2e9;
    --accent: #2f5178;
    --accent-dim: #5a7ba3;
    --match: #1f7a4c;
    --match-bg: #e4f5ec;
    --missing: #b3261e;
    --missing-bg: #fbeae9;
    --extra: #9a5b00;
    --extra-bg: #fbf0dc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --ground: #0f1216;
      --surface: #171b21;
      --surface-2: #1e232b;
      --ink: #e6e9ee;
      --ink-dim: #9aa3b2;
      --border: #2a303a;
      --accent: #8fb2dd;
      --accent-dim: #6d8db3;
      --match: #6fdb9e;
      --match-bg: #12321f;
      --missing: #f2867d;
      --missing-bg: #3a1917;
      --extra: #f0b429;
      --extra-bg: #3a2c0c;
    }}
  }}
  :root[data-theme="dark"] {{
    --ground: #0f1216;
    --surface: #171b21;
    --surface-2: #1e232b;
    --ink: #e6e9ee;
    --ink-dim: #9aa3b2;
    --border: #2a303a;
    --accent: #8fb2dd;
    --accent-dim: #6d8db3;
    --match: #6fdb9e;
    --match-bg: #12321f;
    --missing: #f2867d;
    --missing-bg: #3a1917;
    --extra: #f0b429;
    --extra-bg: #3a2c0c;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: "Source Sans 3", -apple-system, "Segoe UI", sans-serif;
    font-size: 16px;
    line-height: 1.5;
  }}
  .wrap {{
    max-width: 880px;
    margin: 0 auto;
    padding: 2.5rem 1.5rem 6rem;
  }}
  h1, h2, h3 {{
    font-family: "Libre Franklin", -apple-system, sans-serif;
    text-wrap: balance;
    margin: 0;
  }}
  h1 {{
    font-size: 1.7rem;
    font-weight: 800;
    letter-spacing: -0.01em;
  }}
  .subtitle {{
    color: var(--ink-dim);
    font-size: 0.95rem;
    margin-top: 0.35rem;
  }}

  .stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin: 1.5rem 0 2.5rem;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    flex: 1 1 110px;
  }}
  .stat .label {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-dim);
  }}
  .stat .value {{
    font-family: "IBM Plex Mono", monospace;
    font-variant-numeric: tabular-nums;
    font-size: 1.35rem;
    font-weight: 500;
    color: var(--accent);
    margin-top: 0.15rem;
  }}

  .note {{
    font-size: 0.85rem;
    color: var(--ink-dim);
    border-left: 3px solid var(--border);
    padding-left: 0.85rem;
    margin-bottom: 2.5rem;
  }}

  .cards {{
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--border);
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
  }}
  .card-diff {{ border-left-color: var(--missing); }}
  .card-clean {{ border-left-color: var(--match); }}

  .card-head {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.6rem;
  }}
  .card-meta {{
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.78rem;
    color: var(--ink-dim);
  }}
  .card-meta .comment-id {{ color: var(--accent-dim); }}
  .card-meta .dot {{ margin: 0 0.3em; opacity: 0.6; }}
  .card-score {{
    display: flex;
    gap: 0.5rem;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .score-match {{ color: var(--match); }}
  .score-missing {{ color: var(--missing); }}
  .score-extra {{ color: var(--extra); }}

  .card-body {{
    margin: 0 0 1rem;
    padding: 0.7rem 0.9rem;
    background: var(--surface-2);
    border-radius: 8px;
    font-size: 0.93rem;
    max-width: 65ch;
  }}

  .card-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.2rem;
  }}
  @media (max-width: 620px) {{
    .card-columns {{ grid-template-columns: 1fr; }}
  }}
  .col h3 {{
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ink-dim);
    margin-bottom: 0.5rem;
  }}
  .col-count {{
    font-family: "IBM Plex Mono", monospace;
    color: var(--accent-dim);
  }}

  ul.tags {{
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}
  .tag {{
    border-radius: 7px;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--border);
  }}
  .tag-match {{ background: var(--match-bg); border-color: color-mix(in srgb, var(--match) 35%, var(--border)); }}
  .tag-missing {{ background: var(--missing-bg); border-color: color-mix(in srgb, var(--missing) 35%, var(--border)); }}
  .tag-extra {{ background: var(--extra-bg); border-color: color-mix(in srgb, var(--extra) 35%, var(--border)); }}
  .tag-empty {{ color: var(--ink-dim); font-size: 0.85rem; font-style: italic; list-style: none; }}

  .tag-head {{
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.82rem;
  }}
  .tag-facet {{ color: var(--ink-dim); }}
  .tag-value {{ font-weight: 500; }}
  .tag-conf {{
    margin-left: auto;
    color: var(--ink-dim);
    font-variant-numeric: tabular-nums;
  }}
  .tag-evidence {{
    margin: 0.3rem 0 0;
    font-size: 0.82rem;
    color: var(--ink-dim);
    font-style: italic;
  }}

  footer {{
    margin-top: 3rem;
    font-size: 0.8rem;
    color: var(--ink-dim);
    text-align: center;
  }}
</style>

<div class="wrap">
  <h1>{html.escape(title)}</h1>
  <p class="subtitle">{html.escape(subtitle)}</p>

  <div class="stats">
    <div class="stat"><div class="label">Precision</div><div class="value">{precision:.2f}</div></div>
    <div class="stat"><div class="label">Recall</div><div class="value">{recall:.2f}</div></div>
    <div class="stat"><div class="label">F1</div><div class="value">{f1:.2f}</div></div>
    <div class="stat"><div class="label">GT tags</div><div class="value">{len(gt_set)}</div></div>
    <div class="stat"><div class="label">Candidate tags</div><div class="value">{len(cand_set)}</div></div>
    <div class="stat"><div class="label">Matched</div><div class="value">{tp}</div></div>
  </div>

  <p class="note">Sorted by significance (ground truth tag count, weighted, plus disagreement count) - richest and most-disputed comments first. {skipped_empty} comment(s) with zero tags on both sides omitted below.</p>

  <div class="cards">
    {cards_html}
  </div>

  <footer>TEP-{tep} &middot; generated by scripts/render_comment_comparison.py</footer>
</div>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tep", type=int, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--include-audit", type=Path, default=None)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--subtitle", default=None)
    args = parser.parse_args(argv)

    gt_rows = _load_rows(args.ground_truth)
    if args.include_audit:
        gt_rows += _load_rows(args.include_audit)
    cand_rows = _load_rows(args.candidate)

    record = _load_tep_record(args.tep)
    comments_meta = {c["comment_id"]: c for c in _comments_for(record)}

    title = args.title or f"TEP-{args.tep}: {args.candidate.stem}"
    subtitle = (
        args.subtitle or f"vs. {args.ground_truth} (+ {args.include_audit})"
        if args.include_audit
        else f"vs. {args.ground_truth}"
    )

    html_out = render(args.tep, gt_rows, cand_rows, comments_meta, title, subtitle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_out, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
