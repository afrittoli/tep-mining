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
"""Build the interactive TEP data explorer from processed/latest/per_tep_records.json.

Self-contained static HTML: the per-TEP records are embedded inline (no fetch,
so it works offline / opened directly from disk), with a client-side JS
sortable/filterable master table and a per-TEP detail view linked by
everything Sub-Tasks 2-7 collected. Section-attribution corrections made in
the browser can be exported as overrides/section_overrides.jsonl for the
user to review and commit — see the "Corrections" panel in the UI.

Usage:
    uv run scripts/build_explorer.py
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

CSS = """
  :root {
    --ink: #1f2328; --ink-dim: #57606a; --rule: #e5e7eb; --bg: #ffffff; --bg-alt: #f7f8fa;
    --link: #3b82d4; --good: #15803d; --good-bg: #f0fdf4; --bad: #b91c1c; --bad-bg: #fef2f2;
    --warn: #97621c; --warn-bg: #f1e6d2; --accent: #3b82d4;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px;
    line-height: 1.55; color: var(--ink); background: var(--bg);
  }
  a { color: var(--link); text-decoration: none; }
  a:hover { text-decoration: underline; }
  code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.92em;
    background: var(--bg-alt); border: 1px solid var(--rule); border-radius: 3px; padding: 0 4px; }

  header { padding: 18px 24px; border-bottom: 1px solid var(--rule); display: flex;
    align-items: baseline; gap: 20px; flex-wrap: wrap; }
  header h1 { font-size: 18px; font-weight: 600; margin: 0; }
  header .subtitle { color: var(--ink-dim); font-size: 12.5px; }
  header .stats { margin-left: auto; display: flex; gap: 16px; font-size: 12.5px; color: var(--ink-dim); }
  header .stats b { color: var(--ink); }

  #view-list, #view-detail { padding: 18px 24px; }
  .hidden { display: none !important; }

  .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
  .toolbar input[type=text] {
    flex: 1 1 240px; padding: 7px 10px; border: 1px solid var(--rule); border-radius: 6px;
    font-size: 13px; min-width: 180px;
  }
  .toolbar select { padding: 7px 10px; border: 1px solid var(--rule); border-radius: 6px; font-size: 13px; }
  .toolbar .count { color: var(--ink-dim); font-size: 12.5px; white-space: nowrap; }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th {
    position: sticky; top: 0; background: var(--bg-alt); text-align: left; padding: 7px 10px;
    font-weight: 600; border-bottom: 2px solid var(--rule); color: var(--ink-dim); font-size: 11.5px;
    text-transform: uppercase; letter-spacing: .03em; cursor: pointer; white-space: nowrap;
  }
  thead th:hover { color: var(--ink); }
  thead th.sorted::after { content: " " attr(data-dir); font-size: 10px; }
  tbody tr { cursor: pointer; }
  tbody tr:hover { background: var(--bg-alt); }
  tbody tr:nth-child(even) { background: #fbfbfc; }
  tbody tr:nth-child(even):hover { background: var(--bg-alt); }
  tbody td { padding: 6px 10px; border-bottom: 1px solid var(--rule); vertical-align: top; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }

  .badge { display: inline-block; font-size: 10.5px; padding: 1px 7px; border-radius: 9px;
    font-weight: 500; white-space: nowrap; border: 1px solid transparent; }
  .badge-approved  { background: var(--good-bg); color: var(--good); border-color: #bbf7d0; }
  .badge-changes   { background: var(--bad-bg); color: var(--bad); border-color: #fecaca; }
  .badge-commented { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
  .badge-skipped   { background: var(--bg-alt); color: var(--ink-dim); border-color: var(--rule); }
  .badge-warn      { background: var(--warn-bg); color: var(--warn); border-color: #f1d9a8; }
  .badge-override  { background: #f5f3ff; color: #6d28d9; border-color: #ddd6fe; }

  .back-link { display: inline-block; margin-bottom: 12px; font-size: 13px; }
  .detail-header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
  .detail-header h2 { font-size: 20px; margin: 0; }
  .detail-meta { color: var(--ink-dim); font-size: 12.5px; margin-bottom: 18px; }
  .detail-meta a { color: var(--link); }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;
    margin-bottom: 20px; }
  .stat { background: var(--bg-alt); border: 1px solid var(--rule); border-radius: 6px; padding: 10px 12px; }
  .stat .num { font-size: 20px; font-weight: 700; }
  .stat .label { font-size: 11px; color: var(--ink-dim); text-transform: uppercase; letter-spacing: .03em; }

  section.block { margin-bottom: 26px; }
  section.block h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
    color: var(--ink-dim); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin: 0 0 12px; }

  ul.plain { margin: 0; padding-left: 1.1em; }
  ul.plain li { margin-bottom: 4px; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 720px) { .two-col { grid-template-columns: 1fr; } }

  .pr-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px dashed var(--rule);
    flex-wrap: wrap; }
  .pr-row:last-child { border-bottom: none; }
  .pr-row .repo { font-family: ui-monospace, monospace; font-size: 11.5px; color: var(--ink-dim);
    background: var(--bg-alt); border: 1px solid var(--rule); border-radius: 4px; padding: 0 5px; }
  .pr-row .title { flex: 1; }
  .pr-row .size { color: var(--ink-dim); font-size: 11.5px; white-space: nowrap; }
  .pr-row .why { color: var(--ink-dim); font-size: 11.5px; }
  .pr-row.pending-exclude { opacity: 0.55; }
  .pr-row.excluded { opacity: 0.7; }
  .pr-row.candidate { border-left: 2px solid var(--warn); padding-left: 8px; }
  .mini-btn { font-size: 11px; padding: 2px 8px; border: 1px solid var(--rule); border-radius: 10px;
    background: var(--bg-alt); color: var(--ink-dim); cursor: pointer; white-space: nowrap; }
  .mini-btn:hover { background: var(--rule); color: var(--ink); }

  details.self-comments, details.impl-comments, details.review-comments { margin-top: 10px;
    border: 1px solid var(--rule); border-radius: 6px; width: 100%; }
  details.self-comments summary, details.impl-comments summary, details.review-comments summary {
    cursor: pointer; padding: 8px 10px; font-size: 12.5px; color: var(--ink-dim); list-style: none; }
  details.self-comments summary::-webkit-details-marker, details.impl-comments summary::-webkit-details-marker,
    details.review-comments summary::-webkit-details-marker { display: none; }
  details.self-comments summary::before, details.impl-comments summary::before,
    details.review-comments summary::before { content: "▸ "; }
  details.self-comments[open] summary::before, details.impl-comments[open] summary::before,
    details.review-comments[open] summary::before { content: "▾ "; }
  details.self-comments .comment, details.impl-comments .comment, details.review-comments .comment {
    margin: 0 10px 8px; }
  details.self-comments .comment:first-of-type, details.impl-comments .comment:first-of-type,
    details.review-comments .comment:first-of-type { margin-top: 0; }
  details.review-comments details.self-comments { margin: 0 10px 8px; }
  details.impl-comments details.self-comments { margin: 0 10px 8px; }

  .comment { border: 1px solid var(--rule); border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; }
  .comment .meta { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; font-size: 11.5px;
    color: var(--ink-dim); flex-wrap: wrap; }
  .comment .body { font-size: 13px; white-space: pre-wrap; max-height: 5.5em; overflow-y: auto; }
  .comment select { font-size: 11.5px; padding: 1px 4px; border: 1px solid var(--rule); border-radius: 4px; }
  .comment.unmapped { opacity: 0.7; }

  .corrections-bar { position: sticky; bottom: 0; background: var(--bg); border-top: 1px solid var(--rule);
    padding: 10px 24px; display: flex; align-items: center; gap: 12px; font-size: 12.5px; flex-wrap: wrap; }
  .corrections-bar button { font-size: 12.5px; padding: 5px 12px; border: 1px solid var(--rule);
    border-radius: 6px; background: var(--bg-alt); cursor: pointer; }
  .corrections-bar button:hover { background: var(--rule); }
  .corrections-bar .sep { border-left: 1px solid var(--rule); align-self: stretch; }
  #export-box, #pr-export-box { width: 100%; max-width: 900px; font-family: ui-monospace, monospace;
    font-size: 11.5px; padding: 8px; border: 1px solid var(--rule); border-radius: 6px; }

  footer { padding: 16px 24px; text-align: center; font-size: 12px; color: var(--ink-dim);
    border-top: 1px solid var(--rule); }
"""

JS = """
const DATA = JSON.parse(document.getElementById('tep-data').textContent);
const BY_NUMBER = new Map(DATA.map(r => [r.tep_number, r]));

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
function mergeStateBadge(it) {
  // Not review_decision: that's "did any reviewer, ever, leave this state" (fixed priority),
  // which goes stale the moment a reviewer changes their mind after re-reviewing (confirmed on
  // real data — chains#590/#599 both got re-approved by the same reviewer who'd first requested
  // changes, yet kept showing "changes requested" forever). Actual PR disposition is a much
  // more stable, honest signal to show instead.
  if (it.merged_at) return '<span class="badge badge-approved">merged</span>';
  if (it.state === 'closed') return '<span class="badge badge-changes">closed, not merged</span>';
  if (it.state === 'open') return '<span class="badge badge-commented">open</span>';
  return '';
}
function underLinkingRate(r) {
  const total = r.impl_prs.total_count;
  if (!total) return null;
  return (r.impl_prs.discovered_count / total) * 100;
}

// ---------------------------------------------------------------------------
// Corrections (in-browser, exportable — see overrides/section_overrides.jsonl)
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'tep-explorer-corrections-v1';
function loadCorrections() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}
function saveCorrections(c) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(c));
}
let corrections = loadCorrections();

function correctionKey(prNumber, commentId) { return `${prNumber}:${commentId}`; }

function setCorrection(prNumber, commentId, section) {
  corrections[correctionKey(prNumber, commentId)] = {
    repo: 'community', pr_number: prNumber, comment_id: commentId,
    override_section: section, created_at: new Date().toISOString(),
  };
  saveCorrections(corrections);
  renderCorrectionsBar();
}

function renderCorrectionsBar() {
  const n = Object.keys(corrections).length;
  const m = Object.keys(prCorrections).length;
  const bar = document.getElementById('corrections-bar');
  document.getElementById('corrections-count').textContent = n;
  document.getElementById('pr-corrections-count').textContent = m;
  bar.classList.toggle('hidden', n === 0 && m === 0);
}

function exportCorrections() {
  const lines = Object.values(corrections).map(c => JSON.stringify(c));
  const box = document.getElementById('export-box');
  box.value = lines.join('\\n') + (lines.length ? '\\n' : '');
  box.classList.remove('hidden');
  box.select();
}

function clearCorrections() {
  if (!confirm('Clear all ' + Object.keys(corrections).length + ' pending section corrections? This does not affect anything already exported.')) return;
  corrections = {};
  saveCorrections(corrections);
  renderCorrectionsBar();
  document.getElementById('export-box').classList.add('hidden');
  if (location.hash) render();
}

// ---------------------------------------------------------------------------
// PR attribution corrections (in-browser, exportable — see
// overrides/pr_attribution_overrides.jsonl). Answers "why was this PR picked"
// via evidence display in renderImplPrList, and lets a human exclude a
// wrongly-attributed PR or include a missing one.
// ---------------------------------------------------------------------------

const PR_STORAGE_KEY = 'tep-explorer-pr-corrections-v1';
function loadPrCorrections() {
  try { return JSON.parse(localStorage.getItem(PR_STORAGE_KEY)) || {}; } catch { return {}; }
}
function savePrCorrections(c) {
  localStorage.setItem(PR_STORAGE_KEY, JSON.stringify(c));
}
let prCorrections = loadPrCorrections();

function prCorrectionKey(tepNumber, repo, prNumber) { return `${tepNumber}:${repo}:${prNumber}`; }

function recordPrCorrection(tepNumber, repo, prNumber, action, reason) {
  prCorrections[prCorrectionKey(tepNumber, repo, prNumber)] = {
    tep_number: tepNumber, repo, pr_number: prNumber, action, reason: reason || '',
    created_at: new Date().toISOString(),
  };
  savePrCorrections(prCorrections);
  renderCorrectionsBar();
}

function promptExclude(tepNumber, repo, prNumber) {
  const reason = prompt(`Why is ${repo}#${prNumber} not relevant to TEP-${tepNumber}?`, '');
  if (reason === null) return;
  recordPrCorrection(tepNumber, repo, prNumber, 'exclude', reason);
  render();
}

function promptInclude(tepNumber) {
  const repo = (prompt('Repo (e.g. pipeline, triggers, results)?', '') || '').trim();
  if (!repo) return;
  const prNumberStr = (prompt(`PR number in tektoncd/${repo}?`, '') || '').trim();
  const prNumber = parseInt(prNumberStr, 10);
  if (!Number.isFinite(prNumber)) { alert('Not a valid PR number.'); return; }
  const reason = prompt(`Why is ${repo}#${prNumber} relevant to TEP-${tepNumber}?`, '');
  if (reason === null) return;
  recordPrCorrection(tepNumber, repo, prNumber, 'include', reason);
  render();
}

function exportPrCorrections() {
  const lines = Object.values(prCorrections).map(c => JSON.stringify(c));
  const box = document.getElementById('pr-export-box');
  box.value = lines.join('\\n') + (lines.length ? '\\n' : '');
  box.classList.remove('hidden');
  box.select();
}

function clearPrCorrections() {
  if (!confirm('Clear all ' + Object.keys(prCorrections).length + ' pending PR attribution corrections? This does not affect anything already exported.')) return;
  prCorrections = {};
  savePrCorrections(prCorrections);
  renderCorrectionsBar();
  document.getElementById('pr-export-box').classList.add('hidden');
  if (location.hash) render();
}

// ---------------------------------------------------------------------------
// Master table
// ---------------------------------------------------------------------------

let sortKey = 'tep_number';
let sortDir = 1;
let filterText = '';
let filterStatus = '';

function filteredSorted() {
  let rows = DATA.filter(r => {
    if (filterStatus === '__flagged__') {
      if (!(r.flags || []).length) return false;
    } else if (filterStatus && r.status !== filterStatus) {
      return false;
    }
    if (filterText) {
      const hay = (r.title + ' ' + (r.authors || []).join(' ') + ' TEP-' + r.tep_number).toLowerCase();
      if (!hay.includes(filterText.toLowerCase())) return false;
    }
    return true;
  });
  const key = sortKey;
  rows.sort((a, b) => {
    let av, bv;
    if (key === 'under_linking') { av = underLinkingRate(a) ?? -1; bv = underLinkingRate(b) ?? -1; }
    else if (key === 'linked_count') { av = a.impl_prs.linked_count; bv = b.impl_prs.linked_count; }
    else if (key === 'discovered_count') { av = a.impl_prs.discovered_count; bv = b.impl_prs.discovered_count; }
    else if (key === 'impl_sum') { av = a.impl_prs.linked_count + a.impl_prs.discovered_count; bv = b.impl_prs.linked_count + b.impl_prs.discovered_count; }
    else if (key === 'review_comments') { av = a.proposal_pr.review_comment_count; bv = b.proposal_pr.review_comment_count; }
    else if (key === 'authors') { av = (a.authors || []).join(','); bv = (b.authors || []).join(','); }
    else { av = a[key]; bv = b[key]; }
    if (av == null) av = '';
    if (bv == null) bv = '';
    if (av < bv) return -1 * sortDir;
    if (av > bv) return 1 * sortDir;
    return 0;
  });
  return rows;
}

function gapBadge(r) {
  if (!r.gap) return '';
  const label = { open_pr: 'open', conflict: 'conflict', closed_no_merge: 'closed',
    never_assigned: 'unassigned', renumbered: 'renumbered' }[r.gap.fate] || r.gap.fate;
  return `<span class="badge badge-warn">${esc(label)}</span>`;
}

function flagsBadge(r) {
  if (!(r.flags || []).length) return '';
  const title = r.flags.map(f => f.message).join(' \\u2014 ');
  return `<span class="badge badge-warn" title="${esc(title)}">\\u26a0 review</span>`;
}

function renderTable() {
  const rows = filteredSorted();
  document.getElementById('row-count').textContent = `${rows.length} of ${DATA.length} TEPs`;
  const body = rows.map(r => {
    const rate = underLinkingRate(r);
    const rateStr = rate == null ? '—' : rate.toFixed(0) + '%';
    return `<tr onclick="location.hash='tep-${r.tep_number}'">
      <td class="num">${r.tep_number}</td>
      <td>${esc(r.title)} ${gapBadge(r)} ${flagsBadge(r)}</td>
      <td>${esc(r.status || '')}</td>
      <td>${esc((r.authors || []).join(', '))}</td>
      <td class="num">${r.age_days ?? '—'}</td>
      <td class="num">${r.impl_prs.linked_count}</td>
      <td class="num">${r.impl_prs.discovered_count}</td>
      <td class="num">${r.impl_prs.linked_count + r.impl_prs.discovered_count}</td>
      <td class="num">${rateStr}</td>
      <td class="num">${r.proposal_pr.review_comment_count}</td>
    </tr>`;
  }).join('');
  document.getElementById('tbody').innerHTML = body;

  document.querySelectorAll('thead th[data-key]').forEach(th => {
    th.classList.toggle('sorted', th.dataset.key === sortKey);
    th.dataset.dir = sortDir === 1 ? '\\u2191' : '\\u2193';
  });
}

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

function sectionOptions(record, selected) {
  const opts = new Set(record.sections_present || []);
  (record.divergences_from_template ? record.divergences_from_template.missing_from_tep : []).forEach(s => opts.add(s));
  opts.add(selected || '');
  return [...opts].filter(Boolean).sort().map(s =>
    `<option value="${esc(s)}" ${s === selected ? 'selected' : ''}>${esc(s)}</option>`
  ).join('');
}

function renderComment(record, c) {
  const overrideKey = correctionKey(c.pr_number, c.comment_id);
  const pending = corrections[overrideKey];
  const currentSection = pending ? pending.override_section : c.section;
  const tag = pending ? '<span class="badge badge-override">pending override</span>'
    : c.is_override ? '<span class="badge badge-override">override</span>'
    : currentSection ? '' : '<span class="badge badge-skipped">unmapped</span>';
  return `<div class="comment ${currentSection ? '' : 'unmapped'}">
    <div class="meta">
      <b>${esc(c.author || 'unknown')}</b>
      <span>${esc((c.created_at || '').slice(0, 10))}</span>
      ${tag}
      <span style="margin-left:auto">section:
        <select onchange="setCorrection(${c.pr_number}, ${c.comment_id}, this.value); render()">
          <option value="">(unmapped)</option>
          ${sectionOptions(record, currentSection)}
        </select>
      </span>
    </div>
    <div class="body">${esc(c.body)}</div>
  </div>`;
}

function renderProposalPrList(prs) {
  if (!prs.length) return `<p style="color:var(--ink-dim)">None found in raw/tep_pr_map.json.</p>`;
  return prs.map(p => `<div class="pr-row">
      <span class="repo">community</span>
      <a class="title" href="https://github.com/tektoncd/community/pull/${p.pr_number}" target="_blank" rel="noopener">
        #${p.pr_number} ${esc(p.title)}
      </a>
      ${mergeStateBadge(p)}
      <span class="size">${esc((p.reviewer_logins || []).join(', ')) || 'no reviewers recorded'}</span>
    </div>`).join('');
}

function evidenceHtml(it) {
  if (it.attribution_source === 'tep_file_link') {
    const url = it.evidence && it.evidence.url;
    const format = it.evidence && it.evidence.format;
    return url ? `linked (${esc(format || '?')}): <a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>` : 'linked (no URL recorded)';
  }
  if (it.attribution_source === 'search') {
    return it.evidence ? `matched: &ldquo;${esc(it.evidence)}&rdquo;` : 'discovered by search (no snippet captured)';
  }
  if (it.attribution_source === 'manual_include') {
    return it.evidence ? `manually included: ${esc(it.evidence)}` : 'manually included (no reason given)';
  }
  return '';
}

function renderImplComment(c) {
  const where = c.path ? `<span class="badge badge-skipped">${esc(c.path)}${c.line != null ? ':' + c.line : ''}</span>` : '';
  return `<div class="comment">
    <div class="meta">
      <b>${esc(c.author || 'unknown')}</b>
      <span>${esc((c.created_at || '').slice(0, 10))}</span>
      ${where}
    </div>
    <div class="body">${esc(c.body)}</div>
  </div>`;
}

function implCommentsToggle(it) {
  if (!it.comments || !it.comments.length) return '';
  const other = it.comments.filter(c => !c.is_self_comment);
  const self = it.comments.filter(c => c.is_self_comment);
  const otherHtml = other.length ? other.map(renderImplComment).join('')
    : '<p style="color:var(--ink-dim)">No review comments from others.</p>';
  const selfHtml = self.length ? `<details class="self-comments">
    <summary>${self.length} self-review comment${self.length === 1 ? '' : 's'} from the PR's own author</summary>
    ${self.map(renderImplComment).join('')}
  </details>` : '';
  return `<details class="impl-comments" style="flex-basis:100%">
    <summary>${it.review_comment_count} review comment${it.review_comment_count === 1 ? '' : 's'}</summary>
    ${otherHtml}${selfHtml}
  </details>`;
}

function renderImplPrList(tepNumber, items) {
  if (!items.length) return `<p style="color:var(--ink-dim)">None.</p>`;
  return items.map(it => {
    const key = prCorrectionKey(tepNumber, it.repo, it.pr_number);
    const excludePending = prCorrections[key];
    const rowClass = excludePending ? 'pr-row pending-exclude' : 'pr-row';
    if (it.status === 'not_found' || it.status === 'pending_fetch') {
      const label = it.status === 'not_found' ? '404 not found' : 'not yet fetched — run make apply-pr-overrides';
      return `<div class="${rowClass}">
        <span class="repo">${esc(it.repo)}</span>
        <span class="title">#${it.pr_number} <span class="badge badge-skipped">${label}</span>
          <div class="why">${evidenceHtml(it)}</div>
        </span>
        ${excludeControl(tepNumber, it, excludePending)}
      </div>`;
    }
    return `<div class="${rowClass}">
      <span class="repo">${esc(it.repo)}</span>
      <a class="title" href="https://github.com/tektoncd/${esc(it.repo)}/pull/${it.pr_number}" target="_blank" rel="noopener">
        #${it.pr_number} ${esc(it.title)}
      </a>
      ${mergeStateBadge(it)}
      <span class="size">+${it.additions ?? 0}/-${it.deletions ?? 0} (${it.files_changed ?? 0} files)</span>
      ${excludeControl(tepNumber, it, excludePending)}
      <div class="why" style="flex-basis:100%">${evidenceHtml(it)}</div>
      ${implCommentsToggle(it)}
    </div>`;
  }).join('');
}

function excludeControl(tepNumber, it, pending) {
  if (pending) return `<span class="badge badge-override">pending exclude</span>`;
  return `<button class="mini-btn" onclick="promptExclude(${tepNumber}, '${esc(it.repo)}', ${it.pr_number})">not relevant?</button>`;
}

function renderCandidateList(tepNumber, candidates) {
  if (!candidates.length) return `<p style="color:var(--ink-dim)">None.</p>`;
  return candidates.map(c => {
    const key = prCorrectionKey(tepNumber, c.repo, c.pr_number);
    const pending = prCorrections[key];
    const pendingBadge = pending
      ? `<span class="badge badge-override">pending ${pending.action === 'include' ? 'confirm' : 'dismiss'}</span>`
      : '';
    const titleText = c.status === 'not_found' ? `<span class="badge badge-skipped">404 not found</span>`
      : c.status === 'pending_fetch' ? `<span class="badge badge-skipped">not yet fetched</span>`
      : `${esc(c.title || '')} ${c.author ? `<span class="badge badge-skipped">by ${esc(c.author)}</span>` : ''} ${mergeStateBadge(c)}`;
    const actions = pending ? '' : `
        <button class="mini-btn" onclick="promptConfirmCandidate(${tepNumber}, '${esc(c.repo)}', ${c.pr_number})">confirm relevant</button>
        <button class="mini-btn" onclick="promptExclude(${tepNumber}, '${esc(c.repo)}', ${c.pr_number})">dismiss</button>`;
    return `<div class="pr-row candidate ${pending ? 'pending-exclude' : ''}">
      <span class="repo">${esc(c.repo)}</span>
      <a class="title" href="https://github.com/tektoncd/${esc(c.repo)}/pull/${c.pr_number}" target="_blank" rel="noopener">#${c.pr_number}</a>
      ${titleText} ${pendingBadge}
      ${actions}
      <div class="why" style="flex-basis:100%">${esc(c.why_candidate)}${c.evidence ? ' — matched: “' + esc(c.evidence) + '”' : ''}</div>
    </div>`;
  }).join('');
}

function promptConfirmCandidate(tepNumber, repo, prNumber) {
  const reason = prompt(`Why is ${repo}#${prNumber} confirmed as relevant to TEP-${tepNumber}?`, '');
  if (reason === null) return;
  recordPrCorrection(tepNumber, repo, prNumber, 'include', reason);
  render();
}

function renderExcludedList(tepNumber, excluded) {
  if (!excluded.length) return '';
  const rows = excluded.map(e => `<div class="pr-row excluded">
    <span class="repo">${esc(e.repo)}</span>
    <span class="title">#${e.pr_number} <span class="badge badge-skipped">excluded</span>
      <div class="why">was: ${esc(e.was_attribution_source)}${e.reason ? ' &mdash; ' + esc(e.reason) : ''}</div>
    </span>
  </div>`).join('');
  return `<section class="block"><h3>Excluded by manual override (${excluded.length})</h3>${rows}</section>`;
}

function renderDetail(tepNumber) {
  const r = BY_NUMBER.get(tepNumber);
  const container = document.getElementById('view-detail');
  if (!r) { container.innerHTML = '<p>TEP not found.</p>'; return; }

  const linked = r.impl_prs.items.filter(i => i.attribution_source === 'tep_file_link');
  const discovered = r.impl_prs.items.filter(i => i.attribution_source === 'search');
  const manual = r.impl_prs.items.filter(i => i.attribution_source === 'manual_include');
  const rate = underLinkingRate(r);

  const divergences = r.divergences_from_template;
  const divergenceHtml = !divergences ? '<p style="color:var(--ink-dim)">No section data (stub TEP).</p>' : `
    <div class="two-col">
      <div>
        <b>Missing from template</b>
        <ul class="plain">${divergences.missing_from_tep.map(s => `<li>${esc(s)}</li>`).join('') || '<li style="color:var(--ink-dim)">None</li>'}</ul>
      </div>
      <div>
        <b>Extra, not in template</b>
        <ul class="plain">${divergences.extra_in_tep.map(s => `<li>${esc(s)}</li>`).join('') || '<li style="color:var(--ink-dim)">None</li>'}</ul>
      </div>
    </div>`;

  const gapHtml = r.gap ? `<section class="block"><h3>Gap status</h3>
    <p><span class="badge badge-warn">${esc(r.gap.fate)}</span>
    ${r.gap.renamed_from ? ` renamed from TEP-${String(r.gap.renamed_from).padStart(4,'0')}` : ''}</p></section>` : '';

  const flagsHtml = (r.flags || []).length ? `<section class="block"><h3>Flagged for review</h3>
    ${r.flags.map(f => `<p><span class="badge badge-warn">\\u26a0 ${esc(f.code)}</span> ${esc(f.message)}</p>`).join('')}
    </section>` : '';

  const sourceLink = r.source_file
    ? `<a href="https://github.com/tektoncd/community/blob/main/teps/${esc(r.source_file)}" target="_blank" rel="noopener">${esc(r.source_file)}</a>`
    : '(no merged file)';

  const commentsSorted = [...r.proposal_pr.comments].sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
  const otherComments = commentsSorted.filter(c => !c.is_self_comment);
  const selfComments = commentsSorted.filter(c => c.is_self_comment);

  container.innerHTML = `
    <a class="back-link" href="#">&larr; Back to all TEPs</a>
    <div class="detail-header">
      <h2>TEP-${String(r.tep_number).padStart(4, '0')}: ${esc(r.title)}</h2>
      <span class="badge badge-commented">${esc(r.status || '')}</span>
    </div>
    <div class="detail-meta">
      ${esc((r.authors || []).join(', '))} &middot; ${sourceLink} &middot;
      created ${esc(r.creation_date || '?')}, updated ${esc(r.last_updated || '?')}
      ${r.stub ? ' &middot; <span class="badge badge-skipped">stub (no merged file)</span>' : ''}
    </div>

    <div class="grid">
      <div class="stat"><div class="num">${r.impl_prs.linked_count}</div><div class="label">Linked impl PRs</div></div>
      <div class="stat"><div class="num">${r.impl_prs.discovered_count}</div><div class="label">Discovered impl PRs</div></div>
      <div class="stat"><div class="num">${rate == null ? '—' : rate.toFixed(0) + '%'}</div><div class="label">Under-linking rate</div></div>
      <div class="stat"><div class="num">${r.proposal_pr.review_comment_count}</div><div class="label">Proposal review comments</div></div>
      <div class="stat"><div class="num">${r.proposal_pr.review_rounds_approx}</div><div class="label">Review rounds (approx)</div></div>
      <div class="stat"><div class="num">${r.impl_prs.candidate_count}</div><div class="label">Candidates pending review</div></div>
    </div>

    ${flagsHtml}
    ${gapHtml}

    <section class="block">
      <h3>Divergence from template</h3>
      ${divergenceHtml}
    </section>

    <section class="block">
      <h3>Proposal PR${r.proposal_pr.pr_numbers.length === 1 ? '' : 's'}</h3>
      ${renderProposalPrList(r.proposal_pr.prs)}
    </section>

    <section class="block">
      <h3>Review comments by section</h3>
      <details class="review-comments">
        <summary>${r.proposal_pr.comments.length} total, ${r.proposal_pr.comments_unmapped} unmapped</summary>
        ${otherComments.length ? otherComments.map(c => renderComment(r, c)).join('') : '<p style="color:var(--ink-dim)">No review comments from others captured.</p>'}
        ${selfComments.length ? `<details class="self-comments">
          <summary>${selfComments.length} self-review comment${selfComments.length === 1 ? '' : 's'} from the PR's own author (usually just note-to-self, hidden by default)</summary>
          ${selfComments.map(c => renderComment(r, c)).join('')}
        </details>` : ''}
      </details>
    </section>

    <section class="block">
      <h3>Candidates &mdash; found by search, not yet confirmed relevant (${r.impl_prs.candidate_count})</h3>
      ${r.impl_prs.bot_filtered_count ? `<p style="color:var(--ink-dim);font-size:12.5px;margin-bottom:8px">(${r.impl_prs.bot_filtered_count} bot-authored PR${r.impl_prs.bot_filtered_count === 1 ? '' : 's'} auto-filtered, not shown here or anywhere)</p>` : ''}
      ${renderCandidateList(r.tep_number, r.impl_prs.candidates)}
    </section>

    <section class="block">
      <h3>Implementation PRs &mdash; linked by the TEP author (${linked.length})</h3>
      ${renderImplPrList(r.tep_number, linked)}
    </section>

    <section class="block">
      <h3>Implementation PRs &mdash; discovered by cross-repo search (${discovered.length})</h3>
      ${renderImplPrList(r.tep_number, discovered)}
    </section>

    <section class="block">
      <h3>Implementation PRs &mdash; manually included (${manual.length})</h3>
      ${renderImplPrList(r.tep_number, manual)}
      <button class="mini-btn" onclick="promptInclude(${r.tep_number})" style="margin-top:8px">+ tag a missing PR as relevant</button>
    </section>

    ${renderExcludedList(r.tep_number, r.impl_prs.excluded || [])}
  `;
}

// ---------------------------------------------------------------------------
// Routing
// ---------------------------------------------------------------------------

function render() {
  const hash = location.hash.replace('#', '');
  const listView = document.getElementById('view-list');
  const detailView = document.getElementById('view-detail');
  if (hash.startsWith('tep-')) {
    const n = parseInt(hash.slice(4), 10);
    listView.classList.add('hidden');
    detailView.classList.remove('hidden');
    renderDetail(n);
  } else {
    detailView.classList.add('hidden');
    listView.classList.remove('hidden');
    renderTable();
  }
  window.scrollTo(0, 0);
}

window.addEventListener('hashchange', render);
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('search').addEventListener('input', e => { filterText = e.target.value; renderTable(); });
  document.getElementById('status-filter').addEventListener('change', e => { filterStatus = e.target.value; renderTable(); });
  document.querySelectorAll('thead th[data-key]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (sortKey === key) sortDir *= -1; else { sortKey = key; sortDir = 1; }
      renderTable();
    });
  });
  document.getElementById('export-btn').addEventListener('click', exportCorrections);
  document.getElementById('clear-btn').addEventListener('click', clearCorrections);
  document.getElementById('export-pr-btn').addEventListener('click', exportPrCorrections);
  document.getElementById('clear-pr-btn').addEventListener('click', clearPrCorrections);
  renderCorrectionsBar();
  render();
});
"""


def _status_options(records: list[dict]) -> str:
    statuses: set[str] = {r["status"] for r in records if r.get("status")}
    return "".join(f'<option value="{s}">{s}</option>' for s in sorted(statuses))


def build_html(records: list[dict]) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total_impl = sum(r["impl_prs"]["total_count"] for r in records)
    total_discovered = sum(r["impl_prs"]["discovered_count"] for r in records)
    total_reviews = sum(r["proposal_pr"]["review_comment_count"] for r in records)
    rate = (total_discovered / total_impl * 100) if total_impl else 0.0

    data_json = json.dumps(records, sort_keys=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TEP Explorer</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>TEP Explorer</h1>
  <span class="subtitle">Generated {generated} &mdash; source: processed/latest/per_tep_records.json</span>
  <div class="stats">
    <span><b>{len(records)}</b> TEPs</span>
    <span><b>{total_impl}</b> implementation PRs</span>
    <span><b>{total_reviews}</b> review comments</span>
    <span><b>{rate:.0f}%</b> under-linking rate</span>
  </div>
</header>

<div id="view-list">
  <div class="toolbar">
    <input type="text" id="search" placeholder="Search title, author, or TEP number&hellip;">
    <select id="status-filter">
      <option value="">All statuses</option>
      <option value="__flagged__">&#9888; Flagged for review</option>
      {_status_options(records)}
    </select>
    <span class="count" id="row-count"></span>
  </div>
  <table>
    <thead>
      <tr>
        <th class="num" data-key="tep_number">TEP</th>
        <th data-key="title">Title</th>
        <th data-key="status">Status</th>
        <th data-key="authors">Authors</th>
        <th class="num" data-key="age_days">Age (d)</th>
        <th class="num" data-key="linked_count">Linked</th>
        <th class="num" data-key="discovered_count">Discovered</th>
        <th class="num" data-key="impl_sum">Total</th>
        <th class="num" data-key="under_linking">Under-linked</th>
        <th class="num" data-key="review_comments">Reviews</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<div id="view-detail" class="hidden"></div>

<div class="corrections-bar hidden" id="corrections-bar">
  <span><b id="corrections-count">0</b> pending section correction(s)</span>
  <button id="export-btn">Export sections as JSONL</button>
  <button id="clear-btn">Clear</button>
  <span class="sep"></span>
  <span><b id="pr-corrections-count">0</b> pending PR attribution correction(s)</span>
  <button id="export-pr-btn">Export PR overrides as JSONL</button>
  <button id="clear-pr-btn">Clear</button>
  <textarea id="export-box" class="hidden" rows="4" readonly
    placeholder="Copy this into overrides/section_overrides.jsonl and commit."></textarea>
  <textarea id="pr-export-box" class="hidden" rows="4" readonly
    placeholder="Copy this into overrides/pr_attribution_overrides.jsonl and commit."></textarea>
</div>

<footer>
  Corrections are stored locally in your browser only. Export and commit them to
  <code>overrides/section_overrides.jsonl</code> or <code>overrides/pr_attribution_overrides.jsonl</code>
  for synthesize.py to pick up on the next run &mdash; that's the audit trail.
  &middot; Made with IBM Bob
</footer>

<script type="application/json" id="tep-data">{data_json}</script>
<script>{JS}</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the interactive TEP data explorer")
    parser.add_argument("--records", default="processed/latest/per_tep_records.json")
    parser.add_argument("--out", default="reports/explorer.html")
    args = parser.parse_args(argv)

    records_path = Path(args.records)
    if not records_path.exists():
        print(f"ERROR: {records_path} not found. Run `make synthesize` first.", file=sys.stderr)
        return 1

    records = json.loads(records_path.read_text(encoding="utf-8"))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(records), encoding="utf-8")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
