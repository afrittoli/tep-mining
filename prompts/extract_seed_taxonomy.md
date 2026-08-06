# Seed taxonomy extraction

## Why this exists

Review comments raise real, recurring concerns in free text — two comments can raise the same
underlying issue in completely different words, so classifying them by string frequency doesn't
work (see Sub-Task 8 in `data-collection-plan.md`). A taxonomy seeded from vocabulary the
community has already documented, rather than invented or derived from the very comments being
classified, gives classification something traceable to fall back on — and lets a genuinely
undocumented pattern stand out because it matches nothing in the seed set, rather than being
absorbed into an arbitrary invented bucket.

## Sources

Read in full, each covering a different facet. Not every document ends up contributing a value —
several are architecture, feature, or environment documentation rather than a contribution
standard, and get checked and set aside rather than skipped on assumption:

- `design-principles.md` (`tektoncd/community`) — what value or principle a piece of feedback
  might invoke (Reusability, Simplicity, Flexibility, Conformance, Security, API conventions).
- `api_compatibility_policy.md` (`tektoncd/pipeline`) — extends the same facet with concerns
  `design-principles.md` doesn't cover on its own: whether a change is additive or backwards
  incompatible, and the alpha/beta/stable graduation rules.
- `standards.md` (`tektoncd/community`) — what part of a contribution a piece of feedback is
  about, for implementation PRs generally (PR description, commit message, tests, docs, and so
  on).
- `process/tep-process.md` (`tektoncd/community`) — the same "what part of a contribution" facet,
  but for the TEP document itself specifically, not implementation PRs: approval requirements
  (two OWNERs from different companies), and staged authoring (merge early with motivation and
  use cases, add design in follow-up PRs). Neither is covered by `standards.md`, which is scoped
  to implementation-PR review, not TEP-document review.
- `DEVELOPMENT.md` (`tektoncd/pipeline`) — mostly developer-environment setup (SSH, `ko`, cluster
  provisioning, debugger configuration), not a source of any value except "Adding new CRD types":
  a concrete, documented checklist (config YAML, cluster roles, Go structs implementing
  `Defaultable`/`Validatable`, webhook registration, known-types registration) that a reviewer can
  plausibly comment against directly, and that nothing else covers.
- `docs/developers/*.md` (`tektoncd/pipeline`) — a directory of ~14 files, mostly feature
  architecture (how TaskRun pods work, results lifecycle, multi-tenant RBAC, affinity assistant
  behavior) or environment setup (local cluster options, FIPS build flags, tracing setup) — not
  contribution standards, and not a source of any value except three:
  - `api-changes.md`'s Deprecations section (a distinct concern from `api_compatibility_policy.md`
    — sequencing a deprecation, not classifying a change)
  - `feature-versioning.md`'s per-feature-flag checklist (same shape as `DEVELOPMENT.md`'s CRD
    checklist, for a different artifact)
  - `resources-labelling.md`'s standard Kubernetes labels (`app.kubernetes.io/part-of`,
    `component`, `instance`, `name`, `version`) expected on every new resource — a real, narrow,
    citable convention

  `api-versioning.md` and `testing-best-practices.md` are worth reading for depth but reinforce
  values already sourced elsewhere (`api-compatibility`, `tests`) rather than introducing a new
  one.

Find each by checking local checkouts of the relevant repos (e.g. `~/git/github.com/tektoncd/<repo>/`)
before assuming a path; these aren't all in the same repo, or even the same directory.

## Procedure

1. Read each source document in full — not just headings; a heading alone is sometimes too
   terse to write an accurate description from.
2. Propose values for two facets:
   - `principle` — drawn primarily from `design-principles.md`'s own top-level headers, extended
     by `api_compatibility_policy.md` only where it names a distinct concern the first document
     doesn't already cover.
   - `artifact` — drawn from `standards.md`'s own headers, one value per header, extended by
     `process/tep-process.md` for concerns specific to the TEP document itself that
     `standards.md` doesn't cover. Don't merge headers into a combined value yourself, even
     where two headers look related — that's a judgment call for the human review step, not
     this extraction step, and merging early risks hiding a real distinction. Include every
     header, even ones that seem like they'll rarely
     apply — how often something actually shows up is for the classification step to discover,
     not for this step to pre-guess.
3. For each proposed value, write: a short name (2–3 words, kebab-case), a one-line description,
   and a `source` citing the exact document and section it came from. A value with no source
   citation doesn't belong in this file.
4. Don't propose values for a third facet, `nature`. Nothing documented defines it — it's built
   later, bottom-up, from what the classification step in Sub-Task 8 actually finds.
5. Write `conventions/seed-taxonomy.yaml` matching the schema below.

## Output

Each facet carries its own `description` — what that facet means as a category, not just its
values — since `principle`, `artifact`, and `nature` are independent lenses on a comment, not
self-explanatory without one. See `semantics` below for how they combine (they don't: a comment
is classified against each facet independently, can match zero to many values within a facet,
and can match nothing across all three).

Every value also carries a `provenance`: `seeded` (from a document), `discovered` (found during
classification, backed by real example comments), or `suggested` (proposed from a person's own
review experience, not yet backed by either). **This prompt only ever produces `seeded`
values** — that's its whole job, reading documents and citing them. `discovered` values come
from the classification step (Sub-Task 8, step 2); `suggested` values come from a human editing
this file directly, based on their own judgment, independent of this prompt entirely. Don't
invent a `discovered` or `suggested` value yourself when running this prompt — if something
seems real but has no document behind it, leave it out and let a human add it as `suggested`,
or let classification surface it as `discovered`.

```yaml
id: seed-taxonomy
description: "Seed vocabulary for classifying review comments, sourced from documented standards"
semantics: >
  The three facets are independent lenses, not a hierarchy or a joint label. Zero matches in a
  facet is a legitimate outcome, not a gap to fill. Provenance (seeded/discovered/suggested) is
  a property of each value, not of the facet - no facet is exclusive to one provenance.
facets:
  principle:
    description: "Why the feedback matters: which documented value or principle it invokes."
    values:
      - value: simplicity
        description: "..."
        provenance: seeded
        source: "design-principles.md#simplicity"
      # ...
  artifact:
    description: "Where in the contribution the feedback applies."
    values:
      - value: pr-description
        description: "..."
        provenance: seeded
        source: "standards.md#pull-request-description"
      # ...
  nature:
    description: "What kind of fix the feedback asks for (e.g. cosmetic vs. structural vs. logical)."
    values: []   # zero seeded values today - nothing documents this axis; may gain discovered/suggested ones
```

## Review

This file has no `decision:`/`rationale:` fields — it isn't a candidate awaiting a call, it's an
input a person edits directly (add, remove, rename, or merge values) before classification uses
it. Re-running this prompt regenerates a fresh draft if the source documents change; once a
human has edited the file, classification should read the edited version, not a fresh
regeneration.

## Known limits

- Only three documents feed this today. Other repos under `tektoncd/*` may have their own
  documented standards not yet identified (most `CONTRIBUTING.md` files point at general process,
  not content standards, but this hasn't been checked exhaustively) — extend the source list if a
  genuinely relevant one turns up.
