# processed/tep135/classify_part9.py
# Implementation PRs pipeline#6940 "Purge finalizer and delete PVC" (19)
# and pipeline#6994 "Improve workspace related documentation" (15) -- 34 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR6940 = 6940
PR6994 = 6994

add(1268155966, "pipeline", PR6940, [
    ("artifact", "tests", 0.6, "'can you test the case where multiple PVCs have been created? (for per pipelinerun mode)'"),
    ("nature", "content", 0.5, "test coverage gap for a multi-PVC scenario"),
])
add(1268158686, "pipeline", PR6940, [
    ("artifact", "tests", 0.6, "'for per workspace mode, can you test the case where multiple statefulsets exist?' suggests possibly splitting into two test classes"),
    ("nature", "content", 0.5, "test coverage gap for a multi-statefulset scenario"),
    ("nature", "structure", 0.3, "suggests restructuring tests to separate the two modes"),
])
add(1268159341, "pipeline", PR6940, [
    ("artifact", "code", 0.5, "'Can you add a note about why we're deleting this finalizer, and link to the k8s docs?'"),
    ("nature", "content", 0.4, "requests explanatory context for a non-obvious operation"),
])
add(1268162488, "pipeline", PR6940, [
    ("artifact", "code", 0.5, "'It seems simpler to just use the \"remove\" operation... this would also let us make removeFinalizerBytes a constant var'"),
    ("nature", "content", 0.4, "substantive alternative-approach suggestion"),
    ("principle", "simplicity", 0.4, "explicitly frames the alternative as simpler"),
])
add(1268165441, "pipeline", PR6940, [
    ("artifact", "incremental-delivery", 0.4, "'could you link an issue as a TODO for adding optional PVC deletion for per-workspace mode?'"),
    ("nature", "structure", 0.3, "TODO/issue-link convention"),
])
add(1268166763, "pipeline", PR6940, [
    ("artifact", "code", 0.4, "'nit: Is there a constant defined for this value in k8s libs anywhere?'"),
    ("nature", "content", 0.3, "asks whether a hardcoded value has an existing constant"),
])
# 1268519382 "TODO link added" -- ack, zero-match
# 1268519774 "docstring added for the function with k8s doc link" -- routine ack, zero-match
add(1268520753, "pipeline", PR6940, [
    ("artifact", "code", 0.5, "explains the constant exists only in k8s.io/kubernetes, a package not recommended to import directly"),
    ("nature", "content", 0.5, "substantive constraint explanation"),
])
# 1268522310 "I have updated the test case to test multiple PVCs and Affinity Assistants, PTAL" -- routine ack, zero-match
# 1268522531 "Please see the above comment" -- ack, zero-match
add(1268523384, "pipeline", PR6940, [
    ("artifact", "code", 0.4, "reading the jsonpatch doc, questions whether the finalizer's index is needed to remove it"),
    ("nature", "content", 0.4, "investigative question about implementation approach"),
])
add(1268527737, "pipeline", PR6940, [
    ("artifact", "tests", 0.5, "'nit: \"expected\" in the test name is confusing, because you're using this as input data'"),
    ("nature", "structure", 0.4, "test-naming clarity nit"),
])
add(1268528336, "pipeline", PR6940, [
    ("artifact", "code", 0.4, "```suggestion``` clarifying comment about why the pvc-protection finalizer is purged"),
    ("nature", "content", 0.3, "clarifies rationale in a code comment"),
])
add(1268529323, "pipeline", PR6940, [
    ("artifact", "code", 0.3, "'ah I suppose you'd still have to iterate over the finalizers-- either approach is fine' -- closes out the remove-operation discussion"),
    ("nature", "content", 0.3, "light concluding remark on an implementation approach"),
])
add(1268530350, "pipeline", PR6940, [
    ("artifact", "code", 0.4, "'nit: This comment doesn't add clarification; I'd update to focus on \"why\" or just remove it'"),
    ("nature", "content", 0.4, "flags a low-value code comment"),
])
# 1268537703 "thanks, removed 'expected'" -- ack, zero-match
# 1268538023 "😅, fixed" -- ack, zero-match
add(1268540015, "pipeline", PR6940, [
    ("artifact", "tests", 0.4, "adds more detail to a test comment, explains commenting setup/execution/validate sections as a habit"),
    ("nature", "content", 0.4, "substantive test-comment improvement"),
    ("nature", "structure", 0.3, "adopts a consistent setup/execution/validate comment structure"),
])

# --- pipeline#6994 ---
add(1277717539, "pipeline", PR6994, [
    ("artifact", "docs", 0.6, "suggests replacing the confusing term 'PipelineTaskRun' with specific reworded phrasing"),
    ("nature", "content", 0.5, "substantive doc-clarity rewrite"),
    ("nature", "structure", 0.3, "terminology clarity"),
])
add(1277718243, "pipeline", PR6994, [
    ("artifact", "docs", 0.5, "'Why remove this, as opposed to updating to mention the new coscheduling options?'"),
    ("nature", "content", 0.5, "questions whether removal vs. update is the right call for stale docs"),
])
add(1277718880, "pipeline", PR6994, [
    ("artifact", "docs", 0.6, "'This is only true for some cloud providers; e.g. minikube isn't zonal'"),
    ("nature", "content", 0.6, "factual accuracy correction in the docs"),
])
add(1277719310, "pipeline", PR6994, [
    ("artifact", "docs", 0.3, "'Can you link to an issue here?'"),
    ("nature", "structure", 0.3, "issue-link convention"),
])
add(1277722391, "pipeline", PR6994, [
    ("artifact", "docs", 0.7,
     "detailed suggestion to restructure the section around the features Tekton provides, listing concrete target use cases (zonal clusters, ReadWriteOnce PVCs, multiple PVCs per task)"),
    ("nature", "content", 0.7, "substantive reframing of the docs' organizing principle"),
    ("nature", "structure", 0.4, "restructures how the section is organized"),
])
add(1277725983, "pipeline", PR6994, [
    ("artifact", "docs", 0.4, "```suggestion``` reworded section heading"),
    ("nature", "structure", 0.4, "heading wording"),
])
add(1277731128, "pipeline", PR6994, [
    ("artifact", "docs", 0.7,
     "'This docs section is a bit confusing; what is intended to be the distinction between this docs section and the previous one?' asks to reframe toward user perspective with an example"),
    ("nature", "content", 0.6, "substantive clarity/organization concern between two doc sections"),
])
# 1287481844 "I have remove the term PipelineTaskRun in the whole doc." -- routine ack, zero-match
add(1287483490, "pipeline", PR6994, [
    ("artifact", "docs", 0.5, "explains reframing the whole section to focus on the feature Tekton provides, per feedback"),
    ("nature", "content", 0.5, "substantive rewrite explanation"),
])
# 1287486238 "I rephrased this in the new section below" -- routine ack, zero-match
add(1287667756, "pipeline", PR6994, [
    ("artifact", "docs", 0.4, "'Maybe link to that new section here?'"),
    ("nature", "content", 0.3, "cross-link suggestion between doc sections"),
])
# 1287669614 "This looks a lot better!" -- pure praise, zero-match
add(1287670522, "pipeline", PR6994, [
    ("artifact", "docs", 0.3, "'I'd still like to see an issue even with the updated docs!' -- reiterates the issue-link request"),
    ("nature", "structure", 0.3, "issue-link convention, reiterated"),
])
# 1288760722 "issue links updated!" -- ack, zero-match
add(1288762261, "pipeline", PR6994, [
    ("artifact", "docs", 0.3, "clarifies content was moved to an existing new section rather than needing another one"),
    ("nature", "content", 0.3, "clarifying response about doc organization"),
])

out_path = "processed/tep135/classify_part9.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
