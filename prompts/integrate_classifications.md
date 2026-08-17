# Integrate classifications

## Why this exists

`prompts/classify_review_comments.md` deliberately never touches
`comment_classifications.jsonl`, `conventions/classification_cost_log.md`, or
`reports/explorer.html` — those are shared files, and a per-TEP agent writing to them directly
from its own branch is exactly what caused merge conflicts when TEP-75 and TEP-142 were
classified in parallel (the `classification_cost_log.md` conflict from that run is the reason
this prompt exists). This prompt is the other half: it's the *only* process that writes to those
three files, run once a human has approved one or more `classify/tep<N>` branches (see the
"Human review checkpoint" in `prompts/classify_review_comments.md`). Because it's the only
writer, and it runs the branches through sequentially rather than in parallel, conflicts on the
shared files are structurally impossible here, not just avoided by convention.

This can be run by a human directly, or by an agent session — either way, it's a single linear
process, not something to parallelize across multiple agents. If you're an agent running this,
`.claude/settings.json` / `.bob/settings.json` (see `make permissions MODE=parallel`) may already
have you pre-approved for the operations below; if not, expect normal permission prompts.

## Inputs

- One or more approved `classify/tep<N>` branches, each containing exactly one commit's worth of
  `processed/tep<N>/` files (`classify.jsonl`, `audit.jsonl`, `cost.md`, `explorer.html`,
  optionally `notes.md`, plus the script files).
- The current state of `main` (or whatever branch you're integrating into) — this process reads
  and appends to files already there; it doesn't build anything from scratch.

## Before you start: apply any flagged overrides

If any branch being integrated has a `processed/tep<N>/notes.md`, read it now, before doing
anything else below. It's a per-TEP agent's flag of something it noticed but wasn't scoped to
decide on its own — typically a suspected PR misattribution. Decide whether
`overrides/pr_attribution_overrides.jsonl` needs a new `exclude` entry, and commit it to `main`
**before** step 1. Doing this first means the classification data you're about to merge in is
being judged against already-correct attribution, not retrofitted afterward.

## Procedure

1. **Merge each branch.** From the main checkout, one at a time:

   ```bash
   git merge --no-ff classify/tep<N>
   ```

   Each branch only ever touched its own `processed/tep<N>/` directory — a path no other branch
   or `main` itself writes to — so this merge has no overlapping files to conflict on. If git
   reports a conflict here anyway, stop and look closely before resolving; it means something
   touched a path it shouldn't have (see `prompts/classify_review_comments.md`'s Known gotchas).

2. **Resolve the symlink and append this TEP's classification rows to the real dated file.**
   `processed/latest` is a symlink (e.g. to `processed/2026-08-07/`); `git add
   processed/latest/comment_classifications.jsonl` stages the symlink pointer, not the file it
   points to, and silently produces an empty diff — resolve the real path first.

   ```bash
   REAL_DIR=$(readlink processed/latest)
   TARGET="processed/${REAL_DIR}/comment_classifications.jsonl"
   wc -l "$TARGET"   # count before
   cat processed/tep<N>/classify.jsonl processed/tep<N>/audit.jsonl >> "$TARGET"
   wc -l "$TARGET"   # count after — delta must equal (classify.jsonl lines + audit.jsonl lines)
   ```

3. **Validate the combined file** — same inline checks as `classify_review_comments.md`'s
   "Validate before committing," run now on the *whole* file as defence-in-depth (the per-TEP
   agent already validated its own fragment before committing; this catches anything a merge or
   a skipped review step let through):

   ```bash
   uv run python3 - <<'EOF'
   import json
   import os
   from collections import Counter
   from ruamel.yaml import YAML

   yaml = YAML(typ="safe")
   tax = yaml.load(open("conventions/seed-taxonomy.yaml"))
   valid = {facet: {v["value"] for v in fdef["values"]} for facet, fdef in tax["facets"].items()}

   real_dir = os.readlink("processed/latest")
   rows = [json.loads(l) for l in open(f"processed/{real_dir}/comment_classifications.jsonl")]
   bad = [(r["facet"], r["value"], r["comment_id"]) for r in rows
          if r["facet"] not in valid or r["value"] not in valid[r["facet"]]]
   print("total rows:", len(rows), "| invalid facet/value pairs:", bad)

   dupes = [k for k, v in Counter(
       (r["repo"], r["pr_number"], r["comment_id"], r["facet"], r["value"]) for r in rows
   ).items() if v > 1]
   print("duplicate rows:", len(dupes))
   EOF
   ```

   `bad` must be empty. A nonzero `dupes` count is not automatically wrong — two sibling TEPs
   that legitimately share one implementation PR (see `classify_review_comments.md`'s "shared
   PR" gotcha) can independently produce the same `(comment, facet, value)` row, and that's a
   real, expected duplicate, not a bug. If `dupes` is nonzero, check which PR number(s) are
   involved before assuming something's wrong.

4. **Append the cost log row.** `classification_cost_log.md` is updated by simple append, the
   same pattern as the classifications file above — not reassembled from a complete set of
   fragments, so there's no backfill step and no assembly script:

   ```bash
   cat processed/tep<N>/cost.md >> conventions/classification_cost_log.md
   ```

5. **Rebuild the explorer** with all newly-merged data included:

   ```bash
   make explorer
   ```

6. **Verify**: the "N comment classifications loaded" line `make explorer` prints must match the
   new total from step 2/3.

7. **Commit the three shared files together** — this is the one commit in the whole workflow
   that's allowed to touch them:

   ```bash
   git add "processed/${REAL_DIR}/comment_classifications.jsonl" \
       reports/explorer.html conventions/classification_cost_log.md
   git status --short   # confirm exactly these three files (plus whatever the merge itself staged)
   git commit -m "Integrate classifications: TEP-<N>[, TEP-<M>, ...]"
   ```

   If you're integrating more than one branch in this run, repeat steps 1-6 for each *before*
   this single commit — one integration commit covering every branch in the batch, not one per
   branch. Batching is explicitly supported; there's no requirement to integrate branches
   one at a time.

8. **Push**, then clean up each merged branch's worktree:

   ```bash
   git push
   make worktree-remove TEP=<N>   # for each TEP integrated in this run
   ```

   `worktree-remove` uses `git branch -d` (safe delete, not `-D`) — if a branch somehow wasn't
   actually merged, this fails loudly instead of silently discarding it.

## Known gotchas

- **`processed/latest` is a symlink.** Reading through it is always fine; *writing* through it
  is not — see step 2.
- **A `dupes` count above zero isn't automatically a bug** — see step 3. Check which PR(s) are
  involved before treating it as a problem.
- **Apply flagged overrides before merging, not after** — see "Before you start," above. An
  override applied after the fact means the data you already merged was judged against stale
  attribution.

## Known limits

- This process assumes every branch it's given has already passed its own "Validate before
  committing" checks and a human review (see `classify_review_comments.md`'s Human review
  checkpoint) — it re-validates the combined file as defence-in-depth, not as a substitute for
  that review.
- Like `classify_review_comments.md`, this is meant to be run deliberately, a batch at a time —
  not turned into unattended automation that fires on every push to a `classify/*` branch.
