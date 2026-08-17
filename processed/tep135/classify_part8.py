# processed/tep135/classify_part8.py
# Implementation PR pipeline#6927 "Coschedule per (Isolated) PipelineRun e2e support" -- 30 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR = 6927

add(1264185967, "pipeline", PR, [
    ("artifact", "code", 0.4, "'nit: you can use %s with err.Error rather than ignoring a linter'"),
    ("nature", "structure", 0.4, "error-formatting/lint convention nit"),
])
add(1264187917, "pipeline", PR, [
    ("artifact", "code", 0.6, "'I think we also need to delete the PVCs created by the statefulsets, and update integration tests to ensure those PVCs are actually deleted'"),
    ("artifact", "tests", 0.4, "asks for integration-test coverage of PVC deletion"),
    ("nature", "content", 0.6, "substantive missing-behavior concern"),
])
add(1264188486, "pipeline", PR, [
    ("artifact", "code", 0.5, "asks whether this should replace existing functionality in affinity_assistant_names.go"),
    ("nature", "content", 0.5, "questions possible duplicate functionality"),
    ("principle", "consistency-with-existing", 0.3, "checks new code against an existing equivalent"),
])
add(1264189369, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'nit: it doesn't really make sense to differentiate between nil and a pointer to an empty struct; I'd have tests treat them as equivalent'"),
    ("nature", "content", 0.4, "flags an unintentional-looking test distinction"),
])
add(1264190229, "pipeline", PR, [
    ("artifact", "tests", 0.4, "'nit: could the switch statement be replaced with...' code suggestion"),
    ("nature", "structure", 0.4, "test-helper restructuring suggestion"),
])
add(1264190888, "pipeline", PR, [
    ("artifact", "tests", 0.4, "'nit: I think you can compare expectedErr and err directly'"),
    ("nature", "structure", 0.3, "test-assertion simplification nit"),
])
add(1264191375, "pipeline", PR, [
    ("artifact", "code", 0.5, "'Isn't this only true for affinity assistant per workspace?' -- correctness question about a claim's scope"),
    ("nature", "content", 0.5, "questions correctness of a claim across modes"),
])
add(1264191761, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'why remove these tests?'"),
    ("nature", "content", 0.5, "questions removal of test coverage"),
])
add(1264193275, "pipeline", PR, [
    ("artifact", "tests", 0.4, "'nit: can this be replaced with a more informative message? (or even just t.Fatal(err))'"),
    ("nature", "structure", 0.3, "test error-message convention"),
])
add(1264193793, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'could this be simplified to use existing helpers like t.IsFailure?'"),
    ("nature", "structure", 0.3, "suggests using an existing test helper"),
    ("principle", "simplicity", 0.3, "prefers existing helper over custom logic"),
])
add(1264195654, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'how do you prevent the integration test from interfering with the other integration tests? Do they just run sequentially?'"),
    ("nature", "content", 0.5, "substantive question about integration-test isolation"),
])
add(1264195892, "pipeline", PR, [
    ("artifact", "tests", 0.5, "asks to use default-value variables rather than hard-coded values so the test doesn't need updating if defaults change"),
    ("nature", "content", 0.5, "substantive test-maintainability concern"),
    ("nature", "structure", 0.3, "avoiding hard-coded duplication of default values"),
])
add(1267318643, "pipeline", PR, [
    ("artifact", "incremental-delivery", 0.5, "splits cleanup/PVC-deletion logic into a separate PR (#6940), sequences merges, /hold"),
    ("nature", "content", 0.5, "substantive PR-sequencing decision"),
])
add(1270819631, "pipeline", PR, [
    ("artifact", "code", 0.4, "reports errorlint still flags %s formatting for errors, needing %w"),
    ("nature", "content", 0.3, "reports a lint-tool finding while iterating on error formatting"),
])
add(1270820861, "pipeline", PR, [
    ("artifact", "code", 0.4, "clarifies the helper function is only used to calculate an annotation value, not a functional duplicate"),
    ("nature", "content", 0.4, "answers the possible-duplicate-functionality question"),
])
add(1270823747, "pipeline", PR, [
    ("artifact", "tests", 0.4, "explains a test failure due to a runtime.Object type mismatch"),
    ("nature", "content", 0.4, "debugging explanation for a test failure"),
])
# 1270825717 "function isAffinityAssistantDisabled is now no longer used and removed" -- routine cleanup note, zero-match
add(1270913041, "pipeline", PR, [
    ("artifact", "tests", 0.5, "explains the behavior change: statefulsets are now created for all TaskRuns, not just PVC-backed ones, changing test expectations"),
    ("nature", "content", 0.5, "substantive explanation of a behavior/expectation change"),
])
add(1270914312, "pipeline", PR, [
    ("artifact", "tests", 0.4, "follows an existing discussion/pattern for running integration tests sequentially, links the issue"),
    ("nature", "content", 0.4, "grounds the test approach in prior project discussion"),
])
# 1270986734 "Thanks! Changed to default value variables" -- ack, zero-match
# 1270987244 "Changed to `t.IsFailure`" -- ack, zero-match
# 1270987396 "error message updated" -- ack, zero-match
# 1270988456 "The cleanup logic test is updated in #6940" -- routine pointer, zero-match
add(1270991563, "pipeline", PR, [
    ("artifact", "tests", 0.5, "explains comparing error messages via .Error() because direct comparison panics on unexported fmt.wrapError fields"),
    ("nature", "content", 0.5, "substantive explanation of a Go error-comparison limitation"),
])
add(1271060902, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'you can do this with cmpopts.EquateErrors I think? This will check that the error is the right type'"),
    ("nature", "content", 0.4, "suggests a more idiomatic error-comparison approach"),
])
# 1271061483 "sorry, missed this!" -- ack, zero-match
add(1271062524, "pipeline", PR, [
    ("artifact", "tests", 0.5, "'I'm a bit confused, why would we want to validate that a statefulset is created with an empty spec? how is that different from a nil pointer?'"),
    ("nature", "content", 0.5, "substantive question about test-assertion intent"),
])
add(1271126947, "pipeline", PR, [
    ("artifact", "tests", 0.4, "explains cmpopts.EquateErrors requires the same error object, and type is validated separately"),
    ("nature", "content", 0.4, "clarifying technical explanation"),
])
add(1271145392, "pipeline", PR, [
    ("artifact", "tests", 0.6,
     "identifies the confusion source (a StatefulSetSpec filter ignoring Replica/Selector) and proposes removing it for fuller coverage"),
    ("nature", "content", 0.5, "substantive test-coverage improvement proposal"),
])
add(1271180881, "pipeline", PR, [
    ("artifact", "tests", 0.5,
     "explains cmpopts.EquateErrors already uses errors.Is, suggests the redundant error-string comparison could be dropped as it adds little value and makes tests more brittle"),
    ("nature", "content", 0.4, "substantive test-brittleness observation"),
])

out_path = "processed/tep135/classify_part8.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
