# TEP-118 classification v2 vs. ground truth

All 315 comments (22 proposal-PR comments on community#774/945/1004, 293 implementation-PR
comments across 16 PRs on pipeline) were read in full and classified against the revised
taxonomy (`area`/`nature`/`principle`) as an independent second pass, then compared to the
original `agent_classify.jsonl` + `agent_audit.jsonl` ground truth after normalizing the old
taxonomy's facet/value names onto the revised one.

## Headline numbers

- Old ground truth (normalized): 452 tags. New pass: 624 tags. Tags present in both: 423.
- Precision (of my new tags, how many match old): 0.678
- Recall (of old tags, how many I reproduced): 0.936
- F1: 0.786
- Bucketing over all 315 comments: **141 clean agree** (old and new tag sets identical),
  **69 expected** (only mechanical differences: `nature: none` newly existing as an explicit
  value, or an `area` tag added alongside tags the old set already had, now that `area` is
  near-mandatory), **105 judgment** (a real difference beyond those two mechanical cases).

## Recurring disagreement patterns

The single largest driver of the judgment bucket, by far, is not a disagreement about
substance: of the 105 judgment comments, 67 are cases where the old ground truth had already
tagged `area` (and often `principle`) for a comment but never added any `nature` value at all,
because `nature` wasn't mandatory under the old taxonomy and was applied inconsistently. My pass
fills in `nature` (almost always `content`) on those same already-recognized substantive
comments per the revised taxonomy's area+nature coupling rule, which is enough to move the
comment out of the "expected" bucket (the bucketing rule only treats `nature: none` and `area`
additions as mechanical, not `nature: content`) even though there's no real disagreement about
whether the comment matters.

The second most common real disagreement is `principle: simplicity`, which the old ground truth
applied fairly liberally to any comment using words like "clean(er)" or "simple/simpler" in an
everyday code-review sense - e.g. "how is this cleaner to what we had?" (a skeptical pushback
question, not an argument for simplicity), "This example is much simpler than the previous,
consider putting it first" (about doc ordering), or a bare `suggestion` test-value diff with
no simplicity language in the comment at all. My pass reserved `principle: simplicity` for
comments making an actual tradeoff argument (simplest solution vs. one that covers every case),
so it came out more conservative here across five of the mismatched comments.

Third, `content` vs. `formatting` is a genuinely fuzzy line for inline suggestion-style code
diffs. A handful of suggested diffs that fix a real correctness bug (e.g. a wrong loop index in
`pipeline_conversion.go`, or field-key corrections) were tagged `content` by me and `formatting`
by the old pass, which seems to have defaulted every inline suggestion-diff to a code-shape tag;
conversely a few doc/test wording suggestions I tagged `formatting` were `content` in the old
pass. This went in both directions in roughly equal measure (about 11 comments total) rather than
being a one-directional gap.

Fourth, my pass used the more specific `nature` values the revised taxonomy documents -
`magnitude`, `cohesion`, `self-containedness` - more readily than the old pass's plainer
`content`/`formatting` tags, for comments specifically about test redundancy, test size, or
scope-bundling (e.g. "can this test case be simplified? (e.g. fewer combinations)" became
`magnitude` where the old tag was generic `content`; "Is this test case different from the
previous one?" became `cohesion` where the old tag was `content`). This is a taxonomy-precision
difference rather than a disagreement about what the comment is about.

Two principle values were, by contrast, applied consistently between passes and worth noting as
reliable: `crd-version-policy` (this TEP touches Pipeline's dual v1/v1beta1 API surface
constantly, and both passes independently flagged the same "keep v1beta1 in sync with v1"
comments) and `incremental-delivery` (this feature landed across 16+ PRs with heavy use of
"let's defer this to a follow-up PR" - both passes caught most of the same instances, including
several of the recurring "opened a separate PR for this" replies scattered across PRs
6237/6235/6341/6418).

A small number of comments (14) were classified with real content by my pass where the old
ground truth had recorded a total zero-match (no tags of any kind). These land in the "expected"
bucket only when the sole addition is a mechanical `area`/`nature: none` pair, but several of
these 14 carry a genuine new `nature: content` finding (e.g. a proposal-PR question from `abayer`
about whether `flags` should be a matrix param, comment 940539779) and so appear as judgment-
bucket recall gains rather than pure ground-truth misses.
