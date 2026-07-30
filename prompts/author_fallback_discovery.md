# Author-fallback implementation-PR discovery

## Why this exists

`cross_repo_search.py` (Sub-Task 6) can only find a PR that literally contains "TEP-NNNN" or
"TEP NNNN" text somewhere in its title or body. Some genuine implementation PRs never mention
the TEP at all — no number, no title reference, nothing a text search could ever match — yet
they were opened by one of the TEP's own listed authors and their content clearly does what the
TEP proposes.

Verified on 5 real cases in TEP-0173 Phase 0a (2026-07-30): TEP-0005/`pipeline#3142`,
TEP-0014/`pipeline#3087`, TEP-0020/`plumbing#959`, TEP-0028/`pipeline#3390`,
TEP-0031/`cli#1328` — all five had **zero** "TEP" text anywhere (title, body, comments,
reviews — checked directly against the GitHub API, not guessed), and all five were opened by an
author that's an exact match to the TEP's own `authors` frontmatter field. Two mechanical
narrowing attempts were tested and rejected before landing on this prompt-based approach:

- **Date-window scoping** (`[creation_date, last_updated]`) would have missed TEP-0020's own
  target PR — it merged over 6 months after the TEP's `last_updated` field, because doc updates
  don't reliably track ongoing implementation activity. A generous lower bound
  (`merged:>=creation_date`) barely reduces result volume for prolific authors (201→169 for one
  tested author) and isn't worth the residual risk of excluding a late-merged PR.
- **Keyword narrowing** (adding a TEP-title-derived word to the search query) is actively
  unsafe: for TEP-0028, adding `runtime` (a real word from its own title) dropped the result
  count to a tidy 10 — and silently excluded the actual target PR, whose title never used that
  word. A regex or keyword filter cannot tell "irrelevant" from "relevant but phrased
  differently" — that distinction needs to actually read and understand the text.

That's what this prompt is for: cast a wide net (author match, no narrowing), then use an AI
agent's reading comprehension — not a heuristic — to separate real hits from noise. This is
this project's second AI-agent-driven pipeline stage (the first is Sub-Task 8's
`group_conventions.md`) — a deliberate choice for the same reason: some judgments genuinely
need understanding, not string matching, and pretending otherwise produces silently wrong data.

## When to run this

Any TEP where you want more confidence than `total_count == 0` implies "nothing exists" —
most useful for TEPs with `status: implemented` and `impl_prs.total_count == 0` in
`processed/latest/per_tep_records.json` (the same "flagged for review" cohort the explorer's
status filter already surfaces), since those are exactly the cases where the deterministic
pipeline has nothing to show.

## Inputs the agent needs, per TEP

- The TEP number, its `title`, and its **actual content** — read the source `.md` file
  (`community/teps/NNNN-*.md`) directly, at least the Summary/Motivation/Goals sections. The
  frontmatter `title` alone is sometimes uninformative (TEP-0028's is literally
  `task-exec-status-at-runtime`, a slug, not a description) — don't rely on it alone to judge
  relevance later.
- The TEP's `authors` and `collaborators` (from `raw/teps.jsonl`), each with the leading `@`
  stripped.

## Procedure

1. **For each author**, run:

   ```bash
   gh api -X GET "search/issues" -f q="org:tektoncd author:<username> type:pr is:merged" \
     --jq '.total_count, .items[] | {number, title, repo: .repository_url}'
   ```

   No date restriction, no keyword restriction — both were proven unsafe above. If the search
   returns `422 Validation Failed: ... users do not exist ...`, the account is very likely
   deleted (same root cause as TEP-0010's broken commit-to-PR link — see
   `overrides/known_commits.jsonl`). Note it and move to the next author; there's no way to
   search by a deleted account's login.

2. **Skim titles first.** For an author with a long history (dozens to 200+ merged PRs
   org-wide), read through the title list and use judgment to set aside PRs that are obviously
   unrelated by subject (a different feature area entirely, pure dependency bumps, docs-only
   typo fixes, etc.). Be conservative — if a title is ambiguous or you're not sure, keep it on
   the shortlist rather than discard it. This step is about cutting obvious noise, not making
   the real judgment call.

3. **Read the shortlisted candidates properly.** For each, fetch the full title + body (and
   `merged_at` for context) and compare its actual technical content against what the TEP
   proposes. You're looking for whether the PR does the thing the TEP describes — matching
   concepts and behavior, not matching words. A PR titled differently from the TEP but clearly
   implementing the same feature is a hit; a PR that happens to share a word but does something
   unrelated is not.

4. **Known false-positive traps** (all observed on real data this session — don't assume text
   mentioning the right TEP number, or the right author, is automatically sufficient):
   - A PR can genuinely mention "TEP-NNNN" and still be about the *wrong* TEP — e.g. it's
     actually a sibling TEP's own proposal PR that cross-references this one as related work
     (see TEP-0075/TEP-0076 in `_search_confidence()`'s docstring, or TEP-0024's `community#261`
     candidate case).
   - A PR's own self-description can be wrong. TEP-0024's `triggers#783` literally says
     "implements TEP-0023" in its body, merged and attributed there — but a human with domain
     knowledge determined the actual content is TEP-0024's. No text signal resolves this; only
     reading the actual feature being built does.
   - Example/log output embedded in a PR body can coincidentally contain a TEP number that has
     nothing to do with the PR's purpose (TEP-0028's `community#259`, a tooling PR whose body
     includes sample validator output mentioning several TEP numbers as test data).
   - Being the right author is necessary but not sufficient — a prolific contributor works on
     many unrelated things.

## Output

For each PR judged genuinely relevant, write one line matching
`overrides/pr_attribution_overrides.jsonl`'s schema:

```json
{"tep_number": 20, "repo": "plumbing", "pr_number": 959, "action": "include", "reason": "<specific — cite what in the PR matches what the TEP proposes, not just 'looks relevant'>", "created_at": "<ISO 8601 timestamp>"}
```

Don't record anything for candidates read and judged *not* relevant — silence is enough; there's
no existing "candidate" record in the data model for this fallback path to dismiss. If a PR is
genuinely ambiguous even after reading it carefully, say so explicitly in your report rather
than guessing either way — leave it for a human to decide with the PR open in front of them.

**Results from this prompt are proposals, not commits.** Report them for review (the same way
any other correction in this pipeline goes through review) before merging into
`overrides/pr_attribution_overrides.jsonl` — either directly if you're doing the reviewing, or
back to whoever asked for the run. Once accepted, apply with
`uv run scripts/apply_export.py <file>` (or hand-append) and re-run `make synthesize`.

## Known limits

- Deleted GitHub accounts break this path entirely for that author (`author:` search itself
  fails, not just the eventual commit/PR linkage) — same blind spot `known_commits.jsonl`
  exists for, no current workaround.
- No volume cap is applied deliberately (a cap risks the same silent-exclusion failure mode
  keyword-narrowing had) — a prolific author's TEP may mean reading dozens of PR bodies. That's
  the accepted cost of not missing a real hit; an AI agent doing the reading is expected to be
  faster at this than a human doing it by hand, which is the whole premise of this approach.
