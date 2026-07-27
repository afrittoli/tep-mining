# tep-mining

Corpus mining scripts and data for **Phase 0a** of
[TEP-0173: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0173-enhancement-proposal-authoring-skills.md).

The goal is to derive TEP conventions empirically from the `tektoncd/community/teps/` corpus and
its associated GitHub PR history, then present a synthesised candidate set to TEP process
maintainers for a keep/drop/modify interview (Phase 0b: Convention Freeze).

## Pipeline Stages

```
community/teps/ .md files
        |
        v  Sub-Task 2: parse_teps.py
raw/teps.jsonl
        |
        +----> Sub-Task 3: map_tep_prs.py
        |              |
        |              v
        |      raw/tep_pr_map.json
        |              |
        v              v
Sub-Task 4: fetch_tep_prs.py
        |
        v
raw/community_prs.jsonl
raw/community_pr_reviews.jsonl

raw/teps.jsonl
        |
        v  Sub-Task 5: fetch_impl_prs.py
raw/impl_prs.jsonl
raw/impl_pr_reviews.jsonl
        |
        v  Sub-Task 6: cross_repo_search.py (augments impl_prs.jsonl)
processed/YYYY-MM-DD/coverage.json
raw/impl_pr_discoveries.json
        |
        v  Sub-Task 7: synthesize.py
processed/YYYY-MM-DD/per_tep_records.json
        |
        v  Sub-Task 7: build_explorer.py
reports/explorer.html
        |
        v  Sub-Task 8: AI grouping via group_conventions.md prompt
conventions/*.yaml  (decision: ~ fields blank)
        |
        v  Sub-Task 9: human interview
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
make query           # Ad-hoc: launch DuckDB session over every raw/processed JSONL file
```

## Sub-Task 4 note

For now, Sub-Task 4 is implemented to run against all mapped TEP PRs by default rather than a curated Pass 1 sample. The `--sample` option remains available in [`scripts/fetch_tep_prs.py`](scripts/fetch_tep_prs.py) for a future curated subset once one is explicitly chosen.

## Sub-Task 5 note

Sub-Task 5 also runs against all TEPs with implementation PR links by default, same as Sub-Task 4. The `--sample` option remains available in [`scripts/fetch_impl_prs.py`](scripts/fetch_impl_prs.py). Every record it writes to `raw/impl_prs.jsonl` (including 404s) carries `discovered_via: "tep_file_link"`, since it only ever fetches PRs the TEP author already linked in their own document — see Sub-Task 6 below for the mechanism that finds the rest.

## Sub-Task 6 note

Sub-Task 6 must run **after** `make fetch-impl-prs` — it reads and augments `raw/impl_prs.jsonl`, and needs `raw/tep_pr_map.json` (Sub-Task 3) to tell a TEP's own community proposal/doc PRs apart from a genuine implementation PR discovered elsewhere. Like Sub-Tasks 4 and 5, it runs against all TEPs by default (`--sample` remains available). Newly discovered records carry `discovered_via: "search"`. Per-TEP coverage (linked vs. discovered) is written to `processed/YYYY-MM-DD/coverage.json`, with `processed/latest` symlinked to the most recent run, per the storage design below.

## Sub-Task 7 note

`make synthesize` must run **after** `make search` (it reads `processed/latest/coverage.json` and `raw/impl_pr_discoveries.json`, both Sub-Task 6 outputs) and needs `COMMUNITY_REPO_PATH` set (it parses `teps/tools/tep-template.md.template` for the canonical section list, and each TEP's own file for section-attribution of review comments). `review_signals` is comment counts per section, not the keyword-based intent classification the original plan sketched — see the docstring on `_proposal_pr_summary()` in [`scripts/synthesize.py`](scripts/synthesize.py). Section attribution is a best-effort approximation (a comment's line number mapped to the nearest heading in the *current* merged file, not the file as it stood when the comment was made); `make explorer` builds [`reports/explorer.html`](reports/explorer.html), an interactive, filterable/sortable browser over the joined data, where corrections to a specific comment's section can be made and exported as `overrides/section_overrides.jsonl` — commit that file and re-run `make synthesize` to apply them (git history is the audit trail).

Implementation-PR attribution (linked vs. discovered vs. manual) is correctable the same way. Every impl PR shown for a TEP carries an `attribution_source` (`tep_file_link`, `search`, or `manual_include`) and `evidence` explaining why the algorithm picked it — the linked URL for a link, the matched search snippet for a discovery, the human's stated reason for a manual inclusion — so a reviewer can see *why* without re-deriving it. Two corrections are possible in the explorer, both exported as `overrides/pr_attribution_overrides.jsonl`: flag a wrongly-attributed PR as **not relevant** (`action: "exclude"`), or tag a **missing** PR as relevant (`action: "include"`). An `include` naming a PR nothing has fetched yet shows as `pending_fetch` until you run `make apply-pr-overrides`, which fetches just those PRs into `raw/impl_prs.jsonl`/`raw/impl_pr_reviews.jsonl` (tagged `discovered_via: "manual_override"`) so the next `make synthesize` can show its title and stats instead of a placeholder. `not_found` (as opposed to `pending_fetch`) means the PR *was* fetched and GitHub genuinely returned 404 — see the `status` field built in `_impl_prs_summary()` in [`scripts/synthesize.py`](scripts/synthesize.py).

## Detailed Plan

See [data-collection-plan.md](data-collection-plan.md) for the full sub-task breakdown,
storage design, and expected outputs for each stage.

## References

- [TEP-0173: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0173-enhancement-proposal-authoring-skills.md)
- [GitHub REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub Search API](https://docs.github.com/en/rest/search)
