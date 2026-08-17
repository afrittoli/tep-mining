# Classify review comments

## Why this exists

`conventions/seed-taxonomy.yaml` is a vocabulary, not a result — Sub-Task 8 only produces
something useful once real review comments are matched against it. This is that matching step:
one TEP's proposal-PR and implementation-PR comments in, classification rows out — written to
`processed/tep<N>/classify.jsonl` and `processed/tep<N>/audit.jsonl` inside your own isolated
worktree, never appended to the shared `comment_classifications.jsonl` directly. A separate
process does that after a human approves your branch (see "Next step" at the end of this file).
It's an AI-agent stage (not a script) because it's a reading-comprehension job — matching a
comment's actual point against fifteen-plus taxonomy values across three facets isn't reducible
to keyword rules.

This prompt had no written form for the first several TEPs classified in this pipeline — the
procedure below, **including the exact shell/Python commands**, was worked out live, several
bugs deep, across those runs. It was later restructured (see `parallel-classify-plan.md`) so
several agents — any mix of tools, e.g. Claude Code on one TEP and Bob Shell on another — can
classify different TEPs at the same time without ever touching each other's work or the shared
files. The commands are plain `python3`/`bash`/`git` — nothing here assumes any particular AI
coding tool.

Environment note: this project manages Python dependencies with `uv` (see `pyproject.toml`).
Every Python snippet below should run as `uv run python3 ...`. If your shell has a stray
`VIRTUAL_ENV` pointing at an unrelated project, `uv` will warn about it — that warning is
harmless; the commands still use this project's own `.venv`. Add `--active` after `uv run` only
if you specifically want to force the currently-active venv instead.

## Setup: isolate your worktree

Before anything else, from the main checkout:

```bash
make worktree-classify TEP=<N>
```

This creates a dedicated git worktree and branch (`classify/tep<N>`) and prints a `cd` command —
run it. Everything from here on happens inside that worktree, never in the main checkout, and
never in another agent's worktree. Then create your output directory:

```bash
mkdir -p processed/tep<N>
```

Every file you write from this point on goes under `processed/tep<N>/` — never the worktree
root, never anywhere else. That's what lets your work and another agent's simultaneous work on a
different TEP combine later without conflict.

## Inputs

- `conventions/seed-taxonomy.yaml` — the full file, every facet, not just values you expect to
  match. Re-read `semantics:` at the top before starting: facets are independent (a comment can
  match zero, one, or several values per facet), zero matches across all three facets is the
  normal outcome for most comments, and `parent` is advisory only.
- One TEP's comment data from `processed/latest/per_tep_records.json` (a symlink — reading
  through it is always fine, only writing through it is not; see Known gotchas). Pull it like
  this (replace `TEP_NUMBER`):

  ```bash
  uv run python3 - <<'EOF'
  import json
  TEP_NUMBER = 76  # <- set this
  records = json.load(open('processed/latest/per_tep_records.json'))
  rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
  print("TITLE:", rec['title'], "| STATUS:", rec['status'])
  print("proposal comments:", len(rec['proposal_pr']['comments']),
        "pr_numbers:", rec['proposal_pr']['pr_numbers'])
  for pr in rec['impl_prs']['items']:
      print(f"pr#{pr['pr_number']} title={pr.get('title','')[:60]!r} "
            f"comments={len(pr['comments'])}")
  EOF
  ```

  Then dump the actual comment text you'll classify (proposal PRs use `community` as `repo`;
  implementation PRs use the repo the TEP belongs to, e.g. `pipeline`, `triggers`, `chains`):

  ```bash
  uv run python3 - <<'EOF'
  import json
  TEP_NUMBER = 76  # <- set this
  records = json.load(open('processed/latest/per_tep_records.json'))
  rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
  for c in rec['proposal_pr']['comments']:
      print(f"[{c['comment_id']}] pr#{c['pr_number']} sec={c.get('section')!r} "
            f"self={c.get('is_self_comment')} {c['author']}: {c['body']}")
  for pr in rec['impl_prs']['items']:
      for c in pr['comments']:
          print(f"[{c['comment_id']}] pr#{pr['pr_number']} path={c.get('path')!r} "
                f"self={c.get('is_self_comment')} {c['author']}: {c['body']}")
  EOF
  ```

  Read full comment bodies, not truncated ones — truncate only the terminal preview if the
  output is unwieldy, never the text you're actually classifying.

- Before starting: sanity-check the TEP is a reasonable classification target. Confirm it has
  real, on-topic implementation PRs — `gh api repos/<org>/<repo>/pulls/<n> --jq .title` the PR
  titles if in doubt, misattribution happens (see Known gotchas) — and isn't a topic too
  peripheral to be representative of typical review (e.g. tooling/infra TEPs in a different org
  from the core project).

## Procedure

1. **Read every comment**, proposal and impl, in full. Note `author`, `is_self_comment`,
   `path`/`section` where present.
2. **For each comment, decide per facet**: does it invoke a documented `principle`? Which part of
   the contribution (`artifact`) is it about? What kind of fix (`nature`) is it asking for? A
   comment can legitimately match nothing on any facet — pure acknowledgments ("done", "lgtm",
   "thanks", an emoji reaction) are real, expected zero-matches, not something to force a tag
   onto. Don't tag every comment just to raise a count.
3. **Write one row per match** (not per comment) to `processed/tep<N>/classify.jsonl`. Use this
   script shape (this exact pattern, `add(comment_id, repo, pr_number, tags)`, is what every TEP
   classified so far has used — keeping the script file around after the run makes bugs
   traceable later):

   ```python
   # processed/tep<N>/classify.py
   import json

   rows = []

   def add(comment_id, repo, pr_number, tags):
       """tags: list of (facet, value, confidence, evidence)"""
       for facet, value, confidence, evidence in tags:
           rows.append({
               "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
               "facet": facet, "value": value, "confidence": confidence,
               "evidence": evidence,
           })

   # one add() call per comment that matches anything, e.g.:
   add(123456789, "community", 148, [
       ("artifact", "tep-body", 0.8, "asks to expand Motivation/Goals"),
       ("nature", "content", 0.6, "substantive process guidance"),
   ])
   # ... one add() per classifiable comment ...

   out_path = "processed/tep<N>/classify.jsonl"  # <- set <N>
   with open(out_path, "w") as f:
       for r in rows:
           f.write(json.dumps(r) + "\n")
   comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
   print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
   ```

   Each row is `{"repo", "pr_number", "comment_id", "facet", "value", "confidence" (0-1 float),
   "evidence"}`. `evidence` is required and must point at real text in that specific comment —
   never a generic placeholder. A single comment commonly gets several rows (e.g.
   `artifact:tep-body` + `nature:content` + `principle:consistency-with-existing` on the same
   sentence are three separate, real claims, not duplication).
4. **Confidence is a genuine estimate**, not decoration — a comment that's mostly a nit gets a
   low `nature:structure` confidence; a comment making a forceful, specific design argument gets
   a high one. Confidences don't need to be calibrated across TEPs, only honest within one.

**At scale** (a large TEP can have 400+ comments across a dozen implementation PRs — too many
`add()` calls to reason through and write correctly in one pass): split into several scripts,
e.g. `processed/tep<N>/classify_part1.py`, `_part2.py`, ... (by PR, or by chunks of ~80-100
comments), each writing its own `.jsonl` under `processed/tep<N>/`, then `cat` them together into
`processed/tep<N>/classify.jsonl` before validating. This is the expected pattern for large TEPs,
not a workaround — trying to hold an entire large TEP's classification in one continuous pass is
exactly when the "row silently never gets written" bug (see Known gotchas) gets worse, not
better.

## Validate before committing

Two checks, every time, before this data goes anywhere near a commit. Run both from your
worktree root:

**1. Every `(facet, value)` pair exists in `conventions/seed-taxonomy.yaml`** (a typo'd or
invented value silently corrupts aggregate counts later), and **no `(comment, facet, value)`
row is accidentally duplicated**:

```bash
uv run python3 - <<'EOF'
import json
from ruamel.yaml import YAML
from collections import Counter

yaml = YAML(typ="safe")
tax = yaml.load(open("conventions/seed-taxonomy.yaml"))
valid = {facet: {v["value"] for v in fdef["values"]} for facet, fdef in tax["facets"].items()}

rows = [json.loads(l) for l in open("processed/tep<N>/classify.jsonl")]  # <- set <N>
bad = [(r["facet"], r["value"], r["comment_id"]) for r in rows
       if r["facet"] not in valid or r["value"] not in valid[r["facet"]]]
print("total rows:", len(rows), "| invalid facet/value pairs:", bad)

dupes = [k for k, v in Counter(
    (r["repo"], r["pr_number"], r["comment_id"], r["facet"], r["value"]) for r in rows
).items() if v > 1]
print("duplicate rows:", dupes)
EOF
```

Both `bad` and `dupes` must print empty (`[]`) before you continue.

**2. Cross-check tagged comments against the full comment list for that TEP.** Build the set of
`(repo, pr_number, comment_id)` you *didn't* tag and read through it — every one should be a
comment you can justify as a real zero-match. If you find one you actually meant to tag, that's a
bug: the classification pass silently dropped a row it should have written (see Known gotchas).
This single check has caught a real bug in most TEPs classified so far — don't skip it.

```bash
uv run python3 - <<'EOF'
import json
TEP_NUMBER = 76        # <- set this
IMPL_REPO = "pipeline"  # <- set this to the TEP's implementation repo

rows = [json.loads(l) for l in open("processed/tep76/classify.jsonl")]  # <- set path
tagged = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)

records = json.load(open('processed/latest/per_tep_records.json'))
rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)

untagged = []
for c in rec['proposal_pr']['comments']:
    key = ("community", c['pr_number'], c['comment_id'])
    if key not in tagged:
        untagged.append((key, c['author'], c['body'][:150].replace(chr(10), ' ')))
for pr in rec['impl_prs']['items']:
    for c in pr['comments']:
        key = (IMPL_REPO, pr['pr_number'], c['comment_id'])
        if key not in tagged:
            untagged.append((key, c['author'], c['body'][:150].replace(chr(10), ' ')))

print(f"{len(untagged)} untagged comments")
for k, a, b in untagged:
    print(k, a, "|", b)
EOF
```

Read every line of that output. Anything that isn't an obvious ack/reaction is a candidate bug —
go back and add the row you meant to write.

## Audit pass

Once first-pass classification validates clean, run a **separate** pass per
`prompts/audit_classification_coverage.md` — re-reading each already-classified comment fresh
against the full taxonomy to catch matches the first pass missed. Write findings the same way as
first pass — same `add(comment_id, repo, pr_number, tags)` shape, so the two scripts are
copy-pasteable from each other — but stamp `"source_pass": "audit"` on every row:

```python
# processed/tep<N>/audit.py
import json

rows = []

def add(comment_id, repo, pr_number, tags):
    """tags: list of (facet, value, confidence, evidence) - same shape as classify.py"""
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence, "source_pass": "audit",
        })

# one add() call per comment with a missed match found on re-read, e.g.:
add(123456789, "community", 148, [
    ("principle", "feature-justification", 0.45, "explicitly frames Motivation/Goals as ..."),
])

out_path = "processed/tep<N>/audit.jsonl"  # <- set <N>
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"wrote {len(rows)} audit rows")
```

**Write `processed/tep<N>/audit.jsonl` even when the audit finds nothing** — an empty file (zero
lines) is a required, expected output, not an absence. The integration step treats a *missing*
`audit.jsonl` as an error, not as "no findings," precisely so a genuine zero-finding audit can't
be mistaken for an audit that was never run.

Validate `processed/tep<N>/audit.jsonl` with the same taxonomy-membership check as first pass
before it's part of your commit.

Also worth a deliberate re-read for: principle/artifact/nature values that have zero or very few
real examples anywhere in the corpus so far —

```bash
grep -c '"value": "VALUE_NAME_HERE"' processed/latest/comment_classifications.jsonl
```

— a TEP whose topic plausibly touches one of those low-count values is the best chance to find
its first real example, and it's easy to under-tag a value you haven't seen fire yet. A
zero-finding audit pass is a legitimate, honest outcome — don't invent findings to pad the count.

**Scoping the audit at scale**: `audit_classification_coverage.md` describes re-reading every
already-classified comment fresh, which is the ideal — exhaustively re-deriving a classification
from zero is what actually catches blind spots a first pass had. For a small TEP (a few dozen
comments), just do that. For a large one (a few hundred+), exhaustive re-read of every comment
is expensive enough that a **targeted audit** is an acceptable substitute: the low-count-value
`grep -c` sweep above, plus rereading specifically the comments your first pass flagged to
itself as ambiguous, borderline-confidence, or "possibly more here" while classifying. This
trades completeness for cost — say explicitly in your report which approach you used, so the
gap is visible rather than silently assumed away.

## Generate the review report

Once both `classify.jsonl` and `audit.jsonl` validate clean, build a scoped review report — the
same explorer used throughout this pipeline, fed only this TEP's data so a human reviewer sees
full comment text and classification badges without wading through everything else.
`build_explorer.py --classifications` takes exactly one path, so combine first-pass and audit
rows into one file before building — otherwise audit rows (and their `[found on audit pass]`
badge) silently never show up in the report:

```bash
cat processed/tep<N>/classify.jsonl processed/tep<N>/audit.jsonl \
    > processed/tep<N>/all_rows.jsonl  # combined input for the explorer only
uv run python3 - <<'EOF'
import json
from pathlib import Path
TEP_NUMBER = 76  # <- set this
records = json.loads(Path('processed/latest/per_tep_records.json').read_text())
rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
Path(f'processed/tep{TEP_NUMBER}/records_slice.json').write_text(json.dumps([rec]))
EOF
uv run scripts/build_explorer.py \
    --records processed/tep<N>/records_slice.json \
    --classifications processed/tep<N>/all_rows.jsonl \
    --out processed/tep<N>/explorer.html
rm processed/tep<N>/records_slice.json processed/tep<N>/all_rows.jsonl  # throwaway - don't commit
```

`build_explorer.py` doesn't filter by TEP number internally — it just embeds whatever records
it's given — so no script changes were needed to support this. Both `records_slice.json` and
`all_rows.jsonl` are only there to satisfy the script's expected inputs; they're redundant with
files that already exist (`per_tep_records.json`, and `classify.jsonl`/`audit.jsonl` separately)
and get deleted immediately after the build, so neither ends up staged.

## Update the cost log fragment

Write `processed/tep<N>/cost.md` — one Markdown table row, in the same column order as the
existing table in `conventions/classification_cost_log.md` (the integration step appends this
row verbatim, so it must match: TEP, repo, comments total, comments classified, first-pass rows,
audit rows, comment-body chars, passes, session $):

```bash
uv run python3 - <<'EOF'
import json
TEP_NUMBER = 76    # <- set this
REPO = "pipeline"  # <- set this to the TEP's implementation repo

records = json.load(open('processed/latest/per_tep_records.json'))
rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
chars, total = 0, 0
for c in rec['proposal_pr']['comments']:
    chars += len(c['body']); total += 1
for pr in rec['impl_prs']['items']:
    for c in pr['comments']:
        chars += len(c['body']); total += 1

classify_rows = [json.loads(l) for l in open(f'processed/tep{TEP_NUMBER}/classify.jsonl')]
audit_rows = [json.loads(l) for l in open(f'processed/tep{TEP_NUMBER}/audit.jsonl')]
classified = len(set((r['repo'], r['pr_number'], r['comment_id'])
                      for r in classify_rows + audit_rows))

row = (f"| TEP-{TEP_NUMBER} | {REPO} | {total} | {classified} | {len(classify_rows)} | "
       f"{len(audit_rows)} | {chars:,} | first-pass + audit | - |\n")
with open(f'processed/tep{TEP_NUMBER}/cost.md', 'w') as f:
    f.write(row)
print(row)
EOF
```

If you used the targeted-audit shortcut rather than an exhaustive re-read (see "Scoping the
audit at scale"), change `"first-pass + audit"` in the row above to `"first-pass + targeted
audit"`, matching how earlier TEPs recorded the same distinction.

## Commit and push

Stage your whole output directory and nothing else:

```bash
git add -f processed/tep<N>/
git status --short   # confirm ONLY processed/tep<N>/ files are staged - nothing else
git commit -m "Classify + audit TEP-<N> (<short title>)"
git push origin classify/tep<N>
```

`-f` is required: `processed/tep*/` is gitignored on `main` so that directory is never
accidentally staged from the main checkout, and the same rule applies inside your worktree.

Don't run `make explorer`, and don't touch `conventions/classification_cost_log.md` or
`reports/explorer.html` — those are shared files, and this branch never writes to them. Also
write `processed/tep<N>/notes.md` at this point if you found anything a human should look at but
weren't in a position to fix yourself (see Known gotchas) — free text is fine; there's no
required format, and it's fine to skip the file entirely if you have nothing to flag.

## Human review checkpoint

A human reviews the pushed branch's diff before it's integrated. What to check:

- Every staged file is under `processed/tep<N>/` — nothing else (no shared file touched, nothing
  left at the worktree root).
- `classify.jsonl` is non-empty.
- `audit.jsonl` is present — even an empty file is correct; its *absence* is the red flag, not
  its emptiness.
- `cost.md` contains one data row, matching the existing `classification_cost_log.md` table's
  columns.
- `explorer.html` opens in a browser and renders: comment text, classification badges, and — if
  the audit found anything — the `[found on audit pass]` badge styling.
- If `notes.md` is present: read it. It's the agent's flag of something it noticed but wasn't
  scoped to decide on its own (typically a suspected PR misattribution). Decide whether
  `overrides/pr_attribution_overrides.jsonl` needs a new entry on `main`, and add it **before**
  this branch is integrated — see `prompts/integrate_classifications.md` — so the merged data is
  already correct by the time it lands.

**Future extension** (not in scope yet): a CI job on `classify/*` branches that runs the
taxonomy-membership and no-duplicates checks automatically, so the reviewer gets a green/red
signal before opening the diff by hand.

## Next step

Once a branch is approved, integrating it — merging into `main`, appending to the shared files,
rebuilding the explorer — is a separate process: `prompts/integrate_classifications.md`. This
prompt's job ends at push; don't run integration steps yourself from inside a `classify/tep<N>`
worktree.

## Known gotchas (each has actually happened in this pipeline)

- **A row you meant to write silently doesn't exist.** Writing many `add(...)` calls by hand,
  it's easy to fully reason through a comment's classification and then never actually call
  `add()` for it. The untagged-comment cross-check above is what catches this — it has caught a
  real instance in most TEPs run so far.
- **PR misattribution — flag it, don't fix it yourself.** A TEP's number can get reassigned over
  time; a PR whose title cites the *old* number for a since-renumbered TEP can auto-confirm as an
  implementation PR via a title-match heuristic even though it has nothing to do with the TEP
  that number refers to now. `overrides/pr_attribution_overrides.jsonl` is a shared file on
  `main` and you're not scoped to edit it from an isolated per-TEP branch. If an implementation
  PR's actual content doesn't match the TEP's subject at all, write what you found to
  `processed/tep<N>/notes.md` (which PR, why it looks wrong) and leave the decision — and the
  override entry — to the human reviewer.
- **A PR can legitimately belong to two sibling TEPs at once** — this is different from
  misattribution and needs no override, no note. Closely related TEPs sometimes land as one
  shared PR (e.g. a PR whose description says "part of work in TEP-00XX" while
  `per_tep_records.json` attributes it to a *different*, sibling TEP number). Before assuming
  this is the misattribution case above, read the actual comment thread: if reviewers are
  discussing both TEPs' concerns in the same PR (e.g. explicitly splitting mixed logic that
  serves both proposals), it's a genuine shared PR — classify its comments normally, and just
  note the fact in your commit message.
- **Length is not a coverage metric.** Do not use comment length vs. tag count as a completeness
  signal for anything — facets are independent axes, so tag count conflates "how many distinct
  facets does this one point touch" with "how many separate points does this comment make." See
  `prompts/audit_classification_coverage.md`'s "Why this exists" for the full reasoning.
- **Nothing gets written outside `processed/tep<N>/`.** If you catch yourself about to create a
  scratch file anywhere else in the worktree — the root, a temp dir, wherever — stop. Files
  scattered outside a predictable location is exactly the friction `parallel-classify-plan.md`
  exists to remove.

## Known limits

- This is a per-TEP, agent-driven pass, run iteratively (pilot a handful, review, expand) per
  Sub-Task 8's plan — not a batch-API pipeline. Don't build automation to loop this unattended
  over the full corpus; each run benefits from the taxonomy-gap awareness a person or agent
  builds up mid-run (e.g. noticing a value has zero real examples yet), which a blind batch loop
  would not have.
- This prompt classifies comments that exist. It doesn't second-guess whether a TEP's comment
  data itself is complete or correctly attributed — that's `data-collection-plan.md`'s Sub-Task
  6/6b/7's job, upstream of this one (note: those are `data-collection-plan.md`'s own sub-task
  numbers for the overall corpus-mining pipeline, unrelated to `parallel-classify-plan.md`'s
  Sub-Tasks 1-6 for the parallel-execution process itself).
- The two validation checks above are run and self-reported by the classifying agent; nothing
  currently re-verifies them automatically before a human approves the branch (see the CI note
  under Human review checkpoint).
