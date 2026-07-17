# TEP-0192 Phase 0a: Corpus Mining — Data Collection Plan

## Overview

This plan covers the data collection, storage, and synthesis work for **Phase 0a (Corpus Mining)**
of [TEP-0192](0192-enhancement-proposal-authoring-skills.md). The goal is to derive TEP conventions
empirically from the `tektoncd/community/teps/` corpus and its associated GitHub PR history, then
present a synthesized candidate set to TEP process maintainers for a keep/drop/modify interview
(Phase 0b: Convention Freeze).

The output feeds directly into the four skill bodies and their reference documents; no separate
project-config layer exists to route them through.

### Scope

Two-pass approach:
- **Pass 1 (targeted)**: a curated sample of ~20–30 implemented TEPs — the most-iterated and
  those with the most implementation PRs. Produces fast signal, validates the pipeline end-to-end,
  and is sufficient for the interview step in most cases.
- **Pass 2 (full corpus)**: expand to all 83 implemented TEPs only if the interview step reveals
  gaps the sample did not cover.

### Repository

Scripts and data live in a new repository **`afrittoli/tep-mining`** (or a branch on
`afrittoli/community` with no PR to the main repo). Nothing from this work is committed to
`tektoncd/community` until the frozen conventions are ready for the skills themselves.

---

## Repository Layout

```
afrittoli/tep-mining/
├── README.md
├── Makefile                        # targets: fetch, parse, process, query
├── pyproject.toml                  # uv-managed: requests, ruamel.yaml, jinja2
├── .env.example                    # GITHUB_TOKEN=, COMMUNITY_REPO_PATH=
│
├── scripts/
│   ├── parse_teps.py               # offline: TEP .md -> raw/teps.jsonl
│   ├── fetch_tep_prs.py            # API: TEP PR metadata + reviews -> community_prs.jsonl, community_pr_reviews.jsonl
│   ├── fetch_impl_prs.py           # API: impl PR metadata + reviews -> impl_prs.jsonl, impl_pr_reviews.jsonl
│   ├── cross_repo_search.py        # API: GH search for uncited TEP references
│   └── synthesize.py               # joins raw/ -> processed/YYYY-MM-DD/per_tep_records.json
│
├── prompts/
│   └── group_conventions.md        # prompt template for AI grouping step
│
├── raw/                            # JSONL, git-tracked, append-only
│   ├── teps.jsonl
│   ├── community_prs.jsonl
│   ├── community_pr_reviews.jsonl
│   ├── impl_prs.jsonl
│   └── impl_pr_reviews.jsonl
│
├── processed/
│   ├── latest -> YYYY-MM-DD/       # symlink to most recent run
│   └── YYYY-MM-DD/
│       ├── per_tep_records.json
│       └── convention_candidates.json
│
└── conventions/                    # human-annotated YAML, one file per convention area
    ├── tep-structure.yaml
    ├── pr-linking.yaml
    ├── status-transitions.yaml
    ├── tracking-issue.yaml
    └── pr-sizing.yaml
```

---

## Storage Design

### Raw layer — JSONL (append-only, git-tracked)

One `.jsonl` file per data type. Each record is a complete, self-describing JSON object. Files
are append-only: fetch scripts check for an existing `id` field before making an API call, so
re-running accumulates new records without touching existing ones. Git diffs are meaningful
(each new record is one added line).

| File | Content | Key field |
|---|---|---|
| `raw/teps.jsonl` | Parsed TEP frontmatter + section structure | `tep_number` |
| `raw/community_prs.jsonl` | GH PR metadata for TEP proposal PRs in `tektoncd/community` | `pr_number` |
| `raw/community_pr_reviews.jsonl` | Review threads on TEP proposal PRs | `pr_number` + `comment_id` |
| `raw/impl_prs.jsonl` | GH PR metadata for implementation PRs across `tektoncd/*` repos | `repo` + `pr_number` |
| `raw/impl_pr_reviews.jsonl` | Review comments on implementation PRs | `repo` + `pr_number` + `comment_id` |

### Processed layer — versioned JSON snapshots

Each processing run writes to a new `processed/YYYY-MM-DD/` directory. Nothing is overwritten.
The `latest` symlink points to the most recent run. Any AI agent or processing script can be
pointed at `processed/latest/` to work from the current best snapshot without hard-coding a date.

### Annotation layer — YAML (human-edited)

One file per convention area under `conventions/`. Each file contains AI-proposed candidate
conventions with observed frequency evidence and a `decision:` field that the human interviewer
fills in during Phase 0b. This is the direct input to Convention Freeze.

```yaml
# conventions/pr-linking.yaml (example structure)
id: pr-link-format
description: "How implementation PRs should reference the TEP they implement"
observed_variants:
  - format: "full URL in PR body"
    frequency: 0.62
  - format: "TEP-NNNN in PR title"
    frequency: 0.31
  - format: "shorthand #N reference"
    frequency: 0.07
ai_recommendation: "Require full URL in PR body, recommend TEP-NNNN in title"
decision: ~        # keep / "modify: <text>" / drop
rationale: ~       # interviewer's reasoning
```

### Ad-hoc querying

A `Makefile` target loads all JSONL into an in-memory DuckDB session for SQL queries during
the synthesis stage. No DuckDB file is stored; JSONL remains the source of truth.

---

## Sub-Tasks

### Sub-Task 1: Bootstrap the `tep-mining` repository

**Intent**: Create the repository and project scaffolding so all subsequent sub-tasks have a
stable place to land.

**Expected Outcomes**:
- `afrittoli/tep-mining` repository exists (or a dedicated branch on `afrittoli/community`)
- `pyproject.toml` and `uv.lock` present with the required dependencies
- `Makefile` with placeholder targets: `parse`, `fetch-tep-prs`, `fetch-impl-prs`, `search`,
  `synthesize`, `query`
- `.env.example` documenting `GITHUB_TOKEN` and `COMMUNITY_REPO_PATH`
- Empty `raw/`, `processed/`, `conventions/`, `scripts/`, `prompts/` directories with
  `.gitkeep` files
- `README.md` describing the pipeline stages and how to run each

**Todo List**:
1. Create repository (or branch)
2. Write `pyproject.toml` with deps: `requests`, `ruamel.yaml`, `python-dotenv`, `jinja2`; add
   `duckdb` as an optional dev dependency for ad-hoc querying
3. Write `Makefile` with stub targets and a `help` default
4. Write `.env.example`
5. Create directory stubs
6. Write `README.md` with pipeline overview and quickstart

**Relevant Context**:
- `tektoncd/community/teps/tools/teps.py` uses `ruamel.yaml` and `uv` — reuse same toolchain
- `GITHUB_TOKEN` env var convention already established in `teps.py` Phase 0c work

**Status**: [ ] pending

---

### Sub-Task 2: Offline TEP parsing (`parse_teps.py`)

**Intent**: Extract all structured data available from the TEP `.md` files without any API
calls, producing `raw/teps.jsonl` as the foundational dataset that all subsequent stages join
against.

**Expected Outcomes**:
- `raw/teps.jsonl` contains one record per TEP with:
  - Frontmatter fields: `tep_number`, `title`, `status`, `authors`, `collaborators`,
    `creation_date`, `last_updated`
  - Derived fields: `age_days` (creation to last-updated), `sections_present` (list of H2/H3
    headings found), `word_count_per_section` (dict), `impl_pr_links` (list of extracted GitHub
    PR URLs from the Implementation section), `impl_pr_links_format` (classified: full-url /
    shorthand / markdown-link)
  - `source_file`: relative path to the `.md` file
- Running the script a second time with new TEP files appends new records (idempotent on
  existing `tep_number` values)
- A summary printed to stdout: total TEPs parsed, breakdown by status, count with/without
  implementation PR links

**Todo List**:
1. Write `scripts/parse_teps.py`:
   - Accept `--teps-dir` (path to `community/teps/`) and `--output` (default `raw/teps.jsonl`)
   - Use `ruamel.yaml` to parse frontmatter (same library as `teps.py`)
   - Extract H2/H3 headings with a regex on the markdown body
   - Extract GitHub PR URLs with a regex: `https://github\.com/tektoncd/[^/]+/pull/\d+`
   - Classify link format per link
   - Load existing JSONL, skip records with matching `tep_number`, append new ones
2. Add `parse` target to `Makefile`
3. Run against the local `community/teps/` checkout and commit the resulting `raw/teps.jsonl`

**Relevant Context**:
- TEP frontmatter required fields: `title`, `authors`, `creation-date`, `status` (from `teps.py`
  line 58: `REQUIRED_FIELDS`)
- Implementation PR link section heading varies: "Implementation Pull request(s)",
  "Implementation PRs", "Implementation Plan" — the regex must be section-agnostic and scan
  the full document body
- Withdrawn/deferred TEPs (6 total) should be included but tagged; they form the contrast set
  mentioned in TEP-0192 Phase 0a

**Status**: [ ] pending

---

### Sub-Task 3: TEP PR discovery via git log

**Intent**: Identify the GitHub PR numbers for TEP proposal PRs from the `community/` git log,
without any API calls. This produces the input list for Sub-Task 4 (fetching review threads).

**Expected Outcomes**:
- A JSON mapping `tep_number -> community_pr_number` for all TEPs whose merge commit is
  recoverable from the git log
- Coverage stats printed: how many implemented TEPs have a recoverable PR number vs. not
- The mapping saved to `raw/tep_pr_map.json` (not JSONL; it's a lookup table, not a record
  stream)

**Todo List**:
1. Write a script section in `parse_teps.py` (or a separate `scripts/map_tep_prs.py`) that:
   - Runs `git log --merges --format="%H %s"` on the `community/` repo using `subprocess`
   - Matches subject lines of the form `Merge pull request #N` combined with a `TEP-NNNN`
     reference in either the subject or the commit body (`git log --format="%H %s %b"`)
   - Falls back to scanning commit subjects for `TEP-NNNN:` pattern on non-merge commits
   - Writes `raw/tep_pr_map.json`
2. Cross-check: for each TEP in `raw/teps.jsonl`, verify the PR number found in the git log
   matches the TEP number; flag mismatches
3. Add `map-prs` target to `Makefile`

**Relevant Context**:
- GitHub merge commits in the community repo have the subject
  `Merge pull request #N from branch/name`, with the TEP title often in the body
- Some early TEPs (0001–0020) may have been merged before consistent PR titling; coverage will
  be partial — record this explicitly in the stats output

**Status**: [ ] pending

---

### Sub-Task 4: Fetch TEP proposal PR review threads (`fetch_tep_prs.py`)

**Intent**: Retrieve review comments on TEP proposal PRs from the `tektoncd/community` GitHub
repo. This is the primary source of signal for `writing-guide.md` and the `tep-review` skill —
it reveals which sections drew repeated iteration and what reviewers rejected.

**Expected Outcomes**:
- `raw/community_prs.jsonl`: one record per TEP proposal PR with title, body, labels, created/
  merged dates, reviewer logins, review decision
- `raw/community_pr_reviews.jsonl`: one record per review comment with `pr_number`, `comment_id`,
  `body`, `path` (file), `line`, `author`, `created_at`
- Incremental: re-running skips PR numbers already present in the JSONL
- Rate-limit aware: honours `GITHUB_TOKEN`; prints remaining rate-limit after each page
- Pass 1 targets the curated sample (~20–30 TEPs); Pass 2 can extend to the full set

**Todo List**:
1. Write `scripts/fetch_tep_prs.py`:
   - Accept `--pr-map` (path to `raw/tep_pr_map.json`), `--sample` (comma-separated TEP
     numbers for Pass 1), `--all` flag for Pass 2
   - Use the GitHub REST API: `GET /repos/tektoncd/community/pulls/{pr_number}/reviews` and
     `GET /repos/tektoncd/community/pulls/{pr_number}/comments`
   - Load existing JSONL files; skip records with matching `pr_number` + `comment_id`
   - Handle pagination (`Link: <...>; rel="next"` header)
   - Respect `X-RateLimit-Remaining`; sleep until `X-RateLimit-Reset` if below a threshold (10)
2. The Pass 1 curated sample (~20–30 TEPs) is determined by the implementer after Sub-Task 2
   produces `raw/teps.jsonl` — the parsed data (age, impl PR link count, status) provides
   the evidence needed to make the selection. Document the chosen sample list in `README.md`
   before running this sub-task.
3. Add `fetch-tep-prs` target to `Makefile`
4. Run Pass 1 and commit resulting JSONL

**Relevant Context**:
- `GITHUB_TOKEN` / `GH_TOKEN` precedence already established in TEP-0192 Phase 0c for `teps.py`
- Unauthenticated rate limit: 60 req/hr; authenticated: 5000 req/hr — always use a token
- Review comments API returns inline comments; PR review API returns top-level review summaries
  with approve/request-changes decisions — fetch both

**Status**: [ ] pending

---

### Sub-Task 5: Fetch implementation PR metadata and reviews (`fetch_impl_prs.py`)

**Intent**: Retrieve metadata and review comments for implementation PRs across `tektoncd/*`
repos. This is the primary source for `tep-pr-conventions` — PR title/body patterns, linking
syntax, PR count and size per TEP, feature-flag usage.

**Expected Outcomes**:
- `raw/impl_prs.jsonl`: one record per (repo, pr_number) with title, body, labels, files
  changed, additions, deletions, linked issues, created/merged dates
- `raw/impl_pr_reviews.jsonl`: review comments on implementation PRs (same schema as
  `community_pr_reviews.jsonl` plus `repo` field)
- Coverage stats: how many PRs in `impl_pr_links` from `raw/teps.jsonl` were successfully
  fetched vs. 404 (deleted/transferred)

**Todo List**:
1. Write `scripts/fetch_impl_prs.py`:
   - Input: reads `raw/teps.jsonl`, extracts all `impl_pr_links` for TEPs in the Pass 1 sample
   - Groups links by `(org, repo, pr_number)` tuples extracted from URLs
   - Fetches `GET /repos/tektoncd/{repo}/pulls/{pr_number}` for each
   - Fetches `GET /repos/tektoncd/{repo}/pulls/{pr_number}/reviews` and `/comments`
   - Incremental: skips existing `(repo, pr_number)` records
   - Same rate-limit handling as Sub-Task 4
2. Add `fetch-impl-prs` target to `Makefile`
3. Run for the Pass 1 sample and commit JSONL

**Relevant Context**:
- Implementation PRs span repos: `pipeline`, `triggers`, `cli`, `dashboard`, `results`,
  `chains`, `operator` — the fetch script must handle all of them generically via the `(repo,
  pr_number)` tuple
- Some early TEPs link to PRs that may be closed/deleted; 404 responses should be recorded
  as `{"repo": ..., "pr_number": ..., "status": 404}` in the JSONL so the gap is visible

**Status**: [ ] pending

---

### Sub-Task 6: Cross-repo TEP reference search (`cross_repo_search.py`)

**Intent**: Augment `raw/impl_prs.jsonl` by discovering implementation PRs that reference a
TEP but were *not* linked in the TEP file itself and therefore not fetched by Sub-Task 5.
This quantifies the under-linking problem documented in TEP-0192 and surfaces PRs that the
offline-link extraction misses. Sub-Task 5 must complete first; this sub-task extends its
output, it does not replace it.

**Expected Outcomes**:
- `raw/impl_prs.jsonl` augmented with newly discovered PRs not already in the file
- A summary report: for each TEP in the sample, how many PRs were found via search vs. already
  linked in the TEP file — the delta is the under-linking rate
- Coverage stats recorded in `processed/YYYY-MM-DD/coverage.json`

**Todo List**:
1. Write `scripts/cross_repo_search.py`:
   - Use the GH search API: `GET /search/issues?q=org:tektoncd+"TEP-{NNNN}"+type:pr` for each
     TEP in the Pass 1 sample
   - The search API has a separate rate limit (30 req/min authenticated); add a 2-second sleep
     between requests
   - For each PR returned, check if it is already in `raw/impl_prs.jsonl` (by `repo` +
     `pr_number`); if not, fetch its full metadata via the REST API and append it — using the
     same fetch logic as Sub-Task 5
   - All records written by Sub-Task 5 carry `discovered_via: "tep_file_link"`; records added
     here carry `discovered_via: "search"` — this field is set at write time, not modified
     retroactively
2. Add `search` target to `Makefile`; document in `README.md` that it must run after
   `fetch-impl-prs`
3. Run for the Pass 1 sample; record coverage stats in `processed/YYYY-MM-DD/coverage.json`

**Relevant Context**:
- TEP-0192 Phase 0a explicitly notes: "Linking discipline is known to be inconsistent, so
  recall will be partial; record coverage stats rather than assuming completeness"
- The search API returns at most 1000 results per query; for strings like "TEP-0075" this is
  unlikely to be an issue, but page through results if `total_count > 30`
- Sub-Task 5 already sets `discovered_via: "tep_file_link"` on every record it writes; this
  sub-task must not modify existing records, only append new ones

**Status**: [ ] pending

---

### Sub-Task 7: Synthesis — join raw data into per-TEP records (`synthesize.py`)

**Intent**: Join all raw JSONL files into a single structured record per TEP, making the data
ready for AI grouping. This is the bridge between raw collection and the convention-candidate
generation step.

**Expected Outcomes**:
- `processed/YYYY-MM-DD/per_tep_records.json`: a JSON array where each element is one TEP with:
  - All frontmatter fields from `raw/teps.jsonl`
  - `proposal_pr`: PR metadata + review summary (sections commented on, net review rounds,
    review decision outcomes) from `raw/community_pr_reviews.jsonl`
  - `impl_prs`: list of implementation PRs with title, body snippet, files changed, link format
    used, discovered-via field
  - `review_signals`: aggregated — which sections had inline review comments, how many rounds,
    what types of changes were requested (inferred from comment text clustering)
  - `divergences_from_template`: sections present in the template but absent in this TEP, and
    vice versa
- `processed/YYYY-MM-DD/coverage.json`: per-TEP counts of linked vs. discovered PRs,
  review comment counts, gaps in the PR map
- `latest` symlink updated to the new date directory

**Todo List**:
1. Write `scripts/synthesize.py`:
   - Load all JSONL files into memory (volume is small enough)
   - For each TEP in the Pass 1 sample, build the per-TEP record by joining on `tep_number`
     and `(repo, pr_number)`
   - For review signals: bucket comments by the section heading they appear closest to in the
     diff; use simple heuristics (keyword matching) to classify comment intent: structural
     feedback / missing-section / wording / scope / approval
   - Write output to `processed/YYYY-MM-DD/` and update `latest` symlink
2. Add `synthesize` target to `Makefile`
3. Add a `query` target that launches an in-memory DuckDB session with all JSONL loaded as
   tables, for ad-hoc SQL exploration during synthesis review

**Relevant Context**:
- The join key between `community_pr_reviews.jsonl` and `teps.jsonl` is via
  `raw/tep_pr_map.json` (TEP number → community PR number)
- "Review rounds" can be approximated as the number of distinct review submission events
  (`submitted_at` timestamps) per reviewer before a PR was merged

**Status**: [ ] pending

---

### Sub-Task 8: AI grouping — convention candidate generation

**Intent**: Use an AI agent to cluster the per-TEP records into candidate conventions, producing
structured YAML files in `conventions/` that serve as the direct input for the human interview
step. The AI groups; the human decides.

**Expected Outcomes**:
- `conventions/tep-structure.yaml` — section presence/ordering patterns across implemented TEPs
- `conventions/pr-linking.yaml` — PR link format variants and frequencies
- `conventions/status-transitions.yaml` — actual status transition paths observed (dates)
- `conventions/tracking-issue.yaml` — whether and how TEPs used tracking issues/task lists
- `conventions/pr-sizing.yaml` — PR count per TEP, file-change distributions, sequencing
  patterns
- Each file follows the annotated YAML schema described in the Storage Design section, with
  `decision: ~` and `rationale: ~` fields left blank for the human interview

**Todo List**:
1. Write `prompts/group_conventions.md`: a prompt template that:
   - Provides the per-TEP records from `processed/latest/per_tep_records.json` as context
   - Instructs the AI to group observations into candidate conventions per area
   - Requires evidence (observed frequency, example TEP numbers) for each candidate
   - Requires an explicit `ai_recommendation` field with a rationale
   - Outputs the five YAML files described above
2. Run the prompt against `processed/latest/per_tep_records.json` using an AI agent
   (Claude or equivalent); review the output for structural correctness before committing
3. Commit the five `conventions/*.yaml` files with `decision: ~` fields blank
4. Re-running this step with a different AI or prompt produces a new set of YAML files in a
   dated subdirectory (e.g. `conventions/2026-07-10/`) to allow comparison; `conventions/*.yaml`
   at the root holds the version taken forward to the interview

**Relevant Context**:
- TEP-0192 Phase 0a step 4: "produce candidate conventions with observed-frequency evidence,
  and a list of divergences between documented process and observed practice"
- The AI grouping step is deliberately separated from the human interview so that the
  interviewer sees evidence-backed proposals, not raw data

**Status**: [ ] pending

---

### Sub-Task 9: Human interview — convention freeze input

**Intent**: Present the AI-grouped convention candidates to TEP process maintainers as a
structured keep/drop/modify questionnaire. The filled-in `conventions/*.yaml` files become
the input to Phase 0b (Convention Freeze).

**Expected Outcomes**:
- All five `conventions/*.yaml` files have `decision:` and `rationale:` fields filled in
- A `conventions/SUMMARY.md` capturing the key decisions made and any open questions deferred
  to Phase 0b
- Divergences between documented process and observed practice are explicitly called out,
  with a decision on each

**Todo List**:
1. Schedule the interview session(s) with TEP process maintainers
   (`OWNERS` in `community/teps/`)
2. Walk through each `conventions/*.yaml` file: present the `observed_variants`,
   `ai_recommendation`, and ask for a `decision`
3. Fill in `decision:` and `rationale:` fields during or immediately after the session
4. Write `conventions/SUMMARY.md` with decisions and any deferred items
5. Commit the annotated `conventions/*.yaml` files and `SUMMARY.md` — this commit is the
   handoff to Phase 0b

**Relevant Context**:
- TEP-0192 Phase 0a step 5: "present the synthesis as keep/drop/modify questions to the TEP
  process maintainers so skills encode deliberate choices, not corpus averages. Values freeze
  into the skills only after this step."
- TEP-0192 Drawbacks: "Corpus-mining conventions from historical TEPs risks calcifying past
  practice into the skills … unless the interview step is actually used to make deliberate
  choices rather than rubber-stamping mined averages."
- This sub-task's completion is the gate for Phase 0b (Convention Freeze) to begin

**Status**: [ ] pending

---

## Data Flow

```
community/teps/ .md files
        |
        v (Sub-Task 2: parse_teps.py)
raw/teps.jsonl
        |
        +----> (Sub-Task 3: map_tep_prs.py)
        |              |
        |              v
        |      raw/tep_pr_map.json
        |              |
        v              v
(Sub-Task 4: fetch_tep_prs.py)
        |
        v
raw/community_prs.jsonl
raw/community_pr_reviews.jsonl

raw/teps.jsonl
        |
        v (Sub-Task 5: fetch_impl_prs.py)
raw/impl_prs.jsonl
raw/impl_pr_reviews.jsonl
        |
        v (Sub-Task 6: cross_repo_search.py - augments impl_prs.jsonl)
        |
        v (Sub-Task 7: synthesize.py)
processed/YYYY-MM-DD/per_tep_records.json
processed/YYYY-MM-DD/coverage.json
        |
        v (Sub-Task 8: AI grouping via group_conventions.md prompt)
conventions/*.yaml  (decision: ~ fields blank)
        |
        v (Sub-Task 9: human interview)
conventions/*.yaml  (decision: fields filled)
conventions/SUMMARY.md
        |
        v
Phase 0b: Convention Freeze  (input to TEP-0192 Phase 1: Author the Skills)
```

---

## References

- [TEP-0192: Enhancement Proposal Authoring Skills](https://github.com/tektoncd/community/blob/main/teps/0192-enhancement-proposal-authoring-skills.md)
- [TEP-0192 Phase 0a description](https://github.com/tektoncd/community/blob/main/teps/0192-enhancement-proposal-authoring-skills.md#phase-0a-corpus-mining)
- [`teps/tools/teps.py`](https://github.com/tektoncd/community/blob/main/teps/tools/teps.py) — ground truth for numbering and scaffolding
- [GitHub REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub Search API](https://docs.github.com/en/rest/search)
