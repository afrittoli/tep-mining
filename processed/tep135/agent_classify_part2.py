# processed/tep135/classify_part2.py
# Implementation PR pipeline#6741 "Refactor Affinity Assistant PVC creation" -- 60 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR = 6741

add(1210653865, "pipeline", PR, [
    ("artifact", "code", 0.5, "'can this if statement be removed?' -- asks to remove unneeded conditional"),
    ("nature", "content", 0.4, "questions whether the logic path is still needed"),
])
add(1210654715, "pipeline", PR, [
    ("artifact", "code", 0.6, "flags a stale/inaccurate TODO comment"),
    ("nature", "content", 0.5, "'I don't think this TODO is actually true' -- factual accuracy of the comment"),
    ("nature", "structure", 0.4, "'please link an issue here rather than your username' -- TODO formatting convention"),
])
add(1210668180, "pipeline", PR, [
    ("artifact", "tests", 0.6, "suggests adding an `expectedStatefulSet` field to the test case struct for clarity"),
    ("nature", "structure", 0.5, "test-struct organization to improve readability"),
])
add(1210668322, "pipeline", PR, [
    ("artifact", "tests", 0.4, "```suggestion``` fixing t.Fatalf usage in a test"),
    ("nature", "structure", 0.3, "minor code-style fix suggestion"),
])
add(1210669528, "pipeline", PR, [
    ("artifact", "tests", 0.6, "asks whether the test is for cleanup itself or incidental, and whether it can be separated"),
    ("nature", "structure", 0.5, "test organization / separation of concerns"),
])
add(1210671442, "pipeline", PR, [
    ("artifact", "code", 0.7,
     "'PVCs created by statefulset volumeClaimTemplates are not deleted when the statefulset is deleted, we'll need to update existing cleanup logic'"),
    ("nature", "content", 0.7, "substantive correctness gap in cleanup logic"),
])
add(1210671868, "pipeline", PR, [
    ("artifact", "code", 0.5, "'can you update the docstring of this function?'"),
    ("nature", "content", 0.4, "docstring accuracy/completeness"),
])
add(1210679628, "pipeline", PR, [
    ("artifact", "code", 0.6, "asks whether GetPersistentVolumeClaimName needs updating given it's used elsewhere too"),
    ("nature", "content", 0.6, "correctness/completeness concern about a shared function"),
])
# 1212748267 "Ahh. Good catch!" -- ack, zero-match
# 1212748787 "SGTM, removed" -- ack, zero-match
# 1212749080 "Updated the test, PTAL!" -- ack, zero-match
# 1212749215 "Updated!" -- ack, zero-match
add(1212755859, "pipeline", PR, [
    ("artifact", "tests", 0.5, "explains rationale for keeping cleanup coverage inside this test rather than separating it"),
    ("nature", "content", 0.5, "substantive rationale for test structure decision"),
])
# 1212756155 "Sure, updated!" -- ack, zero-match
add(1212756940, "pipeline", PR, [
    ("artifact", "code", 0.5, "explains GetPersistentVolumeClaimName doesn't need updating since PVC naming logic is unchanged"),
    ("nature", "content", 0.5, "substantive rationale response"),
])
# 1212925020 "Updated the cleanup logic to delete PVCs!" -- routine update ack, zero-match
add(1213430459, "pipeline", PR, [
    ("artifact", "tests", 0.4, "'nit: this formatting is a bit weird, can you collapse the brackets'"),
    ("nature", "structure", 0.5, "pure formatting nit"),
])
add(1213430981, "pipeline", PR, [
    ("artifact", "tests", 0.3, "'Is this based on some sort of testing seed?' -- clarifying question about test data"),
    ("nature", "content", 0.3, "clarification about test data provenance"),
])
add(1213431318, "pipeline", PR, [
    ("artifact", "code", 0.4, "'nit: is this line needed?'"),
    ("nature", "structure", 0.3, "flags possibly-unneeded line"),
])
add(1213432101, "pipeline", PR, [
    ("artifact", "tests", 0.6, "'can you make this a field of the test case, to simplify the amount of logic in the test?'"),
    ("nature", "structure", 0.5, "test-struct restructuring for readability"),
    ("principle", "simplicity", 0.4, "explicitly aims to reduce test logic complexity"),
])
add(1213433426, "pipeline", PR, [
    ("artifact", "tests", 0.7,
     "detailed suggestion to put the whole statefulset spec in the test struct and use cmpopts to ignore unimportant fields, reducing implicit assumptions"),
    ("nature", "structure", 0.6, "significant test-structure redesign to reduce hidden logic/assumptions"),
    ("principle", "simplicity", 0.4, "aims to reduce the amount of logic embedded in the test"),
])
add(1213434529, "pipeline", PR, [
    ("artifact", "tests", 0.6, "'this seems inconsistent with allowing the test case to have multiple expected volume claim templates'"),
    ("nature", "content", 0.4, "flags an internal inconsistency in test design"),
    ("principle", "consistency-with-existing", 0.4, "inconsistency between two parts of the same test design"),
])
add(1213435498, "pipeline", PR, [
    ("artifact", "tests", 0.7,
     "suggests adding test cases combining volumes and volumeClaimTemplates, and asserting an error for the unsupported combination"),
    ("nature", "content", 0.6, "coverage gap for a combination case"),
])
add(1213438800, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'can we call c.cleanupAffinityAssistants regardless of the test case? It shouldn't fail even if we never had to create an affinity assistant'"),
    ("nature", "content", 0.4, "robustness of the cleanup call across test cases"),
])
add(1213442891, "pipeline", PR, [
    ("artifact", "code", 0.5, "```suggestion``` rewriting a function's docstring"),
    ("nature", "content", 0.4, "docstring accuracy improvement"),
])
add(1213443203, "pipeline", PR, [
    ("artifact", "code", 0.5, "'It would also be helpful to document the \"owner\" and \"pipelineTaskSubPath\" arguments'"),
    ("nature", "content", 0.4, "docstring completeness for function arguments"),
])
add(1213443896, "pipeline", PR, [
    ("artifact", "code", 0.6, "'Why does this function return an error now? It doesn't seem to be used'"),
    ("nature", "content", 0.5, "questions an apparently-unused error return"),
])
add(1213444336, "pipeline", PR, [
    ("artifact", "code", 0.5, "'is this the PipelineRun workspace binding or the TaskRun workspace binding?' -- clarity question"),
    ("nature", "content", 0.4, "clarity of what a variable represents"),
])
add(1213446497, "pipeline", PR, [
    ("artifact", "code", 0.7,
     "'If we're applying the volumeClaimTemplate to the statefulset spec, I believe the PVCs generated will have different names than they did previously' -- correctness concern"),
    ("nature", "content", 0.6, "substantive correctness concern about generated PVC naming"),
])
add(1213447313, "pipeline", PR, [
    ("artifact", "code", 0.4, "'curious why \"\" is used here?' -- clarity question"),
    ("nature", "content", 0.3, "clarifying question about a hardcoded value"),
])
add(1213448070, "pipeline", PR, [
    ("artifact", "code", 0.6, "'I think this function returns an error, can you add handling?'"),
    ("nature", "content", 0.5, "missing error handling"),
])
add(1213448944, "pipeline", PR, [
    ("artifact", "code", 0.5, "'can you update the docstring of this function? the docstring should also clarify the function's behavior when claimName is an empty string'"),
    ("nature", "content", 0.5, "docstring completeness for an edge case"),
])
# 1218446005 "Thanks for the suggestion. I have updated the test cases... PTAL!" -- ack, zero-match
add(1218449608, "pipeline", PR, [
    ("artifact", "tests", 0.5, "explains code-coverage rationale and defers dedicated cleanup tests to a follow-up PR given PR size"),
    ("nature", "content", 0.5, "substantive rationale for deferring test coverage"),
])
add(1218451225, "pipeline", PR, [
    ("artifact", "code", 0.4, "explains function naming confusion, renamed the function and docstring"),
    ("nature", "structure", 0.4, "renaming for clarity/readability"),
])
# 1218451497 "Thanks, resolved!" -- ack, zero-match
add(1218452902, "pipeline", PR, [
    ("artifact", "tests", 0.4, "clarifies a test value is deterministic, computed from a specific function"),
    ("nature", "content", 0.4, "clarifying response about test data derivation"),
])
# 1218453496 "Please see the updated test logic" -- ack, zero-match
# 1218453709 "Please see the updated test logic" -- ack, zero-match
# 1218454069 "String doc updated and included documentation..." -- routine ack, zero-match
# 1218454496 "String doc updated!" -- ack, zero-match
# 1218454852 "Good catch, fixed!" -- ack, zero-match
# 1218457600 "You are right, removed!" -- ack, zero-match
# 1218458613 "I probably did some experiment but forgot to put it back... Fixed it." -- ack, zero-match
# 1218460093 "Please see the latest update with new function names..." -- ack, zero-match
# 1218462016 "Thanks, added the test case!" -- ack, zero-match
add(1218481273, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'nit: would it be simpler to create the configmap in all cases, and have the value of disable-affinity-assistant be passed in from the configmap?'"),
    ("nature", "structure", 0.4, "test setup restructuring"),
    ("principle", "simplicity", 0.4, "explicitly argues the alternative is simpler"),
])
add(1218482532, "pipeline", PR, [
    ("artifact", "code", 0.4, "'I'm sort of confused what this means-- do you just mean the file paths are joined?' -- clarity question"),
    ("nature", "content", 0.3, "clarity of docstring wording"),
])
add(1218483172, "pipeline", PR, [
    ("artifact", "code", 0.5,
     "'This comment goes a bit into implementation details. I think what would be most helpful for the docstring is whether this is supposed to be the pipelinerun as owner ref or taskrun'"),
    ("nature", "content", 0.5, "docstring should focus on the right level of detail"),
])
add(1218484570, "pipeline", PR, [
    ("artifact", "code", 0.5, "'can you please add a docstring for this function?'"),
    ("nature", "content", 0.4, "missing docstring"),
])
add(1218493986, "pipeline", PR, [
    ("artifact", "code", 0.4, "'nit: It might make sense to shorten PersistentVolumeClaim to PVC in function names'"),
    ("nature", "structure", 0.5, "naming-convention nit"),
])
add(1218494644, "pipeline", PR, [
    ("artifact", "code", 0.5,
     "notes the new separate functions help readability but one call site (GetPersistentVolumeClaimNameWithoutAffinityAssistant inside createOrUpdateAffinityAssistants) is confusing, suggests a clarifying comment"),
    ("nature", "content", 0.5, "readability/clarity concern about a specific call site"),
])
# 1219500577 "Happy to see it helps with readability! Yeah, added a comment here." -- ack, zero-match
# 1219501920 "updated!" -- ack, zero-match
add(1219502814, "pipeline", PR, [
    ("artifact", "code", 0.3, "confirms the docstring meaning (file paths joined) and updates it for clarity"),
    ("nature", "content", 0.3, "clarifying response, docstring update"),
])
add(1219507883, "pipeline", PR, [
    ("artifact", "tests", 0.5, "proposes using a boolean flag in the test case instead of a full configmap for the single relevant field"),
    ("nature", "content", 0.5, "substantive alternative test-design proposal"),
    ("nature", "structure", 0.3, "test-case shape/readability"),
])
add(1219707211, "pipeline", PR, [
    ("artifact", "tests", 0.5, "agrees with the boolean-flag approach and supplies example code"),
    ("nature", "content", 0.4, "endorses and elaborates the alternative test design"),
])
add(1223167756, "pipeline", PR, [
    ("artifact", "code", 0.5, "'why do we need an array to append claims and claimTemplates?' inside a for loop -- design question"),
    ("nature", "content", 0.5, "questions necessity of a data structure choice"),
])
add(1223193517, "pipeline", PR, [
    ("artifact", "code", 0.5,
     "explains the slice is needed for a follow-up function (createOrUpdateAffinityAssistantsPerPipelineRun) to be added later"),
    ("nature", "content", 0.5, "substantive rationale tied to planned follow-up work"),
])
# 1223195995 "Oh I see, thanks!" -- ack, zero-match

out_path = "processed/tep135/classify_part2.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
