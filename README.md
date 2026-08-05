# tep-mining

Corpus mining scripts and data for **Phase 0a** of
[TEP-0173: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0173-enhancement-proposal-authoring-skills.md).

The goal is to derive TEP conventions empirically from the `tektoncd/community/teps/` corpus and
its associated GitHub PR history, then present a synthesised candidate set to TEP process
maintainers for a keep/drop/modify interview (Phase 0b: Convention Freeze).

## Pipeline Stages

Each stage is tagged `[script]` (deterministic `make` target, reproducible unattended),
`[AI agent]` (needs an agentic AI session to read a `prompts/*.md` file and execute it — not
run-to-run reproducible, which is why every one writes proposals to a reviewable file instead of
committing directly), or `[human]` (a review/decision gate, no automation). See
[data-collection-plan.md](data-collection-plan.md#data-flow) for the full diagram including
Sub-Task 8, omitted here for brevity — this is the condensed operational version.

```
community/teps/ .md files
        |
        v  [script] Sub-Task 2: parse_teps.py
raw/teps.jsonl
        |
        +----> [script] Sub-Task 3: map_tep_prs.py
        |              |
        |              v
        |      raw/tep_pr_map.json
        |              |
        v              v
[script] Sub-Task 4: fetch_tep_prs.py
        |
        v
raw/community_prs.jsonl
raw/community_pr_reviews.jsonl

raw/teps.jsonl
        |
        v  [script] Sub-Task 5: fetch_impl_prs.py
raw/impl_prs.jsonl
raw/impl_pr_reviews.jsonl
        |
        v  [script] Sub-Task 6: cross_repo_search.py (augments impl_prs.jsonl)
processed/YYYY-MM-DD/coverage.json
raw/impl_pr_discoveries.json
        |
        v  [AI agent] Sub-Task 6b: author_fallback_discovery.md prompt (on demand)
        v  [human] review proposed includes/excludes
overrides/pr_attribution_overrides.jsonl
        |
        v  [script] Sub-Task 7: synthesize.py
processed/YYYY-MM-DD/per_tep_records.json
        |
        v  [script] Sub-Task 7: build_explorer.py
reports/explorer.html
        |
        v  [script]+[AI agent]+[human] Sub-Task 8 (see data-collection-plan.md)
conventions/*.yaml  (decision: ~ fields blank, 6 files)
        |
        v  [human] Sub-Task 9: human interview
conventions/*.yaml  (decision: fields filled)
conventions/SUMMARY.md
        |
        v
Phase 0b: Convention Freeze
```

## Quickstart

```bash
# 1. Install dependencies (requires uv)
uv sync

# 2. Copy and fill in environment variables
cp .env.example .env
# edit .env: set GITHUB_TOKEN and COMMUNITY_REPO_PATH

# 3. Run each stage in order
make parse           # Sub-Task 2: parse TEP .md files -> raw/teps.jsonl
make map-prs         # Sub-Task 3: git log -> raw/tep_pr_map.json
make fetch-tep-prs   # Sub-Task 4: fetch TEP proposal PR reviews
make fetch-impl-prs  # Sub-Task 5: fetch implementation PR metadata
make search          # Sub-Task 6: cross-repo TEP reference search
make synthesize      # Sub-Task 7: join raw data -> processed/
make explorer        # Sub-Task 7: build the interactive data explorer -> reports/explorer.html
make apply-pr-overrides  # Optional: fetch metadata for a manually-"included" PR, then re-run synthesize
make apply-export FILE=path/to/export.jsonl  # Merge an explorer-exported corrections file into overrides/
make query           # Ad-hoc: launch DuckDB session over every raw/processed JSONL file

# 4. Sub-Task 8: review-comment taxonomy - NOT YET IMPLEMENTED (status: pending),
#    shown here as the planned sequence once built - see data-collection-plan.md for the full flow
#   [AI agent] run prompts/extract_seed_taxonomy.md -> conventions/seed-taxonomy.yaml (draft)
#   [human]    review/edit conventions/seed-taxonomy.yaml before it's used for anything
#   [AI agent] classify review comments against the reviewed seed taxonomy -> conventions/review-taxonomy.yaml
make validate-conventions  # [script] mechanical check: every count in review-taxonomy.yaml traces to real comment text
```

## Sub-Task 2 note

`_extract_pr_links()` only trusts PR links found under a heading naming the TEP's own implementation-PR list (`## Implementation Pull Requests` and real corpus variants like `Implementation Pull request(s)` / `Implementation PRs`, at any `##`/`###` level) — not the whole document body. TEPs commonly link *other* TEPs' proposal PRs as related work throughout Motivation/Requirements/Design Details (e.g. "see also TEP-0076"); a whole-body scan swept those up as if they were this TEP's own implementation (confirmed on TEP-0075: 3 of its 19 "linked" PRs were actually TEP-0048/0074/0076's own proposal PRs). A TEP with no recognizable heading gets zero linked PRs rather than falling back to the whole-body scan — a deliberate precision-over-recall choice: only 62 of 147 TEPs have a heading a matcher can find, so this does cost real recall for the other 85 (up to 160 fewer total linked PRs corpus-wide), but cross-repo search (Sub-Task 6) and manual `include` overrides exist specifically to claw back genuine misses one at a time, auditably — see `_implementation_section_text()` in [`scripts/parse_teps.py`](scripts/parse_teps.py).

## Sub-Task 4 note

For now, Sub-Task 4 is implemented to run against all mapped TEP PRs by default rather than a curated Pass 1 sample. The `--sample` option remains available in [`scripts/fetch_tep_prs.py`](scripts/fetch_tep_prs.py) for a future curated subset once one is explicitly chosen.

## Sub-Task 5 note

Sub-Task 5 also runs against all TEPs with implementation PR links by default, same as Sub-Task 4. The `--sample` option remains available in [`scripts/fetch_impl_prs.py`](scripts/fetch_impl_prs.py). Every record it writes to `raw/impl_prs.jsonl` (including 404s) carries `discovered_via: "tep_file_link"`, since it only ever fetches PRs the TEP author already linked in their own document — see Sub-Task 6 below for the mechanism that finds the rest.

## Sub-Task 6 note

Sub-Task 6 must run **after** `make fetch-impl-prs` — it reads and augments `raw/impl_prs.jsonl`, and needs `raw/tep_pr_map.json` (Sub-Task 3) to tell a TEP's own community proposal/doc PRs apart from a genuine implementation PR discovered elsewhere. Like Sub-Tasks 4 and 5, it runs against all TEPs by default (`--sample` remains available). Newly discovered records carry `discovered_via: "search"`. Per-TEP coverage (linked vs. discovered) is written to `processed/YYYY-MM-DD/coverage.json`, with `processed/latest` symlinked to the most recent run, per the storage design below.

The search query matches two surface forms in one call: zero-padded `"TEP-0109"` and non-padded space-separated `"TEP 109"` — found necessary via a real merged PR (`chains#491`, TEP-0109) whose title/body only ever wrote "TEP 109", never "TEP-0109", so the original dash-only query never saw it at all. See the docstring on `_search_prs_for_tep()` in [`scripts/cross_repo_search.py`](scripts/cross_repo_search.py) for the full empirical case (why this variant and not others).

## Sub-Task 6b note

Some implementation PRs never mention the TEP at all — no number, no title reference, nothing text search could ever match — yet were opened by one of the TEP's own listed authors and clearly do implement it. Verified on 5 real cases: zero "TEP" text anywhere in any of them (checked directly against the API, not guessed), all opened by an exact-match listed author. Narrowing the candidate list mechanically (date window, keyword) was tested and rejected — both silently exclude real hits (see [`prompts/author_fallback_discovery.md`](prompts/author_fallback_discovery.md) for the specific cases). This is an AI-agent task, not a script: run the prompt against a TEP with `impl_prs.total_count == 0`, and it searches by author (no narrowing), reads the shortlisted candidates against the TEP's actual content, and proposes `include` records for review — same audit trail as every other correction (`overrides/pr_attribution_overrides.jsonl`, applied via `apply_export.py`).

## Sub-Task 7 note

`make synthesize` must run **after** `make search` (it reads `processed/latest/coverage.json` and `raw/impl_pr_discoveries.json`, both Sub-Task 6 outputs) and needs `COMMUNITY_REPO_PATH` set (it parses `teps/tools/tep-template.md.template` for the canonical section list, and each TEP's own file for section-attribution of review comments). `review_signals` is comment counts per section, not the keyword-based intent classification the original plan sketched — see the docstring on `_proposal_pr_summary()` in [`scripts/synthesize.py`](scripts/synthesize.py). Section attribution is a best-effort approximation (a comment's line number mapped to the nearest heading in the *current* merged file, not the file as it stood when the comment was made); `make explorer` builds [`reports/explorer.html`](reports/explorer.html), an interactive, filterable/sortable browser over the joined data, where corrections to a specific comment's section can be made and exported as `overrides/section_overrides.jsonl` — commit that file and re-run `make synthesize` to apply them (git history is the audit trail).

Implementation-PR attribution (linked vs. discovered vs. manual) is correctable the same way. Every impl PR shown for a TEP carries an `attribution_source` (`tep_file_link`, `search`, or `manual_include`) and `evidence` explaining why the algorithm picked it — the linked URL for a link, the matched search snippet for a discovery, the human's stated reason for a manual inclusion — so a reviewer can see *why* without re-deriving it. Two corrections are possible in the explorer, both exported as `overrides/pr_attribution_overrides.jsonl`: flag a wrongly-attributed PR as **not relevant** (`action: "exclude"`), or tag a **missing** PR as relevant (`action: "include"`). An `include` naming a PR nothing has fetched yet shows as `pending_fetch` until you run `make apply-pr-overrides`, which fetches just those PRs into `raw/impl_prs.jsonl`/`raw/impl_pr_reviews.jsonl` (tagged `discovered_via: "manual_override"`) so the next `make synthesize` can show its title and stats instead of a placeholder. `not_found` (as opposed to `pending_fetch`) means the PR *was* fetched and GitHub genuinely returned 404 — see the `status` field built in `_impl_prs_summary()` in [`scripts/synthesize.py`](scripts/synthesize.py).

Three more corrections, driven by a manual review of TEP-0137's data: bot-authored PRs and review comments (`login` ending in `"[bot]"` — dependabot, github-actions, etc.) are filtered out entirely, no human review needed — there's no judgment call in "dependabot bumped a version and the vendored code happens to mention this TEP." A search-discovered PR that isn't explicitly linked by the TEP author gets no free pass either: unless its title names the TEP (e.g. `[TEP-0137] ...` or `TEP-0052: ...`, checked at/near the start of the title) or its own author is one of the TEP's listed authors, it's parked in a **Candidates** section — visible per-TEP in the explorer with the match evidence and *why* it's unconfirmed, but excluded from every count (`discovered_count`, `total_count`, under-linking rate) until a human confirms it (the same `include` override) or dismisses it (the same `exclude` override) — this is what catches the concrete failure mode that motivated it: a downstream repo's dependency-bump PR that happens to vendor in a commit mentioning the TEP, which is neither authored by a TEP author nor named after the TEP. Linked PRs skip this gate entirely, since the TEP author linking it *is* the confirmation regardless of who opened it. Finally, review comments from a PR's own author are still collected and counted exactly as before, just **grouped and collapsed by default** in the explorer (`is_self_comment` on each comment) — usually note-to-self, rarely the reviewer feedback the review-comment view exists to surface.

The author-match trust signal is withheld for `community`-repo search hits specifically: a `community` PR is almost always *some* TEP's own proposal/doc PR, and closely related TEPs frequently share an author, so "this PR's author is a listed author of TEP-X" says nothing about whether the PR is actually *about* TEP-X (found via TEP-0075: a PR that was TEP-0076's own proposal, opened by a shared author, was being auto-confirmed as TEP-0075's implementation). Only a title match confirms a `community` hit; code repos keep both signals.

Implementation-PR review comments (`raw/impl_pr_reviews.jsonl`, ~10K records) are no longer collapsed to a bare count — each confirmed impl PR carries its own `comments` list (bot-filtered and `is_self_comment`-flagged the same way proposal-PR comments are), shown in the explorer as a per-PR expandable toggle, collapsed by default given the volume. The proposal-PR "Review comments by section" panel is now collapsed by default too, for the same reason.

`flags` on each TEP record surface data worth a second look without opening every TEP by hand: currently just "marked `implemented` but zero confirmed impl PRs" (split into `implemented_no_prs` vs. `implemented_only_candidates` depending on whether unconfirmed candidates exist) — see `_consistency_flags()` in [`scripts/synthesize.py`](scripts/synthesize.py). The explorer shows a warning badge next to a flagged TEP's title in the master table and a "Flagged for review" entry in the status filter.

The master table's "Linked"/"Discovered" columns are individually sortable now (previously "Linked" wasn't wired to a real sort key at all, and "Discovered" was silently sorting by total instead), and a new "Total" column (linked + discovered) is sortable too.

Per-PR badges no longer show `review_decision` (APPROVED / CHANGES_REQUESTED / COMMENTED) — that field is computed as "did *any* review, ever, hit this state" with a fixed priority, so it goes stale the moment a reviewer changes their mind after re-reviewing (confirmed on real data: `chains#590` and `chains#599` both got re-approved by the *same* reviewer who'd first requested changes, yet kept showing "changes requested" forever, since request-changes always wins the priority regardless of what came after). Fetch scripts now also capture each PR's `state` (open/closed); the badge shows the PR's actual disposition instead — **merged**, **closed, not merged**, or **open** — a more stable, honest signal than a review-event history that was never being interpreted with recency in mind.

A checkbox next to the status filter flips it from "show only this status" to "show everything except" (works on the "Flagged for review" pseudo-status too).

Some implementations exist only as a bare commit with no retrievable PR — e.g. the commit's author account was later deleted, which can sever GitHub's own commit-to-PR association even though the code genuinely shipped (confirmed on TEP-0010: `GET /commits/{sha}/pulls` returns empty for that specific commit, but works correctly for other commits; TEP-0021's case is similar but the account isn't deleted — the commit likely predates or bypassed the PR workflow entirely). Since there's no PR, there are no review comments to collect, so this is tracked separately in `overrides/known_commits.jsonl` (`{tep_number, repo, commit_sha, note}`) rather than shoehorned into the PR-attribution mechanism above. The explorer shows these read-only, per TEP; they never count toward `total_count`, `candidate_count`, or any of the impl-PR stats — but a TEP marked `implemented` with a known commit and nothing else no longer trips the `implemented_no_prs` flag, since a human has already explained the gap.

"Tag a missing PR or commit as relevant" now takes a single GitHub URL plus a reason, not three separate prompts. The URL is parsed client-side: a `.../pull/N` link becomes a `pr_attribution_overrides.jsonl` `include`; a `.../commit/<sha>` link becomes a `known_commits.jsonl` entry; anything else is rejected with an explanation rather than silently misfiled. Both shapes share the same pending-corrections count and export button — a single export can contain a mix of both, since `apply_export.py` already routes each record by its own shape.

Corrections made in the explorer now trigger a real file download (`*.export.jsonl`) instead of requiring copy-paste out of the textarea. `scripts/apply_export.py` (`make apply-export FILE=...`) merges a downloaded export into the right `overrides/*.jsonl` — auto-detected from the record's own shape, since each export only ever contains one correction type — skipping any record that's already present, so it's safe to run more than once on the same or an overlapping export.

## Sub-Task 8 note

Review-comment content needs a different method than headings/link-formats: two comments can
raise the same concern in completely different words, so string-frequency clustering (right for
rigid template vocabulary) is the wrong tool here. Instead, `prompts/extract_seed_taxonomy.md`
reads this org's own documented standards — `design-principles.md`, `standards.md`,
`api_compatibility_policy.md` (in `tektoncd/pipeline`, not `community`) — and proposes a seed
vocabulary for two facets (`principle`, `artifact`), each value traceable to a real doc section;
a human reviews `conventions/seed-taxonomy.yaml` before it's used for anything. Comments are then
classified multi-label and confidence-scored against that seed vocabulary — not binary, not
single-label, since a comment routinely spans more than one concern — and anything that doesn't
fit an existing value proposes a new one, which is the actual mechanism for surfacing
conventions nobody documented (the stated goal of this sub-task). A third facet, `nature`
(cosmetic vs. structural vs. logical), has no seed at all and is built bottom-up entirely from
what the classification pass finds. Scoped to the Pass-1 sample for now, not the full 12,779
comments corpus-wide — full coverage would need batch LLM-API-calling infrastructure this
pipeline doesn't have yet, deferred unless Sub-Task 9's interview shows the sample isn't enough.

## Detailed Plan

See [data-collection-plan.md](data-collection-plan.md) for the full sub-task breakdown,
storage design, and expected outputs for each stage.

## References

- [TEP-0173: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0173-enhancement-proposal-authoring-skills.md)
- [GitHub REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub Search API](https://docs.github.com/en/rest/search)
