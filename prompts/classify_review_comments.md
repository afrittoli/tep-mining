# Classify review comments

## Why this exists

`conventions/seed-taxonomy.yaml` is a vocabulary, not a result — Sub-Task 8 only produces
something useful once real review comments are matched against it. This is that matching step:
one TEP's proposal-PR and implementation-PR comments in, rows appended to
`processed/YYYY-MM-DD/comment_classifications.jsonl` out. It's an AI-agent stage (not a script)
because it's a reading-comprehension job — matching a comment's actual point against fifteen-plus
taxonomy values across three facets isn't reducible to keyword rules.

This prompt had no written form for the first several TEPs classified in this pipeline — the
procedure below, **including the exact shell/Python commands**, was worked out live, several
bugs deep, across those runs. The commands are plain `python3`/`bash`/`git` — nothing here
assumes any particular AI coding tool. Writing it down is what makes the next TEP delegable to a
fresh agent (any agent) or session instead of requiring someone who was present for that history.

Environment note: this project manages Python dependencies with `uv` (see `pyproject.toml`).
Every Python snippet below should run as `uv run python3 ...`. If your shell has a stray
`VIRTUAL_ENV` pointing at an unrelated project, `uv` will warn about it — that warning is
harmless; the commands still use this project's own `.venv`. Add `--active` after `uv run` only
if you specifically want to force the currently-active venv instead.

## Inputs

- `conventions/seed-taxonomy.yaml` — the full file, every facet, not just values you expect to
  match. Re-read `semantics:` at the top before starting: facets are independent (a comment can
  match zero, one, or several values per facet), zero matches across all three facets is the
  normal outcome for most comments, and `parent` is advisory only.
- One TEP's comment data from `processed/latest/per_tep_records.json`. Pull it like this
  (replace `TEP_NUMBER`):

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
3. **Write one row per match** (not per comment) to a scratch JSONL file. Use this script shape
   (this exact pattern, `add(comment_id, repo, pr_number, tags)`, is what every TEP classified so
   far has used — keeping the script file around after the run makes bugs traceable later):

   ```python
   # classify_tepN.py
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

   out_path = "classify_tepN.jsonl"
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

## Validate before merging

Two checks, every time, before this data touches the real classification file. Run both from
the repo root, in the same directory as your `classify_tepN.jsonl`:

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

rows = [json.loads(l) for l in open("classify_tepN.jsonl")]
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

rows = [json.loads(l) for l in open("classify_tepN.jsonl")]
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
first pass, but add `"source_pass": "audit"` to each row:

```python
# audit_tepN.py
import json

rows = []

def add(comment_id, repo, pr_number, facet, value, confidence, evidence):
    rows.append({
        "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
        "facet": facet, "value": value, "confidence": confidence,
        "evidence": evidence, "source_pass": "audit",
    })

# one add() call per missed match found on re-read

out_path = "audit_tepN.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"wrote {len(rows)} audit rows")
```

Validate `audit_tepN.jsonl` with the same taxonomy-membership check as first pass before merging
it in.

Also worth a deliberate re-read for: principle/artifact/nature values that have zero or very few
real examples anywhere in the corpus so far —

```bash
grep -c '"value": "VALUE_NAME_HERE"' processed/latest/comment_classifications.jsonl
```

— a TEP whose topic plausibly touches one of those low-count values is the best chance to find
its first real example, and it's easy to under-tag a value you haven't seen fire yet. A
zero-finding audit pass is a legitimate, honest outcome — don't invent findings to pad the count.

## Merging, building, verifying

1. **Append to the real dated file, never the symlink**: `processed/latest` is a symlink (e.g.
   to `processed/2026-08-07/`); `git add processed/latest/comment_classifications.jsonl` stages
   the symlink pointer, not the file it points to, and silently produces an empty diff.

   ```bash
   REAL_DIR=$(readlink processed/latest)
   TARGET="processed/${REAL_DIR}/comment_classifications.jsonl"
   wc -l "$TARGET"                                    # count before
   cat classify_tepN.jsonl audit_tepN.jsonl >> "$TARGET"
   wc -l "$TARGET"                                    # count after - delta must equal
                                                        # (first-pass rows + audit rows)
   ```

2. **Rebuild the explorer**:

   ```bash
   make explorer
   ```

   Confirm the reported "N comment classifications loaded" count matches the new total from
   step 1.

3. **Verify rendering**, not just the row count — badges are easy to get right in the data and
   wrong in the browser (a missing argument, a stale cache key). `reports/explorer.html` embeds
   the classification data as JSON and exposes `CLASSIFICATION_INDEX` (a `Map` keyed by
   `` `${repo}|${pr_number}|${comment_id}` ``) and `classificationBadgesHtml(repo, pr_number,
   comment_id)` as globals in its inline `<script>`. Any JS-capable environment can spot-check a
   few comment IDs this way — a headless browser (e.g. `puppeteer-core` against a local Chrome
   install) is one option if available, but isn't required; reading the embedded JSON block
   directly and confirming a few rows are present and well-formed is an acceptable substitute if
   no browser automation is available in your environment. Check at least one audit-pass row
   renders with `source_pass: "audit"` intact.

4. **Update `conventions/classification_cost_log.md`** with a row for this TEP: comment counts,
   first-pass/audit row counts, and total comment-body character count as a proxy for the token
   cost this TEP added:

   ```bash
   uv run python3 - <<'EOF'
   import json
   TEP_NUMBER = 76  # <- set this
   records = json.load(open('processed/latest/per_tep_records.json'))
   rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
   chars, n = 0, 0
   for c in rec['proposal_pr']['comments']:
       chars += len(c['body']); n += 1
   for pr in rec['impl_prs']['items']:
       for c in pr['comments']:
           chars += len(c['body']); n += 1
   print("comments:", n, "total body chars:", chars)
   EOF
   ```

5. **Commit** the real dated classifications file, `reports/explorer.html`, and the cost log
   together. Don't commit `.coverage` or any local workspace/editor files alongside it.

   ```bash
   git add "processed/${REAL_DIR}/comment_classifications.jsonl" reports/explorer.html \
       conventions/classification_cost_log.md
   git status --short   # confirm nothing unexpected is staged
   git commit -m "Pilot classify + audit TEP-<N> (<short title>)"
   ```

## Known gotchas (each has actually happened in this pipeline)

- **A row you meant to write silently doesn't exist.** Writing many `add(...)` calls by hand,
  it's easy to fully reason through a comment's classification and then never actually call
  `add()` for it. The untagged-comment cross-check above is what catches this — it has caught a
  real instance in most TEPs run so far.
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
- **`processed/latest` is a symlink.** Reading through it works fine (`per_tep_records.json`,
  `comment_classifications.jsonl` for the untagged-check/grep steps above); *writing* through it
  for `git add` purposes does not — see the Merging section.

## Known limits

- This is a per-TEP, agent-driven pass, run iteratively (pilot a handful, review, expand) per
  Sub-Task 8's plan — not a batch-API pipeline. Don't build automation to loop this unattended
  over the full corpus; each run benefits from the taxonomy-gap awareness a person or agent
  builds up mid-run (e.g. noticing a value has zero real examples yet), which a blind batch loop
  would not have.
- This prompt classifies comments that exist. It doesn't second-guess whether a TEP's comment
  data itself is complete or correctly attributed — that's Sub-Task 6/6b/7's job, upstream of
  this one.
