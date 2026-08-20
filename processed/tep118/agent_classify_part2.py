# processed/tep118/classify_part2.py
# Impl PRs #6235 (Add validation for matrix include pipeline parameter variables)
# and #6238 (Add validation for matrix pipeline context parameter variables)
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


# --- PR #6235: TEP-0118: Add validation for matrix include pipeline parameter variables ---
add(1120761443, "pipeline", 6235, [
    ("artifact", "tests", 0.7, "please add tests for these changes"),
])
# 1120827712 (EmmaMunley, self) - points to tests covered in a sibling PR (#6238), cross-PR coordination. zero-match.
# 1120935332 (jerop, "ok, will put a hold on this... /hold") - procedural bot command, zero-match.
# 1122168015 (EmmaMunley, self, "The tests have been added. /hold cancel") - procedural ack, zero-match.
# 1122286986 (jerop, "/unhold") - procedural bot command, zero-match.
add(1122288484, "pipeline", 6235, [
    ("artifact", "code", 0.55, "suggests making this a member function of Matrix, per a pattern suggested elsewhere"),
    ("nature", "structure", 0.4, "receiver/function-shape suggestion"),
])
add(1122292111, "pipeline", 6235, [
    ("artifact", "tests", 0.7, "asks why the test for matrix.params was removed, whether accidental"),
    ("nature", "content", 0.4, "concern about a test-coverage regression"),
])
add(1122293660, "pipeline", 6235, [
    ("artifact", "tests", 0.7, "this test covers invalid contexts everywhere; don't remove existing tests for non-matrix context variables"),
    ("nature", "content", 0.4, "test-coverage regression for unrelated functionality"),
])
add(1122294416, "pipeline", 6235, [
    ("artifact", "tests", 0.65, "don't remove this test; same applies to the other test cases"),
])
# 1122503286 (EmmaMunley, self, "This has been refactored.") - ack, zero-match.
# 1122503366 (EmmaMunley, self, "That was accidental.") - ack, zero-match.
add(1122508934, "pipeline", 6235, [
    ("artifact", "tests", 0.4, "explains the rationale for isolating context-variable tests into TestContextValidMatrix/TestContextInvalidMatrix"),
    ("nature", "content", 0.35, "design rationale for the test split"),
])
add(1123351284, "pipeline", 6235, [
    ("artifact", "code", 0.5, "suggests an early-return guard to reduce nested conditionals"),
    ("nature", "structure", 0.55, "readability/nesting nit"),
])
add(1123356579, "pipeline", 6235, [
    ("artifact", "tests", 0.5, "asks if this test case can be simplified with fewer combinations"),
    ("nature", "content", 0.35, "test data complexity"),
])
add(1123360800, "pipeline", 6235, [
    ("artifact", "tests", 0.6, "confused what this test is for; test name doesn't match what it tests, asks to remove unrelated array params"),
    ("nature", "cohesion", 0.5, "test mixes unrelated array-param content into a string-param test"),
])
add(1123364131, "pipeline", 6235, [
    ("nature", "cohesion", 0.7, "flags unrelated changes leaked in from PR #6238, asks to remove them"),
    ("artifact", "pr-size", 0.35, "unrelated content bundled into this PR"),
])
add(1123371052, "pipeline", 6235, [
    ("artifact", "code", 0.55, "error message indexing (include.params[1]) is confusing for users, suggests a clearer field path"),
    ("nature", "content", 0.5, "clarity/correctness of a user-facing validation error"),
])
add(1123597620, "pipeline", 6235, [
    ("artifact", "tests", 0.5, "suspects a bad rebase since new test classes are being added instead of merged"),
    ("nature", "content", 0.4, "rebase/merge hygiene concern"),
])
add(1123610090, "pipeline", 6235, [
    ("artifact", "incremental-delivery", 0.35, "offers to open a separate PR for test cases that were never added before the referenced PR merged"),
])
add(1123637046, "pipeline", 6235, [
    ("artifact", "incremental-delivery", 0.7, "recommends a separate PR with its own commit message/PR title to explain the reasoning, rather than bundling"),
    ("nature", "cohesion", 0.55, "confusing to understand why these changes are bundled in"),
    ("artifact", "commit-message", 0.4, "use commit message/PR title to explain reasoning"),
])
add(1123739499, "pipeline", 6235, [
    ("artifact", "incremental-delivery", 0.35, "confirms splitting the change out into a separate PR (#6279)"),
])
add(1123810664, "pipeline", 6235, [
    ("artifact", "code", 0.4, "explains a nil check can be removed since it's already verified elsewhere"),
    ("nature", "structure", 0.35, "redundant-check removal rationale"),
])
add(1123875393, "pipeline", 6235, [
    ("principle", "crd-version-policy", 0.55, "asks whether this test missing from v1/pipeline_validation_test.go should be added there too"),
    ("artifact", "tests", 0.55, "test coverage gap in the parallel API version"),
])
add(1123877160, "pipeline", 6235, [
    ("artifact", "tests", 0.65, "suggests adding a similar test for matrix.params if it doesn't already exist, with a concrete example"),
])
add(1127060717, "pipeline", 6235, [
    ("artifact", "code", 0.55, "asks to move this function to matrix_types.go for better code organization"),
])
add(1127061520, "pipeline", 6235, [
    ("artifact", "code", 0.4, "should live alongside the other matrix member functions"),
])
add(1127093295, "pipeline", 6235, [
    ("artifact", "code", 0.5, "confused why include only validates string params while matrix validates array params - asymmetric validation"),
    ("nature", "content", 0.5, "clarity of validation logic asymmetry"),
])
add(1127116538, "pipeline", 6235, [
    ("artifact", "code", 0.5, "suggests adding a comment to explain the validation asymmetry"),
    ("nature", "content", 0.45, "missing explanatory comment"),
])
add(1127142440, "pipeline", 6235, [
    ("artifact", "code", 0.4, "explains the asymmetry is intentional per the TEP's API design and existing type validation function"),
    ("nature", "content", 0.35, "clarifying design rationale with reference to the TEP and existing validation"),
])

# --- PR #6238: TEP-0118: Add validation for matrix pipeline context parameter variables ---
# 1119092190 (lbernick, "Thank you for writing a docstring!") - compliment, zero-match.
add(1119094374, "pipeline", 6238, [
    ("artifact", "code", 0.55, "suggests including the received param's type in the error message"),
    ("nature", "content", 0.5, "error message content improvement"),
])
add(1119098553, "pipeline", 6238, [
    ("artifact", "tests", 0.55, "test covers an invalid param in both task.params and matrix.include.params; asks to scope to matrix.include only"),
    ("nature", "cohesion", 0.5, "test conflates two unrelated things"),
])
add(1119099733, "pipeline", 6238, [
    ("artifact", "tests", 0.5, "asks what this test case covers that existing test cases don't"),
    ("nature", "content", 0.4, "redundant-test justification"),
])
add(1120187445, "pipeline", 6238, [
    ("artifact", "tests", 0.35, "follow-up nudge that an earlier comment wasn't addressed, applies to all the test cases"),
])
add(1120305188, "pipeline", 6238, [
    ("artifact", "tests", 0.5, "this case is already covered by the previous test case"),
    ("nature", "cohesion", 0.4, "redundant test case"),
])
add(1120305926, "pipeline", 6238, [
    ("artifact", "tests", 0.5, "please remove params from these test cases"),
    ("nature", "cohesion", 0.45, "scope tests down to remove unrelated params"),
])
add(1120307165, "pipeline", 6238, [
    ("principle", "crd-version-policy", 0.65, "make sure to keep v1beta1 in sync with v1 - copy over the changes made in v1 tests"),
    ("artifact", "tests", 0.5, "test parity between API versions"),
])
add(1120860066, "pipeline", 6238, [
    ("artifact", "code", 0.45, "discussion of introducing a named `Params []Param` type instead of using `[]Param` directly"),
    ("principle", "tekton-api-conventions", 0.4, "proposes a more structural/idiomatic collection type for consistency"),
])
add(1120865227, "pipeline", 6238, [
    ("artifact", "code", 0.5, "suggests reusing a common function for retrieving values from params instead of duplicating logic - code-level DRY, not the Tekton reusability design principle"),
])
add(1120908681, "pipeline", 6238, [
    ("artifact", "incremental-delivery", 0.45, "asks the author to follow up once the referenced PR #6180 is resolved"),
])

out_path = "processed/tep118/classify_part2.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
