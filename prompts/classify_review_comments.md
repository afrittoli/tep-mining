# Classify review comments

## Why this exists

`conventions/seed-taxonomy.yaml` is a vocabulary, not a result — Sub-Task 8 only produces
something useful once real review comments are matched against it. This is that matching step:
one TEP's proposal-PR and implementation-PR comments in, rows appended to
`processed/YYYY-MM-DD/comment_classifications.jsonl` out. It's an AI-agent stage (not a script)
because it's a reading-comprehension job — matching a comment's actual point against fifteen-plus
taxonomy values across three facets isn't reducible to keyword rules.

This prompt had no written form for the first several TEPs classified in this pipeline — the
procedure below was worked out live, several bugs deep, across those runs. Writing it down here
is what makes the next TEP delegable to a fresh agent or session instead of requiring someone who
was present for that history.

## Inputs

- `conventions/seed-taxonomy.yaml` — the full file, every facet, not just values you expect to
  match. Re-read `semantics:` at the top before starting: facets are independent (a comment can
  match zero, one, or several values per facet), zero matches across all three facets is the
  normal outcome for most comments, and `parent` is advisory only.
- One TEP's comment data from `processed/latest/per_tep_records.json`: `proposal_pr.comments`
  (list, each carries its own `pr_number` — a proposal can span more than one PR) and
  `impl_prs.items[].comments` (per implementation PR).
- Before starting: sanity-check the TEP is a reasonable classification target. Confirm it has
  real, on-topic implementation PRs (`gh api` the PR titles if in doubt — misattribution happens,
  see Known gotchas) and isn't a topic too peripheral to be representative of typical review
  (e.g. tooling/infra TEPs in a different org from the core project).

## Procedure

1. **Read every comment**, proposal and impl, in full — not a truncated preview. Note `author`,
   `is_self_comment`, `path`/`section` where present.
2. **For each comment, decide per facet**: does it invoke a documented `principle`? Which part of
   the contribution (`artifact`) is it about? What kind of fix (`nature`) is it asking for? A
   comment can legitimately match nothing on any facet — pure acknowledgments ("done", "lgtm",
   "thanks", an emoji reaction) are real, expected zero-matches, not something to force a tag
   onto. Don't tag every comment just to raise a count.
3. **Write one row per match** (not per comment) to a script-local JSONL, in the shape:
   `{"repo": ..., "pr_number": ..., "comment_id": ..., "facet": ..., "value": ..., "confidence":
   <0-1 float>, "evidence": "<short quote or tight paraphrase of the specific text that
   justifies this match>"}`. `evidence` is required and must point at real text in that specific
   comment — never a generic placeholder. A single comment commonly gets several rows (e.g.
   `artifact:tep-body` + `nature:content` + `principle:consistency-with-existing` on the same
   sentence are three separate, real claims, not duplication).
4. **Confidence is a genuine estimate**, not decoration — a comment that's mostly a nit gets a
   low `nature:structure` confidence; a comment making a forceful, specific design argument gets
   a high one. Confidences don't need to be calibrated across TEPs, only honest within one.

A convenient implementation pattern (used throughout this pipeline so far): a small Python
script with `add(comment_id, repo, pr_number, tags)` where `tags` is a list of
`(facet, value, confidence, evidence)` tuples, writing to a scratch `.jsonl` file. Keeping this
script around (even after the run) makes bugs traceable later.

## Validate before merging

Two checks, every time, before this data touches the real classification file:

1. **Every `(facet, value)` pair exists in `conventions/seed-taxonomy.yaml`.** A typo'd or
   invented value silently corrupts aggregate counts later. Load the taxonomy, build a
   `{facet: {valid values}}` map, check every row.
2. **Cross-check tagged comments against the full comment list for that TEP.** Build the set of
   `(repo, pr_number, comment_id)` you *didn't* tag and read through it. Every one should be a
   comment you can justify as a real zero-match (procedural, a pure ack, an emoji). If you find
   one you actually meant to tag, that's a bug — the classification pass silently dropped a row
   it should have written (see Known gotchas). This single check has caught a real bug in most
   TEPs classified so far; don't skip it.

## Audit pass

Once first-pass classification validates clean, run a **separate** pass per
`prompts/audit_classification_coverage.md` — re-reading each already-classified comment fresh
against the full taxonomy to catch matches the first pass missed, tagging any additions
`"source_pass": "audit"`. Also worth a deliberate re-read for: principle/artifact/nature values
that have zero or very few real examples anywhere in the corpus so far (check with
`grep -c '"value": "<value>"' processed/latest/comment_classifications.jsonl`) — a TEP whose
topic plausibly touches one of those is the best chance to find its first real example, and it's
easy to under-tag a value you haven't seen fire yet. A zero-finding audit pass is a legitimate,
honest outcome — don't invent findings to pad the count.

## Merging, building, verifying

1. **Append to the real dated file, never the symlink**: `processed/latest` is a symlink (e.g.
   to `processed/2026-08-07/`); `git add processed/latest/comment_classifications.jsonl` stages
   the symlink pointer, not the file it points to, and silently produces an empty diff. Resolve
   the real path first (`readlink processed/latest`) and operate on
   `processed/<real-date>/comment_classifications.jsonl` directly.
2. **Rebuild the explorer**: `make explorer`. Confirm the reported "N comment classifications
   loaded" count matches your new total.
3. **Verify rendering**, not just the row count — badges are easy to get right in the data and
   wrong in the browser (a missing argument, a stale cache key). A headless-browser check
   (`puppeteer-core` against a local Chrome install, `CLASSIFICATION_INDEX` /
   `classificationBadgesHtml()` are both exposed as globals in `reports/explorer.html`) that
   spot-checks a few comment IDs — including at least one audit-pass row, to confirm the
   `[found on audit pass]` badge styling — is enough; this doesn't need a full UI walkthrough.
4. **Update `conventions/classification_cost_log.md`** with a row for this TEP: comment counts,
   first-pass/audit row counts, and total comment-body character count (sum of `len(c['body'])`
   across every comment processed) as a proxy for the token cost this TEP added.
5. **Commit** the real dated classifications file, `reports/explorer.html`, and the cost log
   together. Don't commit `.coverage` or any local workspace files alongside it.

## Known gotchas (each has actually happened in this pipeline)

- **A row you meant to write silently doesn't exist.** Writing many `add(...)` calls by hand,
  it's easy to fully reason through a comment's classification in your head and then never
  actually call `add()` for it. The untagged-comment cross-check above is what catches this —
  it has caught a real instance in most TEPs run so far.
- **PR misattribution.** A TEP's number can get reassigned over time; a PR whose title cites the
  *old* number for a since-renumbered TEP can auto-confirm as an implementation PR via a
  title-match heuristic even though it has nothing to do with the TEP that number refers to now.
  If an implementation PR's actual content doesn't match the TEP's subject at all, check
  `overrides/pr_attribution_overrides.jsonl` and add an `exclude` entry rather than classifying
  unrelated comments.
- **Length is not a coverage metric.** Do not use comment length vs. tag count as a completeness
  signal for anything — facets are independent axes, so tag count conflates "how many distinct
  facets does this one point touch" with "how many separate points does this comment make." See
  `prompts/audit_classification_coverage.md`'s "Why this exists" for the full reasoning.

## Known limits

- This is a per-TEP, agent-driven pass, run iteratively (pilot a handful, review, expand) per
  Sub-Task 8's plan — not a batch-API pipeline. Don't build automation to loop this unattended
  over the full corpus; each run benefits from the taxonomy-gap awareness a person or agent
  builds up mid-run (e.g. noticing a value has zero real examples yet), which a blind batch loop
  would not have.
- This prompt classifies comments that exist. It doesn't second-guess whether a TEP's comment
  data itself is complete or correctly attributed — that's Sub-Task 6/6b/7's job, upstream of
  this one.
