# Taxonomy Revision & Tiered Classification — Plan

## Overview

Local-model classification runs against `conventions/seed-taxonomy.yaml` (see
`local-llm-classification.md`) surfaced two separate problems, best fixed together rather than
separately:

1. **The taxonomy conflates location with judgment.** The `artifact` facet's own definition is
   "where in the contribution the feedback applies" - a place - but roughly a third of its
   values (`pr-size`, `functionality`, `incremental-delivery`, `container-image-config`,
   `reconciler-pattern`, `approval-process`, `tep-staging`) actually name a documented standard
   or a judgment, not a place. That's a real cause of model confusion, not just an aesthetic
   complaint: granite specifically has shown a strong tendency to collapse onto whichever facet
   is easiest to over-fire on, and a facet whose own values don't consistently answer the
   question its description asks is exactly the kind of thing that makes collapse worse.
2. **One classification pass can't cheaply do everything worth doing.** Catching every missed
   tag and every taxonomy gap to the same standard, on every comment, means paying for the most
   expensive model on comments that were never ambiguous in the first place. A tiered pipeline -
   cheap pass first, expensive pass only where something was actually uncertain - keeps the
   thorough pass affordable without lowering the bar on quality.

This plan covers both: revising the taxonomy's shape (this session's discussion, working from
real comment examples), and a 3-pass pipeline that uses the revised taxonomy's own structure
(area+nature coupling, principle sparsity) to decide what's worth a second, more expensive look.

---

## Part 1: Taxonomy revision

### Design principle for the taxonomy

**`area` (renamed from `artifact`) + `nature` together identify the object of a comment**, and
are expected on nearly every substantive comment - they're not independent lenses, `nature`
describes the shape of feedback *about* a specific `area`. **`principle` is the independent
one**: how often it's actually present isn't assumed going in - that's an open empirical
question, not a design premise - but it's open to new discoveries in a way `area` isn't (the
location vocabulary should already be closed; `principle` isn't).

### Changes to `area` (formerly `artifact`)

- Rename the facet `artifact` → `area`.
- **Near-mandatory coverage**: unlike `principle`, an `area` match should be present on
  essentially every substantive comment. If no existing value fits, the prompt must require a
  candidate `area` be proposed - however low the confidence - rather than silently returning
  empty. (Contrast with `principle` and `nature`, where a confident empty result stays a
  legitimate, non-flagged outcome.)
- **Drop `pr-size`.** Its own description ("small and self-contained, one commit per PR,
  refactoring separated from feature work") is a 3-way duplicate of existing `nature` values:
  size → `magnitude`, self-contained → `self-containedness`, refactoring-separated →
  `cohesion`. No replacement needed; the three `nature` values already cover it.
- **Move to `principle`** (keeping existing `parent` relationships where set): `functionality`,
  `incremental-delivery`, `reconciler-pattern`, `container-image-config`, `approval-process`,
  `tep-staging`. None of these name a place; all of them name a documented standard or
  convention being invoked - `principle`'s own definition ("which documented value or principle
  it invokes") doesn't require the source to be `design-principles.md` specifically, and
  `approval-process`/`tep-staging` are already sourced from `process/tep-process.md`, the same
  shape as a seeded principle from any other doc. `container-image-config` becomes a child of
  `flexibility` (`parent: flexibility`) rather than a standalone value - it's a narrow instance
  of "avoid being opinionated / hardcoding," not a distinct principle of its own.
- **Keep in `area`, but mark as narrower**: `crd-registration`, `feature-gate-registration`,
  `resource-labeling`. These are completeness checklists tied to a specific place in the code,
  not documented principles - add `parent: code` to each, the same mechanism
  `tekton-api-conventions` already uses for `parent: consistency-with-existing`.
- Remaining `area` values (`pr-description`, `release-notes`, `commit-message`, `docs`, `code`,
  `tests`, `tep-body`) are unchanged - these are the clean "yes, this names a place" set that
  prompted the review in the first place.

### Changes to `nature`

- **Add `none`**: an explicit value meaning "reviewed, and this comment is insignificant"
  (acknowledgments, "lgtm", pure logistics). Replaces relying on an empty `nature` match to mean
  the same thing - an explicit value is easier to get an LLM to commit to than a bare absence,
  and it's what Part 2's pipeline uses to decide which comments need a `principle` pass at all
  (skip anything tagged `nature: none`).
- **Rename `structure`** - confirmed, the name should change for clarity. Proposing
  `formatting` over `cosmetic`: "cosmetic" carries a faint dismissive connotation ("just
  cosmetic") that doesn't fit a taxonomy trying to stay neutral/descriptive, where "formatting"
  states the same thing (form vs. substance) without editorializing. Open to a different pick,
  but `formatting` is the default unless redlined.

### Changes to `principle`

- No structural change - stays "why the feedback matters, which documented value it invokes."
- Explicitly **not** assumed to be rare going in (that assumption was float and walked back
  during this discussion) - but flagging for a closer look in Part 2 is **confidence-gated, not
  presence-gated**: a confident empty result needs no follow-up; a low-confidence match (found
  *something*, not sure it's right) is what escalates to Pass 3. This keeps the expensive pass
  scoped to genuine uncertainty regardless of how common principle matches actually turn out to
  be once real data comes in.

### Worked examples from this discussion (for the eventual few-shot set)

> "This change seems unrelated to deleting completed runs, was this intentional?"

Ground truth (old taxonomy) had `pr-size` + `cohesion` - `pr-size` was wrong, `cohesion` was the
real signal. Under the revised taxonomy: `area: code`, `nature: cohesion`, weak
`principle: feature-justification`.

> "Just to confirm: do we expect this to re-enqueue the item in the workqueue so we'll retry
> with backoff?"

Ground truth had `reconciler-pattern` + `content` (granite found neither). Under the revised
taxonomy: `area: code`, `nature: content`, `principle: reconciler-pattern` - the pattern
reference moves from a fake "location" to where it actually belongs.

---

## Part 2: Tiered classification pipeline

### Design principle for the pipeline

Match model cost to actual uncertainty. Most comments are unambiguous on `area`/`nature` and
have no `principle` at all - a fast, cheap pass handles those correctly the first time. Only
comments where something was genuinely uncertain (missing area/nature, low-confidence
principle, or text that doesn't look fully accounted for by its tags) go to a slower, more
capable pass. granite4.2's built-in thinking mode (`think: low/high` on Ollama's `/api/chat`,
verified against the same endpoint `_call_ollama` already uses) is a natural fit for the
expensive pass, since it's a dial on the same model family rather than a second model to
maintain a separate prompt/schema for.

### Pass 1 — area + nature (fast model, e.g. `think: low`/off)

Identify the `(area, nature)` pair for each comment. If either is missing (no confident match),
flag the comment as missing that specific facet - `area` almost never comes back confidently
empty (see near-mandatory coverage above), so an area-missing flag is itself a signal something
went wrong, not a normal outcome.

### Pass 2 — principle (same or fast model, sees Pass 1's results)

Skip every comment tagged `nature: none` in Pass 1. For the rest, look for `principle`. A
confident empty result is fine, no flag. A low-confidence match escalates to Pass 3. **The
confidence threshold that decides "low" must be a configurable CLI value** (same pattern as the
existing `--facet-coverage-threshold`), not hardcoded - we don't yet know what the right cutoff
is until there's real data to tune against.

### Pass 3 — thinking model, flagged comments only

Sees all of Pass 1 + Pass 2's results as context. Processes, comment by comment, only the
comments flagged by either earlier pass, plus comments flagged by the uncovered-text heuristic
below. This is where `think: high` (or a separate reasoning-capable model) is worth the cost,
because the input set is small by construction.

### Model selection

Every pass's model is a CLI flag, same as `--model` today - no pass is hardcoded to a specific
model. Recommended defaults, pending real timing/quality data (see Open Questions):
`granite4.2:8b` with `think: low` (or off) for Passes 1-2, `granite4.2:30b` with `think: high`
for Pass 3. Reasoning: `8b` is small enough to stay cheap across the full comment set both
passes touch, while `30b` is only worth its extra cost because Pass 3's input is already
filtered down to the flagged subset - using the largest available variant there doesn't
meaningfully change total cost the way it would if it ran on everything.

### Execution mode & backends

The 3-pass structure is itself a form of facet-splitting (area+nature together, principle
separately) and becomes the default under this pipeline, superseding today's flat
`--facet-split` (which asks about all three facets as fully separate calls). Whether a single
"everything in one combined call" mode is still worth keeping is open - but at least keep it
available for a comparison run against the `claude-cli` backend specifically, since fewer,
larger calls may be meaningfully cheaper there than under Ollama, where call count doesn't cost
money the same way.

Also want `bob-cli` as a new `--backend` option, alongside `claude-cli` - shelling out to Bob's
CLI the same way `_call_claude_cli` shells out to `claude -p`. Needs Bob's actual non-interactive
invocation syntax and JSON-schema-output support (if any) confirmed before it can be speced
precisely; `parallel-classify-plan-discussion.md` confirms Bob Shell exists as a distinct agent
tool with its own settings/permission model, but not its CLI invocation shape for this use case.

### Catching missed tags on comments that *did* get tagged

The 3-pass flow above only catches comments where an expected facet came back missing or
uncertain. It doesn't catch the separate case: a comment gets confident `area`/`nature`/
`principle` matches, but still contains additional signal - a second, unrelated concern - that
nothing tagged.

**Mechanism**: add a `quote` field to each match, alongside the existing `evidence` paraphrase -
an exact (or near-exact) literal substring of the comment, used purely mechanically. After
tagging, compute the union of a comment's matched `quote` spans and measure what fraction of
the comment's text falls outside that union - no LLM call needed for this step, just string
math. If the uncovered residual exceeds a configurable threshold, flag the comment for Pass 3
even though it already had confident matches.

**Why a literal quote instead of asking the model to self-report a coverage percentage**: this
project already has a documented case of granite4 producing degenerate/bucketed output when
asked for a self-reported numeric judgment under schema-constrained decoding (`--task score`
mode, see `_call_ollama`'s `ollama_format` docstring on `mellea-adoption`) - a self-reported "%
of comment covered" field risks the same failure mode, on the same model family. A literal
quote also composes correctly across multiple matches by construction (union of spans handles
overlap correctly) where per-match self-reported percentages have no such guarantee, and it's a
free bonus: verifying the quote is an actual substring of the comment is a cheap grounding/
hallucination check that a bare number can't give us. `evidence` stays a paraphrase for
human-readable review tooling (e.g. `scripts/render_comment_comparison.py`); `quote` is a new,
separate field with the opposite constraint.

---

## Open questions

Resolved design questions (configurability, container-image-config's home, the `structure`
rename, default models, execution mode, Bob CLI) have moved into Parts 1-2 above. What's left
is empirical, not design work - values to tune once the pipeline is actually implemented and
run against real data, not decisions to make on paper:

- Exact confidence thresholds for Pass 2's principle-flag and the uncovered-text-residual flag
  (both already specced as CLI-configurable - just don't have good default numbers yet).
- Whether `granite4.2:8b`/`granite4.2:30b` are actually the right sizes for Passes 1-2/Pass 3,
  or whether real timing/quality data (same kind of sweep already run against tep52) points
  elsewhere.
- Bob CLI's actual non-interactive invocation syntax and structured-output support, needed
  before `--backend bob-cli` can be implemented.
