# Parallel TEP Classification — Process Improvement Plan

## Overview

The `classify_review_comments` task is currently run one TEP at a time by a single agent.
Running it in parallel across multiple agents (e.g. Claude on one TEP, Bob on another)
revealed five classes of friction:

1. **No worktree setup** — agents worked directly on shared branches and ran into conflicts.
2. **Files written to the wrong location** — scratch files ended up in the project root because
   the prompt doesn't mandate a working directory or file naming convention.
3. **Shared mutable files cause merge conflicts** — `comment_classifications.jsonl`,
   `classification_cost_log.md`, and `reports/explorer.html` are all written to by every agent
   and must be merged manually; the cost log had a recorded `<<<<<<< HEAD` conflict (now
   resolved externally).
4. **No permission pre-approvals** — agents receive interactive permission prompts for every
   file read, script execution, and git operation, breaking the "non-interactive except at
   human review" requirement.
5. **No integration process** — there is no defined step for merging per-TEP branches back
   together and rebuilding the shared derived files.

### Design principle

**Per-TEP agents are strictly isolated.** Each agent works in its own git worktree, writes
only to `processed/tep<N>/` within that worktree, and ends its session by pushing its branch.
It never touches `comment_classifications.jsonl`, `classification_cost_log.md`,
or `reports/explorer.html`.

**A separate integration process** (a new prompt) handles everything that requires a global
view: merging branches, appending to shared files, rebuilding the explorer, and updating the
cost log. It runs once after one or more per-TEP branches are approved by a human.

---

## Sub-Tasks

### Sub-Task 1 — Create per-agent permission config files and a `make permissions` management target

**Status**: `[x] done`

**Who runs this**: A human, once, before any parallel classification work begins. These are
one-time repo setup steps, not something any agent does. The `make permissions` target is used
to switch between modes whenever needed thereafter.

**Intent**: Both Claude Code and Bob Shell ask for interactive permission every time an agent
runs a shell command, reads a file, creates a file, or executes a script. They use completely
different permission systems and config file formats — a single shared file cannot cover both.
Pre-approving the specific operations the classification workflow needs in each tool's own
format eliminates all mid-run prompts, so the only human checkpoint is reviewing the finished
branch.

The permission state also needs to be reversible: after parallel classification is done, it
should be easy to restore maximum-safety defaults. A `make permissions` target manages both
config files together, ensuring they stay in sync and neither tool is accidentally left open.

**Expected Outcomes**:
- `.claude/settings.json` and `.bob/settings.json` exist in the repo. A new worktree checks
  out whatever is **committed** at its branch point — not uncommitted changes sitting in the
  main checkout — so `make permissions MODE=parallel` must be run *and committed* on `main`
  before `make worktree-classify` is run, or the new worktree inherits the locked-down
  baseline instead. `worktree-classify` refuses to create a worktree unless this is already
  true (see Sub-Task 2).
- `make permissions MODE=parallel` writes both files with the full set of pre-approved
  operations needed for classification, so agents run without any permission prompts.
- `make permissions MODE=safe` writes both files in locked-down state: no pre-approved
  operations; every tool call requires explicit human approval.
- `make permissions` with no `MODE` prints the current state of both files without modifying
  anything.
- The target is idempotent: running it twice with the same `MODE` produces the same files.

**Two modes**:

*`parallel` mode* — pre-approves exactly the operations the classification workflow uses:

| Operation | Claude Code | Bob Shell |
|---|---|---|
| Run Python scripts | `Bash(uv run python3 *)` | `run_shell_command(uv)` |
| Run shell snippets | `Bash(bash *)` | `run_shell_command(bash)` |
| Git operations | `Bash(git *)` | `run_shell_command(git)` |
| Make targets | `Bash(make *)` | `run_shell_command(make)` |
| Row-count checks | `Bash(wc -l *)` | `run_shell_command(wc)` |
| Concatenate files | `Bash(cat *)` | `run_shell_command(cat)` |
| Create directories | `Bash(mkdir -p *)` | `run_shell_command(mkdir)` |
| Read any file | `Read(*)` | *(reads don't require shell; no entry needed)* |
| Write per-TEP files | `Write(processed/tep*/**)` | `write_to_file(processed/tep*)` |

*`safe` mode* — removes all pre-approvals; both files contain empty allowed lists. Every
tool call requires explicit human confirmation. Use after classification is complete or when
working on sensitive parts of the repo.

**Note on Bob Shell pattern matching**: Bob Shell's `tools.allowed` entries match by prefix
against the full command string — `run_shell_command(git)` matches `git status`, `git add`,
`git commit`, etc. There is no documented `*` wildcard syntax; prefix matching on the command
name covers all subcommands. The `write_to_file` entry uses a path prefix to scope file
creation to the per-TEP output directory only.

**Todo List**:
1. Write `scripts/manage_permissions.py`:
   - Accept `--mode {parallel,safe,status}` argument.
   - For `parallel`: write `.claude/settings.json` and `.bob/settings.json` with the full
     allowed lists from the table above.
   - For `safe`: write both files with empty `allow`/`allowed` arrays.
   - For `status`: read both files (if they exist) and print a human-readable summary of what
     is currently allowed in each, without modifying anything.
   - In all write modes: if a file already exists and already matches the target state exactly,
     print "already up to date" and skip the write (idempotent).
   - Print a clear one-line confirmation for each file written or skipped.
2. Add a `permissions` target to `Makefile`:

   ```makefile
   permissions: ## Manage agent permissions. MODE=parallel (classify) | MODE=safe (locked down) | no MODE (status)
       uv run scripts/manage_permissions.py --mode $(if $(MODE),$(MODE),status)
   ```

3. Commit the initial state of both settings files (written by `make permissions MODE=safe`
   as the safe baseline) to `main`.

**Relevant Context**:
- `.claude/` already exists in the repo (contains `worktrees/`). `.bob/` does not yet exist;
  the script creates it.
- Claude Code settings schema: `{ "permissions": { "allow": ["Bash(pattern)", "Write(pattern)", ...] } }`.
- Bob Shell settings schema: `{ "tools": { "allowed": ["run_shell_command(prefix)", "write_to_file(path)", ...] } }`.
  Bob Shell reads `.bob/settings.json` as the project-level config (priority 4 of 7: below
  CLI args and env vars, above user settings and system defaults).
- The two files are always written together by `manage_permissions.py` so they cannot drift
  out of sync with each other.
- Both files should be committed after each `make permissions` invocation that changes them,
  so the permission state is part of the repo history and visible in diffs.

---

### Sub-Task 2 — Add `make worktree-classify` and `make worktree-remove` targets

**Status**: `[x] done`

**Who runs this**: The per-TEP agent runs `make worktree-classify TEP=<N>` as its very first
step, before doing any classification work. The human just tells the agent which TEP to
classify — worktree setup is the agent's responsibility. `make worktree-remove TEP=<N>` is
run by the integration process after a branch is merged.

**Intent**: Without a dedicated worktree, agents default to working on whatever branch is
currently checked out and conflict with each other immediately. A Make target gives agents a
single, unambiguous command to create their isolated environment without needing to know or
remember the git worktree syntax. The target also guards against mistakes (missing `TEP`,
duplicate worktree) so the agent cannot accidentally start work in the wrong place.

**Expected Outcomes**:
- `make worktree-classify TEP=<N>` creates a git worktree at `../tep-mining-tep<N>` (a
  sibling directory alongside the main checkout, outside the repo) on a new branch
  `classify/tep<N>`, and prints `cd ../tep-mining-tep<N>` to stdout.
- Re-running `make worktree-classify TEP=<N>` when the worktree already exists prints the
  path without error (idempotent).
- `make worktree-remove TEP=<N>` removes the worktree and deletes the local branch.
- No `.gitignore` changes are needed — the worktree lives outside the repo entirely.

**Why sibling directory, not `.claude/worktrees/`**: Claude Code's own subagent isolation
mechanism creates worktrees under `.claude/worktrees/agent-<id>` and has been observed to
silently reap those directories between agent pauses and resumes. A sibling path outside the
repo is unambiguously outside that cleanup scope. The TEP-142 parallel run used exactly this
pattern (`tep-mining-classify-tep142` alongside the main checkout) and survived without issue.

**Todo List**:
1. Add `worktree-classify` target to `Makefile`:
   - Exit with an error if `TEP` is not set.
   - Create the worktree with `git worktree add ../tep-mining-tep$(TEP) -b classify/tep$(TEP)`,
     or skip creation and print the path if the worktree already exists.
   - Print `cd ../tep-mining-tep$(TEP)` as the final line of output.
2. Add `worktree-remove` target to `Makefile`:
   - Exit with an error if `TEP` is not set.
   - Run `git worktree remove ../tep-mining-tep$(TEP) --force`.
   - Run `git branch -d classify/tep$(TEP)`.

**Relevant Context**:
- Git worktrees share the object store but each has its **own independent working directory**.
  A worktree created with `git worktree add` checks out the files as committed at its branch
  point — it does not see uncommitted changes in the main checkout. `.bob/settings.json` and
  `.claude/settings.json` only take effect in a new worktree if `make permissions MODE=parallel`
  was already run *and committed* on `main` first. `worktree-classify` enforces this: it reads
  `.claude/settings.json` at `HEAD` (not the working tree) and refuses to create a worktree if
  the allow list there is empty, printing the exact remediation command. This guard exists
  because the first real run of this plan skipped the commit step, so every classify worktree
  silently inherited the locked-down baseline and every tool call prompted for approval —
  the mechanism was built but never switched on.
- The `classify/tep<N>` branch naming convention is already in use (the past conflict was on
  `classify/tep142`).

---

### Sub-Task 3 — Define `processed/tep<N>/` as the per-TEP agent output directory

**Status**: `[x] done`

**Who runs this**: Implemented as changes to `prompts/classify_review_comments.md` and
`prompts/audit_classification_coverage.md`. Each agent then follows the updated prompts.

**Intent**: The current prompt does not specify where to write output files, so agents write
them wherever their CWD happens to be — which has been the project root. Giving each TEP a
fixed, predictable output directory inside the worktree fixes the scatter problem and gives
the integration process a stable path to read from.

**Design decisions**:

*Does this affect existing classified TEPs?* No. TEPs 29, 33, 84, 109, 9, 26, 76, 75, and
142 are already merged into `processed/2026-08-07/comment_classifications.jsonl`, the
global explorer, and `conventions/classification_cost_log.md`. The new `processed/tep<N>/`
layout only applies to future classification runs — nothing is backfilled, since the cost
log is updated by simple append (Sub-Task 5, step 4), not reassembled from a complete set of
per-TEP fragments.

*Should the integration step be mandatory or only for parallel runs?* **Mandatory always.**
Having two documented paths (solo: append-and-commit directly; parallel: write fragments and
integrate separately) means agents need conditional logic and the prompt needs branching. A
single path — per-TEP agents always write fragments, integration always runs separately — is
simpler, more consistent, and prevents the global files from ever being touched by a
classifying agent regardless of how many agents are running. For solo use, the human simply
runs the integration step immediately after one branch, rather than batching many.

*What does the human review against?* The human reviews a **per-TEP explorer report**
(`processed/tep<N>/explorer.html`), generated by the agent at the end of its session by
passing its `classify.jsonl`+`audit.jsonl` as the classification source to the existing
`build_explorer.py` script (which already accepts `--records`, `--classifications`, and
`--out` as arguments). This scoped report shows the exact TEP with full comment text and
classification badges — the same quality of review as the global explorer, but limited to
the one TEP being reviewed. The global explorer is rebuilt only at integration time.

**Expected Outcomes**:
- Every file a per-TEP agent produces lives under `processed/tep<N>/` in its worktree:
  - `processed/tep<N>/classify.jsonl` — first-pass classification rows
  - `processed/tep<N>/audit.jsonl` — audit-pass rows (empty file if no findings, never absent)
  - `processed/tep<N>/cost.md` — one Markdown table row for the cost log
  - `processed/tep<N>/notes.md` — free-text notes on suspected misattributions or other
    issues for the human reviewer; omitted if nothing to flag
  - `processed/tep<N>/explorer.html` — scoped single-TEP report for human review
  - `processed/tep<N>/classify_part*.py` — script files kept for traceability
  - `processed/tep<N>/audit_part*.py` — audit script files kept for traceability
- No file is ever written to the worktree root or any other directory.
- The integration step is mandatory for all classification runs — solo or parallel. There is
  no "append directly" shortcut path in the prompt.
- `processed/tep*/` is added to `.gitignore` on `main` so those dirs are never accidentally
  staged from the main checkout. The files are committed only on `classify/*` branches,
  where the integration process reads them after merge.

**Todo List**:
1. Update `prompts/classify_review_comments.md`:
   - Replace all `classify_tepN.*` references with `processed/tep<N>/classify.*`.
   - Replace all `audit_tepN.*` references with `processed/tep<N>/audit.*`.
   - Update the Python script template's `out_path` variable accordingly.
   - Add `mkdir -p processed/tep<N>` as the first shell step after the worktree `cd`.
   - State explicitly that `processed/tep<N>/audit.jsonl` must be created even when the audit
     finds nothing (write an empty file; its absence is an error in the integration step).
   - Add a step to generate the per-TEP explorer report after validation passes:

     ```bash
     uv run python3 - <<'EOF'
     import json; from pathlib import Path
     TEP_NUMBER = <N>  # <- set this
     records = json.loads(Path('processed/latest/per_tep_records.json').read_text())
     rec = next(r for r in records if r['tep_number'] == TEP_NUMBER)
     Path(f'processed/tep{TEP_NUMBER}/records_slice.json').write_text(json.dumps([rec]))
     EOF
     uv run scripts/build_explorer.py \
         --records processed/tep<N>/records_slice.json \
         --classifications processed/tep<N>/classify.jsonl \
         --out processed/tep<N>/explorer.html
     ```

   - Instruct the agent to write `processed/tep<N>/notes.md` with any suspected
     misattributions or data issues found during classification. The agent flags, never
     decides — the override decision belongs to the human reviewer.
   - Remove the "Merging, building, verifying" section entirely — that responsibility moves
     to the integration prompt (Sub-Task 5).
2. Update `prompts/audit_classification_coverage.md`:
   - Replace the audit output path with `processed/tep<N>/audit.jsonl`.
3. Add `processed/tep*/` to `.gitignore` with a comment:
   `# per-TEP scratch dirs; committed only on classify/* branches, not on main`.

**Relevant Context**:
- `build_explorer.py` already accepts `--records`, `--classifications`, and `--out` as CLI
  arguments and does not filter by TEP number internally. No script changes are needed to
  support per-TEP reports.
- The `.gitignore` rule causes `git add processed/tep<N>/` to silently skip those files on
  `main`. On the `classify/tep<N>` branch the same rule applies, so the per-TEP commit must
  use `git add -f processed/tep<N>/` (force-add) to override it. This must be stated
  explicitly in the prompt's commit step (Sub-Task 4).

---

### Sub-Task 4 — Rewrite the per-TEP agent's commit and handoff section

**Status**: `[x] done`

**Who runs this**: Implemented as changes to `prompts/classify_review_comments.md`.
Each agent then follows the updated prompt.

**Intent**: The current prompt's final steps mix per-TEP work (classify, validate) with
shared-file mutations (appending to `comment_classifications.jsonl`, running `make explorer`,
updating `classification_cost_log.md`). In a parallel setting those shared-file steps cause
conflicts and must be removed from the per-TEP prompt entirely. The agent's job ends with a
clean scoped commit and a push; a human then reviews the branch before handing it to the
integration process.

**Expected Outcomes**:
- The per-TEP agent's final commit contains exactly the files under `processed/tep<N>/` and
  nothing else. No shared file is staged or modified.
- The agent runs `git push origin classify/tep<N>` as its very last action.
- The prompt ends with a "Human review checkpoint" section that tells the reviewer exactly
  what to check in the diff before approving the branch for integration.
- There is no `make explorer` step and no shared-file edit anywhere in
  `prompts/classify_review_comments.md`.

**Todo List**:
1. Replace the existing "Merging, building, verifying" and commit sections in
   `prompts/classify_review_comments.md` with a new "Commit and push" section:

   ```bash
   git add -f processed/tep<N>/
   git status --short   # confirm only processed/tep<N>/ files are staged
   git commit -m "Classify + audit TEP-<N> (<short title>)"
   git push origin classify/tep<N>
   ```

2. Add a "Human review checkpoint" section at the end of the prompt. The reviewer checks:
   - All staged files are under `processed/tep<N>/` — nothing else.
   - `classify.jsonl` is non-empty.
   - Validation outputs (taxonomy membership, no duplicates, untagged check) were clean.
   - `cost.md` row is present.
   - `explorer.html` renders correctly (open in browser; verify classification badges appear).
   - `notes.md` — read it if present; decide whether any flagged misattribution needs an
     entry in `overrides/pr_attribution_overrides.jsonl` on `main` before integration runs.
3. Add a "Next step" line pointing to `prompts/integrate_classifications.md`.
4. **Future extension** (not in scope now): a CI job on `classify/*` branches that runs the
   taxonomy-membership and no-duplicates validation checks automatically, giving the reviewer
   a green/red signal before they open the diff.

**Relevant Context**:
- `reports/explorer.html` and `conventions/classification_cost_log.md` are never touched by a
  per-TEP agent. Both are updated by the integration process.
- The `notes.md` check is explicit in the reviewer checklist so a reviewer cannot accidentally
  approve a branch without noticing a flagged misattribution.

---

### Sub-Task 5 — Write `prompts/integrate_classifications.md`

**Status**: `[x] done`

**Who runs this**: A human (or a dedicated agent session) after one or more `classify/tep<N>`
branches have been reviewed and approved. This is the only process that writes to
`comment_classifications.jsonl`, `classification_cost_log.md`, and `reports/explorer.html`.

**Intent**: There is currently no defined integration step. The work that belongs here
(merging branches, appending to shared files, rebuilding the explorer, updating the cost log)
was previously done ad-hoc inside each per-TEP session, which is the root cause of conflicts.
Moving all shared-file writes to a single, well-defined process makes conflicts structurally
impossible.

**Expected Outcomes**:
- `prompts/integrate_classifications.md` exists and is the single authoritative description
  of the post-classification merge process.
- The integration process can absorb any number of `classify/tep<N>` branches in one run;
  batching is explicitly supported.
- After a successful run, `main` contains the updated `comment_classifications.jsonl`, a
  rebuilt `reports/explorer.html`, and an updated `conventions/classification_cost_log.md`.
  No merge conflicts are possible because only this process writes those files.
- Each `classify/tep<N>` branch and its worktree are cleaned up after merge.

**Integration procedure (content of the new prompt)**:
1. For each `classify/tep<N>` branch to integrate:
   `git merge --no-ff classify/tep<N>` from `main`.
2. Resolve the symlink and append per-TEP data to the real dated file:

   ```bash
   REAL_DIR=$(readlink processed/latest)
   TARGET="processed/${REAL_DIR}/comment_classifications.jsonl"
   wc -l "$TARGET"   # count before
   cat processed/tep<N>/classify.jsonl processed/tep<N>/audit.jsonl >> "$TARGET"
   wc -l "$TARGET"   # count after — delta must equal classify rows + audit rows
   ```

3. Validate the combined file (taxonomy membership + no duplicates) — same inline scripts
   as in `prompts/classify_review_comments.md`, run now on the full file as a
   defence-in-depth check.
4. Append the cost log fragment:

   ```bash
   cat processed/tep<N>/cost.md >> conventions/classification_cost_log.md
   ```

5. Run `make explorer` to rebuild `reports/explorer.html` with all new data.
6. Verify the explorer ("N comment classifications loaded" matches new total).
7. Commit the three shared files together:

   ```bash
   git add "processed/${REAL_DIR}/comment_classifications.jsonl" \
       reports/explorer.html conventions/classification_cost_log.md
   git commit -m "Integrate classifications: TEP-<list>"
   ```

8. Clean up: `make worktree-remove TEP=<N>` for each merged branch.

**Todo List**:
1. Write `prompts/integrate_classifications.md` containing the procedure above, with exact
   shell snippets.
2. Note that the process can be run interactively by a human or by a dedicated agent session
   with `.claude/settings.json` / `.bob/settings.json` pre-approvals in place.
3. Note that any `notes.md` files flagged by per-TEP agents should be reviewed and acted on
   (i.e. `overrides/pr_attribution_overrides.jsonl` updated if needed) **before** step 1,
   not after — so that the merged data is already correct when the classifications are
   appended.

**Relevant Context**:
- The shell snippets for steps 2 and 7 are lifted from the current "Merging, building,
  verifying" section of `prompts/classify_review_comments.md` (with paths updated for the
  `processed/tep<N>/` layout). That section is removed from the per-TEP prompt in Sub-Task 4.
- `classification_cost_log.md` is updated by append (step 4), not regenerated from scratch —
  same pattern as `comment_classifications.jsonl`. No assembly script needed.

---

### Sub-Task 6 — Update `data-collection-plan.md` and `README.md`

**Status**: `[x] done`

**Who runs this**: Done once after all other sub-tasks are complete and the new workflow has
been tested on at least one TEP end-to-end.

**Intent**: `data-collection-plan.md` is the authoritative description of the Sub-Task 8
workflow and has been kept in sync with every prior change to the pipeline. `README.md`
documents the available Make targets and directory layout. Both will be out of date once the
new prompts, targets, and directory layout from Sub-Tasks 1–5 are in place.

**Expected Outcomes**:
- `data-collection-plan.md` Sub-Task 8 section reflects the new per-TEP agent scope
  (fragment output only, no shared-file writes), the integration step as a distinct stage,
  and the new `processed/tep<N>/` layout.
- `README.md` lists the new Make targets (`worktree-classify`, `worktree-remove`,
  `permissions`) and describes the parallel classification workflow at a high level.
- No other documents are changed; the prompts themselves are updated in Sub-Tasks 3 and 4.

**Todo List**:
1. Update `data-collection-plan.md`:
   - Sub-Task 8 procedure: replace "Merging, building, verifying" with a reference to the
     integration prompt.
   - Sub-Task 8 storage: add `processed/tep<N>/` to the directory layout diagram and
     describe its contents.
   - Sub-Task 8 step table: add the integration step as a distinct row between classification
     and human review.
2. Update `README.md`:
   - Add `worktree-classify`, `worktree-remove`, and `permissions` to the Make targets list.
   - Add a short "Parallel classification" section describing the agent → human review →
     integration workflow.

---

## Execution order

Sub-Tasks 1 and 2 are independent and can be done in either order. Sub-Task 3 depends on
both (prompt references the worktree path; `.gitignore` change assumes the worktree location
is settled). Sub-Task 4 depends on Sub-Task 3. Sub-Task 5 depends on Sub-Tasks 3 and 4
(references the output paths and the removed sections). Sub-Task 6 depends on all others.

```
1 (permissions) ─┐
                 ├─→ 3 (output layout) ─→ 4 (per-TEP commit) ─→ 5 (integration prompt) ─→ 6 (docs)
2 (worktrees)  ─┘
```
