# processed/tep135/classify_part6.py
# Implementation PR pipeline#6893 "Revert PVC creation" -- 41 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR = 6893

add(1248122738, "pipeline", PR, [
    ("artifact", "code", 0.4, "'would it make sense to revert only this change?' -- questions revert scope"),
    ("nature", "content", 0.4, "questions the scope of the proposed revert"),
])
add(1248127410, "pipeline", PR, [
    ("artifact", "code", 0.5, "explains a partial revert would leave PVCs undeleted on PipelineRun deletion"),
    ("nature", "content", 0.5, "substantive consequence of the narrower revert option"),
])
add(1248129742, "pipeline", PR, [
    ("artifact", "code", 0.4, "flags uncertainty whether #6635 still works with only a partial revert"),
    ("nature", "content", 0.4, "flags a dependency risk from the revert scope"),
])
add(1248173867, "pipeline", PR, [
    ("artifact", "code", 0.6, "proposes a PipelineRun finalizer to delete affinity-assistant PVCs, asks for elaboration on the #6635 concern"),
    ("nature", "content", 0.6, "substantive alternative design proposal"),
])
# 1248228240 "/hold" -- bot command, zero-match
add(1252172648, "pipeline", PR, [
    ("artifact", "code", 0.6, "justifies a full revert over a partial one: PVC ownership reverts to PipelineRuns, and a partial revert would leave inconsistent behavior unless followups land in the same release"),
    ("artifact", "functionality", 0.4, "concerned merging only a partial revert leaves inconsistent, non-releasable-feeling behavior across releases"),
    ("nature", "content", 0.7, "detailed substantive justification for the chosen revert strategy"),
])
add(1252990328, "pipeline", PR, [
    ("artifact", "code", 0.5, "'I'm not sure I understand why this logic is changing. Shouldn't we just need to update createOrUpdateAffinityAssistantsPerAABehavior?'"),
    ("nature", "content", 0.5, "questions the extent of a change"),
])
add(1252992671, "pipeline", PR, [
    ("artifact", "code", 0.5, "'it might be simpler to just remove the switch statement for now, and add it back in later when it's actually needed'"),
    ("nature", "content", 0.4, "suggests deferring unneeded complexity"),
    ("principle", "simplicity", 0.4, "explicitly frames removing unused logic as simpler"),
])
add(1252994019, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'maybe instead replace this with an assertion that the pvc is not deleted?'"),
    ("nature", "content", 0.4, "concrete test-assertion suggestion"),
])
add(1253000172, "pipeline", PR, [
    ("artifact", "code", 0.7,
     "explains the code relies on an implicit assumption (PVCs already created from volume claim templates) that's hard to follow, suggests mode-awareness or better naming/comments"),
    ("nature", "content", 0.6, "substantive readability/correctness-risk concern about an implicit assumption"),
])
add(1253003193, "pipeline", PR, [
    ("artifact", "code", 0.3, "agrees finalizers have limited advantage over owner references given unknowns, approves the PR"),
    ("nature", "content", 0.3, "concludes the finalizer-vs-owner-reference discussion"),
])
add(1253200392, "pipeline", PR, [
    ("artifact", "code", 0.5, "explains intended responsibility split: statefulset-creation stays generic, business logic lives in the calling functions"),
    ("nature", "content", 0.5, "substantive design-responsibility explanation"),
    ("nature", "structure", 0.3, "commits to clarifying variable names and comments"),
])
# 1253276781 "Thanks, Lee! /hold cancel" -- ack, zero-match
# 1253276977 "SGTM, updated" -- ack, zero-match
# 1253277362 "SGTM, updated" -- ack, zero-match
add(1253278838, "pipeline", PR, [
    ("artifact", "code", 0.5, "explains at which point PVCs are created from VolumeClaimTemplate depending on the affinity-assistant behavior mode"),
    ("nature", "content", 0.5, "substantive explanation of mode-dependent behavior"),
])
add(1253372136, "pipeline", PR, [
    ("artifact", "code", 0.6, "suggests moving PVC creation into createOrUpdateAffinityAssistants to reduce assumptions and redundant handling of the disabled case"),
    ("nature", "content", 0.5, "substantive refactor suggestion"),
    ("nature", "structure", 0.4, "code reorganization to reduce redundancy"),
])
add(1253527208, "pipeline", PR, [
    ("artifact", "code", 0.5, "pushes back, prefers separating PVC-creation concerns from affinity-assistant concerns"),
    ("nature", "content", 0.5, "substantive design pushback"),
    ("nature", "cohesion", 0.4, "argues against bundling PVC creation into the affinity-assistant function"),
])
add(1253528110, "pipeline", PR, [
    ("artifact", "code", 0.3, "defends variable naming as accurate, adds clarifying doc instead"),
    ("nature", "content", 0.3, "light clarifying response"),
])
add(1253664086, "pipeline", PR, [
    ("artifact", "code", 0.4, "reports offline agreement to put PVC creation logic in the affinity-assistant creation function to make it atomic"),
    ("nature", "content", 0.4, "records a design decision reached via offline sync"),
])
add(1254529888, "pipeline", PR, [
    ("artifact", "code", 0.4, "'nit: perAABehavior is a bit redundant with the function arguments; we could shorten the function name'"),
    ("nature", "structure", 0.5, "function naming nit"),
])
add(1254534220, "pipeline", PR, [
    ("artifact", "reconciler-pattern", 0.6,
     "'CreatePVCsForWorkspacesWithoutAffinityAssistant will fail if it tries to create PVCs that already exist, but createOrUpdateAffinityAssistantsAndPVCsPerAABehavior runs on every reconcile loop. Will this work past the first reconcile loop?'"),
    ("nature", "content", 0.6, "substantive reconcile-loop idempotency concern"),
])
add(1254539364, "pipeline", PR, [
    ("artifact", "code", 0.4, "'we need to update the docstring of CreatePVCsForWorkspacesWithoutAffinityAssistant' with a link"),
    ("nature", "content", 0.4, "stale docstring flagged"),
])
add(1254543235, "pipeline", PR, [
    ("artifact", "code", 0.6, "provides a concrete alternative refactor, while explicitly noting a preference to keep this PR scoped to the revert"),
    ("nature", "content", 0.5, "substantive alternative implementation sketch"),
    ("nature", "structure", 0.4, "restructures the case-handling logic"),
    ("artifact", "incremental-delivery", 0.4, "'Maybe refactoring changes could be split into a separate PR?'"),
])
add(1254581058, "pipeline", PR, [
    ("artifact", "reconciler-pattern", 0.5,
     "explains the PVC-creation call is guarded by pipelineRunFacts.State.IsBeforeFirstTaskRun() so it only executes once per PipelineRun, addressing the reconcile-loop idempotency concern"),
    ("nature", "content", 0.5, "substantive answer about reconcile-loop safety"),
])
# 1254586005 "Renamed to createOrUpdateAffinityAssistantsAndPVCs" -- ack, zero-match
add(1258400264, "pipeline", PR, [
    ("artifact", "incremental-delivery", 0.4, "agrees to put the refactoring in a separate PR to keep this one scoped"),
    ("nature", "content", 0.3, "scoping decision"),
])
# 1258414562 "This looks great! Thanks Quan." -- pure praise/ack, zero-match
add(1258417772, "pipeline", PR, [
    ("artifact", "code", 0.4, "'would it make sense to change this function name now?'"),
    ("nature", "structure", 0.4, "function-naming question"),
])
add(1258419924, "pipeline", PR, [
    ("artifact", "code", 0.5, "'not a big fan of docstrings that explain how a function is called; sufficient to explain it creates PVCs for workspaces with volumeClaimTemplates'"),
    ("nature", "content", 0.5, "docstring content/scope guidance"),
])
add(1258422092, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'It looks like this is just checking the PVC exists? is it expected that the return value from the client is ignored?'"),
    ("nature", "content", 0.4, "questions an ignored return value in a test assertion"),
])
add(1258422969, "pipeline", PR, [
    ("artifact", "incremental-delivery", 0.5,
     "'I'm approving this PR but I have a strong preference that refactoring changes happen first. typically refactoring changes that get deferred to later just get deprioritized'"),
    ("nature", "content", 0.5, "flags the risk of deferred refactoring never landing"),
])
add(1258658590, "pipeline", PR, [
    ("artifact", "incremental-delivery", 0.5, "explains investigation into scoping, opens a tracking issue for the refactor, argues merging as-is unblocks parallel followup work"),
    ("nature", "content", 0.5, "substantive scoping/sequencing justification"),
])
# 1258661254 "Thank you! I appreciate it!" -- ack, zero-match
add(1258662804, "pipeline", PR, [
    ("artifact", "tests", 0.4, "explains ignoring the return value is fine since the naming-rule check happens via error"),
    ("nature", "content", 0.4, "clarifying test-assertion rationale"),
])
add(1258665828, "pipeline", PR, [
    ("artifact", "code", 0.3, "removes the usage docstring for now, defers full explanation to the followup refactor PR"),
    ("nature", "content", 0.3, "light deferral of a docstring improvement"),
])
add(1258668643, "pipeline", PR, [
    ("artifact", "code", 0.4, "renamed the function to CreatePVCsForWorkspaces to reflect it's now separated from the AA StatefulSet"),
    ("nature", "structure", 0.4, "renaming to reflect the new responsibility split"),
])
add(1258714985, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'nit: Thanks for the comments step by step in the e2e test. Wondering it might be beneficial to add a summary to the docstring here?'"),
    ("nature", "content", 0.4, "requests a summary docstring for a detailed e2e test"),
])
# 1258745476 "SGTM, docstring added" -- ack, zero-match
add(1259852116, "pipeline", PR, [
    ("artifact", "tests", 0.4, "'need to update the docstring for this test'"),
    ("nature", "content", 0.4, "stale test docstring flagged"),
])
# 1259897370 "Good catch, fixed!" -- ack, zero-match

out_path = "processed/tep135/classify_part6.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
