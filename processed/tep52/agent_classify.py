# processed/tep52/classify.py
# TEP-52: Tekton Results: Automated Run Resource Cleanup
# Proposal PRs: community#347, community#357 (community#355 has 0 comments, skipped)
# Implementation PR: results#103

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


# ---- community#347 ----

add(581412143, "community", 347, [
    ("artifact", "tep-body", 0.55, "asks why the controller continues to be informed about completed objects and whether restart would reprocess all of them"),
    ("nature", "content", 0.5, "substantive clarifying question about Motivation's problem framing"),
])
add(581413422, "community", 347, [
    ("artifact", "tep-body", 0.6, "flags that pod logs are lost too and suggests adding this as a caveat"),
    ("nature", "content", 0.55, "asks for an additional caveat about log loss impacting dashboard/cli"),
])
add(581414267, "community", 347, [
    ("artifact", "tep-body", 0.5, "asks to flesh out etcd strain the way controller strain was described"),
    ("nature", "content", 0.45, "requests more substantive detail on etcd scaling impact"),
])
add(581414554, "community", 347, [
    ("artifact", "tep-body", 0.4, "clarifying whether 'metadata' means the complete spec and status"),
    ("nature", "content", 0.35, "low-stakes terminology clarification"),
])
add(581415266, "community", 347, [
    ("artifact", "tep-body", 0.4, "asks for more explanation of 'the grace period has not been met yet'"),
    ("nature", "content", 0.35, "clarifying question on Use Cases wording"),
])
add(581415762, "community", 347, [
    ("artifact", "tep-body", 0.65, "asks for a caveat about re-creating a taskrun/pipelinerun with the same name after cleanup, and pod deletion"),
    ("nature", "content", 0.6, "substantive edge-case the TEP should call out"),
])
add(581417527, "community", 347, [
    ("artifact", "tep-body", 0.6, "asks whether grace period can be configured to hours/days, and raises compatibility with external tools relying on k8s API as source of truth"),
    ("nature", "content", 0.6, "two substantive design questions about configurability and external-tool impact"),
])
add(581419594, "community", 347, [
    ("artifact", "tep-body", 0.5, "asks how re-queueing after grace period would actually work"),
    ("nature", "content", 0.45, "clarifying question on mechanism design"),
])
add(581443645, "community", 347, [
    ("artifact", "tep-body", 0.45, "describes reworking the proposal's performance framing and separation-of-concerns argument"),
    ("nature", "content", 0.4, "author revising substantive design argument in Goals"),
])
add(581510744, "community", 347, [
    ("principle", "feature-justification", 0.6, "presents cluster load-test data (etcd/API slowdowns near 10k TaskRuns) as evidence the cleanup feature is needed"),
    ("artifact", "tep-body", 0.55, "substantiates the Motivation section with concrete investigation results"),
    ("nature", "content", 0.55, "detailed empirical follow-up to a motivation question"),
])
add(581515158, "community", 347, [
    ("artifact", "tep-body", 0.55, "added a new Motivation section covering Pod GC precedent"),
    ("nature", "content", 0.5, "substantive addition explaining existing Pod GC exposes similar problems"),
])
add(581516149, "community", 347, [
    ("artifact", "tep-body", 0.45, "clarifies that stored metadata is the full proto-ized CRD including TypeMeta/ObjectMeta"),
    ("nature", "content", 0.4, "answers the earlier metadata-scope question"),
])
add(581518878, "community", 347, [
    ("artifact", "tep-body", 0.3, "confirms the tentative grace-period design and notes a note was added"),
    ("nature", "content", 0.3, "brief but substantive confirmation of design intent"),
])
add(581519773, "community", 347, [
    ("artifact", "tep-body", 0.55, "rewords grace-period definition with pseudocode for clarity"),
    ("nature", "content", 0.5, "substantive redefinition of grace-period semantics"),
])
add(581521108, "community", 347, [
    ("artifact", "tep-body", 0.6, "discusses run-recreation duplicate-results edge case, adds a new section on pod-log loss, and floats a new FR for preserving pod metadata"),
    ("nature", "content", 0.55, "substantive design discussion and content addition"),
])
add(581525457, "community", 347, [
    ("artifact", "tep-body", 0.55, "explains async deletion scheduling mechanics and reconciler-restart safety (idempotent re-processing)"),
    ("nature", "content", 0.5, "detailed mechanism explanation added to the proposal discussion"),
])
# 583775911 bobcatfish "nice!! thanks for doing the additional investigation" - pure ack, zero-match
# 583776938 bobcatfish "ah okay so the ENTIRE object - just (pedantically) checking..." - confirms understanding, no ask, zero-match
add(583781491, "community", 347, [
    ("artifact", "tep-body", 0.55, "works through whether duplicate Results from run recreation is a new risk this proposal introduces, concludes it's pre-existing but worth mentioning"),
    ("nature", "content", 0.5, "substantive risk-analysis discussion"),
])
# 583781866 bobcatfish "lolololol ... sounds like we're covered :D" - jokes + resolution ack, zero-match

# ---- community#357 ----

add(586701259, "community", 357, [
    ("artifact", "tep-body", 0.4, "asks whether 'automated nature of runs being created' specifically means triggering-system-created runs"),
    ("nature", "content", 0.35, "terminology clarification"),
])
add(586702303, "community", 357, [
    ("principle", "simplicity", 0.4, "suggests deferring an optimization to a separate pipelines issue rather than solving it in this proposal"),
    ("artifact", "tep-body", 0.5, "questions whether the lookup approach should be reconsidered or handled via a follow-up issue"),
    ("nature", "content", 0.45, "substantive suggestion to scope out an optimization concern"),
])
add(588555581, "community", 357, [
    ("artifact", "tep-body", 0.4, "asks whether results were observed for taskruns deleted after completion"),
    ("nature", "content", 0.35, "clarifying question about test observations backing the proposal"),
])
add(588556534, "community", 357, [
    ("principle", "consistency-with-existing", 0.5, "points to the existing user-profiles.md doc and suggests reusing its 'Pipeline and Task Users' category instead of a new one"),
    ("artifact", "tep-body", 0.5, "suggests aligning Use Cases terminology with the existing user-profiles doc"),
    ("nature", "content", 0.45, "substantive suggestion to reuse existing categorization"),
])
add(588557694, "community", 357, [
    ("principle", "simplicity", 0.35, "reiterates that the lookup-optimization concern should be handled independent of this proposal"),
    ("artifact", "tep-body", 0.4, "reiterates scoping the optimization question out of this TEP"),
    ("nature", "content", 0.35, "repeats/reinforces the scope-deferral point"),
])
# 588654863 wlynch "Yup! Added a note." - brief ack, zero-match
add(588666500, "community", 357, [
    ("principle", "simplicity", 0.55, "weighs journaling as an alternative to the label-lookup mechanism but flags it would trade for different complexity, particularly name-collision risk"),
    ("artifact", "tep-body", 0.5, "explains why the current label-based lookup mechanism exists"),
    ("nature", "content", 0.5, "substantive design tradeoff discussion"),
])
add(588673495, "community", 357, [
    ("principle", "feature-justification", 0.5, "anecdotal evidence that 'kubectl delete tr --all' fixed a cluster experiencing load problems, supporting the need for cleanup"),
    ("artifact", "tep-body", 0.5, "provides further empirical support and discusses methodology for testing"),
    ("nature", "content", 0.45, "substantive supporting evidence and methodology discussion"),
])
add(588680760, "community", 357, [
    ("principle", "consistency-with-existing", 0.5, "weighs reusing the existing user-profiles.md categories against keeping custom roles that map to multiple existing profiles"),
    ("artifact", "tep-body", 0.55, "elaborates why custom user categories are still useful alongside the existing doc"),
    ("nature", "content", 0.5, "substantive counter-argument in the consistency discussion"),
])
add(590386873, "community", 357, [
    ("principle", "reusability", 0.5, "asks whether the persistence signal should be generalized for use by other systems beyond deletion"),
    ("artifact", "tep-body", 0.5, "raises whether Results should emit broader lifecycle events"),
    ("nature", "content", 0.5, "substantive suggestion to broaden the feature's applicability"),
])
add(590439436, "community", 357, [
    ("principle", "consistency-with-existing", 0.4, "points to TEP-0032 Tekton Notifications as the place this cross-cutting concern belongs"),
    ("artifact", "tep-body", 0.4, "defers the broader event-emission idea to a related TEP"),
    ("nature", "content", 0.35, "brief but substantive scoping response"),
])
# 590626331 wlynch: just a link (filed issue) - zero-match
add(592476515, "community", 357, [
    ("principle", "consistency-with-existing", 0.6, "explicitly argues missing roles should be added to the shared user-profiles.md rather than invented per-TEP"),
    ("artifact", "tep-body", 0.5, "raises whether Use Cases roles should live in the shared doc instead"),
    ("nature", "content", 0.45, "substantive process suggestion, though explicitly non-blocking"),
])
add(592483331, "community", 357, [
    ("principle", "feature-justification", 0.5, "asks for confirmation that list-call latency actually grows with object count even under label filtering, to substantiate the scaling claim"),
    ("artifact", "tep-body", 0.5, "works through and asks to confirm the double-write mechanism underlying the motivation"),
    ("nature", "content", 0.5, "substantive follow-up validating the performance claim"),
])
add(592484640, "community", 357, [
    ("artifact", "tep-body", 0.4, "clarifies/suggests a load-test methodology (bypass pod creation to isolate CRD behavior)"),
    ("nature", "content", 0.35, "methodology suggestion for the investigation backing the proposal"),
])
add(592806756, "community", 357, [
    ("principle", "feature-justification", 0.65, "presents concrete load-test data showing ~2s list latencies at ~7k objects, directly substantiating the performance motivation"),
    ("artifact", "tep-body", 0.6, "adds concrete data to support the Motivation section's scaling claims"),
    ("nature", "content", 0.55, "detailed empirical results shared in the thread"),
])
add(592815845, "community", 357, [
    ("artifact", "tep-body", 0.3, "notes plan to add missing use-case roles in a follow-up PR"),
    ("nature", "content", 0.3, "brief scope note"),
])
add(592816408, "community", 357, [
    ("principle", "feature-justification", 0.45, "qualifies that controller-side latency is less concerning than client list latency since data is cached, refining the performance justification"),
    ("artifact", "tep-body", 0.5, "adds nuance to the performance investigation results"),
    ("nature", "content", 0.45, "substantive qualification of prior data"),
])
add(592817017, "community", 357, [
    ("artifact", "tep-body", 0.35, "discusses whether the controller could create Runs directly in a completed state for test purposes"),
    ("nature", "content", 0.3, "methodology follow-up"),
])
add(595484848, "community", 357, [
    ("principle", "reusability", 0.5, "proposes adding a requirement to emit cloudevents during the Results lifecycle so other systems could consume it, not just deletion"),
    ("artifact", "tep-body", 0.55, "proposes a new Requirements-section item"),
    ("nature", "content", 0.5, "substantive scope-expansion proposal"),
])
add(595486499, "community", 357, [
    ("artifact", "tep-body", 0.6, "points out the TEP text still describes the old controller-list-latency framing and hasn't been updated to reflect the newer investigation"),
    ("nature", "content", 0.55, "flags the TEP document is out of sync with subsequent findings"),
])
# 596106074 bobcatfish: apology/thanks meta-comment - zero-match
add(596256707, "community", 357, [
    ("nature", "cohesion", 0.55, "decides the cloudevents idea deserves its own TEP rather than being bundled into this one"),
    ("artifact", "tep-body", 0.45, "keeps the Requirements section scoped, deferring the broader event idea"),
    ("principle", "simplicity", 0.4, "keeps this proposal to its narrower scope instead of also solving the cloudevents case"),
])
# 596257432 wlynch "Updated! PTAL." - brief ack, zero-match
add(597043983, "community", 357, [
    ("artifact", "tep-body", 0.5, "flags a broken markdown link in the TEP"),
    ("nature", "structure", 0.55, "a formatting defect (broken link), not a substance issue"),
])
# 597801750 wlynch "Fixed!" - ack, zero-match

# ---- results#103 ----

add(605640819, "results", 103, [
    ("artifact", "tests", 0.55, "asks why the extra buffer was added and whether it was fixing an observed test race"),
    ("nature", "content", 0.45, "substantive question about test correctness rationale"),
])
add(605642470, "results", 103, [
    ("artifact", "tests", 0.55, "flags that a minute-long buffer might mask future timing bugs the test should otherwise catch"),
    ("nature", "content", 0.5, "substantive concern about test effectiveness"),
])
add(605652374, "results", 103, [
    ("artifact", "code", 0.55, "suggests two Infof log lines would be better as Debugf given expected audience/verbosity"),
    ("nature", "structure", 0.4, "log-level/verbosity convention suggestion rather than a substance change"),
])
add(605674920, "results", 103, [
    ("artifact", "reconciler-pattern", 0.55, "asks whether the error path re-enqueues the item in the workqueue with backoff"),
    ("nature", "content", 0.45, "substantive question about reconciler retry behavior"),
])
add(605675061, "results", 103, [
    ("artifact", "reconciler-pattern", 0.5, "asks why EnqueueKeyAfter was used instead of EnqueueAfter"),
    ("nature", "content", 0.4, "substantive API-usage question in reconciler/controller code"),
])
add(605675529, "results", 103, [
    ("artifact", "reconciler-pattern", 0.6, "suggests handling k8serrors.IsNotFound as a no-op for the dueling-deletes case"),
    ("artifact", "code", 0.5, "a correctness fix to the deletion error-handling code"),
    ("nature", "content", 0.55, "substantive correctness suggestion, not a style nit"),
])
add(605677533, "results", 103, [
    ("artifact", "code", 0.6, "suggests setting DeleteOptions.Preconditions.UID to avoid deleting the wrong object if two runs share a name"),
    ("artifact", "reconciler-pattern", 0.5, "a correctness safeguard for the reconciler's delete call"),
    ("nature", "content", 0.55, "substantive race-condition/correctness concern"),
])
add(605678387, "results", 103, [
    ("artifact", "pr-size", 0.55, "asks whether an unrelated-looking change belongs in this PR"),
    ("nature", "cohesion", 0.65, "directly questions whether the PR is bundling in something unrelated to deleting completed runs"),
])
# 605868342 wlynch "Don't think so. Done!" - ack, zero-match
add(605868777, "results", 103, [
    ("artifact", "code", 0.35, "notes moving another log line to debug level, following up on the earlier log-level suggestion"),
    ("nature", "structure", 0.3, "minor logging-verbosity fix"),
])
# 605869381 wlynch "Done." - ack, zero-match
# 605869928 wlynch "Great idea! Done." - ack, zero-match
add(605935472, "results", 103, [
    ("artifact", "commit-message", 0.55, "author flags the commit message doesn't yet explain why the change was made and plans to update it"),
    ("artifact", "reconciler-pattern", 0.55, "explains why Record updates need to be conditional now that 'not ready yet' retries happen"),
    ("nature", "content", 0.55, "substantive explanation of reconciler update behavior and its rationale"),
])
add(605951716, "results", 103, [
    ("artifact", "tests", 0.55, "explains the real/fake clock mixing issue the buffer addresses and how the fix avoids masking timing bugs"),
    ("nature", "content", 0.55, "detailed rationale answering the earlier test-buffer concern"),
])
add(605960822, "results", 103, [
    ("artifact", "reconciler-pattern", 0.6, "cites controller-runtime's Reconciler docs and knative/pkg's matching behavior for stopping re-enqueue via a permanent error"),
    ("principle", "consistency-with-existing", 0.45, "aligns the error-handling approach with how knative/pkg does the same thing"),
    ("nature", "content", 0.5, "substantive answer grounded in upstream conventions"),
])
add(606010890, "results", 103, [
    ("artifact", "pr-description", 0.6, "agrees the rationale should be captured in the PR description"),
    ("artifact", "docs", 0.5, "agrees a doc comment should also capture this context"),
    ("nature", "content", 0.5, "explicit ask to document the explanation in two places"),
])

out_path = "processed/tep52/classify.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
