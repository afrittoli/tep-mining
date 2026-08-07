# Audit classification coverage

## Why this exists

Classifying a comment (`prompts/extract_seed_taxonomy.md`'s output applied to real comment
text) and checking whether that classification is *complete* are different jobs, and doing both
in one pass is unreliable — whatever blind spot caused a tag to be missed the first time is not
obviously visible to the same read that missed it. A numeric proxy (comment length vs. tag
count) was considered and rejected: facets are independent axes, so one real point in a comment
can legitimately touch several facets at once (e.g. `artifact:tep-body` + `nature:content` +
`principle:feature-graduation` + `principle:crd-version-policy` on a single sentence is two
distinct claims — `feature-graduation` and `crd-version-policy` — not four; `tep-body` and
`content` are the shared coordinates both claims sit at, not separate points). Tag count doesn't
measure what "coverage" needs it to measure. This is a reading-comprehension job, so it gets a
second, separate agent pass instead.

## Inputs, per comment already classified

- The full comment body (not a snippet).
- Every classification row already recorded for that comment (`facet`, `value`, `confidence`,
  `evidence`) from `processed/latest/comment_classifications.jsonl`.
- The full `conventions/seed-taxonomy.yaml` — not just the values already applied to this
  comment; a missed match is by definition a value that *wasn't* applied.

## Procedure

For each comment:

1. Read the comment body in full, then its existing tags with their `evidence`.
2. Judge whether the existing tags account for everything substantive in the comment. A
   comment can legitimately have residual content that's genuinely untaggable (pleasantries,
   pure quoting, procedural coordination) — that's not a gap, don't force a match onto it.
3. For each real gap found, decide which of two cases it is:
   - **An existing taxonomy value fits, but wasn't applied.** Propose it as an additional
     classification row, same shape as any normal match, with real `evidence` quoting or
     tightly paraphrasing the missed part of the comment.
   - **Nothing in the current taxonomy covers it.** Don't force the nearest existing value —
     flag the specific text fragment and describe a candidate new value (name, description,
     which facet it belongs in), the same way `tep-body` was discovered. This is a proposal,
     not an addition to `seed-taxonomy.yaml` — new values still go through the same human
     review gate every other addition has gone through.
4. If a comment's existing tags already look complete, say so explicitly rather than staying
   silent — a reviewer needs to know "checked, nothing missing" is a real outcome, not
   indistinguishable from "not checked yet."

## Output

Two kinds of finding, kept distinct from first-pass classification rather than blended in
invisibly:

- **Missed existing match** — a normal `comment_classifications.jsonl` row (`repo`,
  `pr_number`, `comment_id`, `facet`, `value`, `confidence`, `evidence`), plus `source_pass:
  "audit"` so the record of which pass actually found it doesn't get lost.
- **Uncovered fragment** — `{repo, pr_number, comment_id, fragment, candidate_facet,
  candidate_value, candidate_description}`, a proposal for a human to review before it becomes
  a real `suggested` taxonomy value.

## Known limits

- This only re-examines comments that were already classified once — it doesn't independently
  discover comments that got zero tags and should have gotten some (that's still just regular
  classification, run again if the first pass is suspected to have skipped real comments
  entirely, not this prompt's job).
- No volume cap, same reasoning as `author_fallback_discovery.md`: capping risks the same
  silent-exclusion failure keyword-narrowing had elsewhere in this pipeline.
