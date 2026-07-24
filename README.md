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
        |
        v  Sub-Task 7: synthesize.py
processed/YYYY-MM-DD/per_tep_records.json
processed/YYYY-MM-DD/coverage.json
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
make query           # Ad-hoc: launch DuckDB session over JSONL files
```

## Sub-Task 4 note

For now, Sub-Task 4 is implemented to run against all mapped TEP PRs by default rather than a curated Pass 1 sample. The `--sample` option remains available in [`scripts/fetch_tep_prs.py`](scripts/fetch_tep_prs.py) for a future curated subset once one is explicitly chosen.

## Detailed Plan

See [data-collection-plan.md](data-collection-plan.md) for the full sub-task breakdown,
storage design, and expected outputs for each stage.

## References

- [TEP-0173: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0173-enhancement-proposal-authoring-skills.md)
- [GitHub REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub Search API](https://docs.github.com/en/rest/search)
