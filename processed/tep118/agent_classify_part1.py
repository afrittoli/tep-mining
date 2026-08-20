# processed/tep118/classify_part1.py
# Proposal PR comments (community#774, #1004) + impl PRs #5383, #6177, #6188, #6219, #6229, #6230
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


# --- Proposal PR: community#774, #1004 ---
# 936933008, 936933087 (jerop, self, "TODO(jerop) add image") - self-note placeholder, zero-match.

add(938162567, "community", 774, [
    ("artifact", "tep-body", 0.6, "walks through two candidate `include` syntaxes with a concrete example, asking which the author intends"),
    ("nature", "content", 0.5, "substantive design exploration of matrix.include syntax"),
])
add(938162950, "community", 774, [
    ("artifact", "tep-body", 0.5, "proposes an alternative design using an array of object params instead of the discussed syntax"),
    ("nature", "content", 0.45, "alternative design proposal for the TEP"),
])
add(938224743, "community", 774, [
    ("artifact", "tep-body", 0.4, "confirms which of two candidate include syntaxes is correct, with a worked combination list for the rejected one"),
    ("nature", "content", 0.35, "substantive semantics confirmation for the proposal"),
])
add(938226135, "community", 774, [
    ("artifact", "tep-body", 0.35, "clarifying that the discussed example is already an array of object params"),
])
# 938226366 (jerop, self, "or could you show me an example of what you mean?") - pure clarifying question, zero-match.
add(938839060, "community", 774, [
    ("principle", "simplicity", 0.6, "argues the alternative syntax is nicer because it avoids writing out combinations for every param, referencing GH Actions precedent"),
    ("artifact", "tep-body", 0.55, "extended design discussion comparing two include syntaxes"),
    ("nature", "content", 0.5, "substantive tradeoff argument"),
])
add(938850058, "community", 774, [
    ("artifact", "tep-body", 0.45, "sketches an alternative array-of-object-params design with a full YAML example"),
    ("nature", "content", 0.4, "concrete alternative design example"),
])
add(938957369, "community", 774, [
    ("principle", "simplicity", 0.4, "declines the array-of-objects design, 'would rather not go there' - avoiding added complexity"),
    ("artifact", "tep-body", 0.4, "design decision on object param support"),
])
add(939218299, "community", 774, [
    ("artifact", "tep-body", 0.5, "walks through the worked combination example step by step to confirm understanding"),
    ("nature", "content", 0.4, "substantive worked example clarifying the proposal's semantics"),
])
add(939219784, "community", 774, [
    ("principle", "simplicity", 0.45, "updates the proposal example to drop the redundant include entry, leveraging the flags default instead"),
    ("artifact", "tep-body", 0.55, "shows a before/after edit of the TEP's example"),
    ("nature", "content", 0.4, "simplification of the worked example"),
])
add(939903534, "community", 774, [
    ("artifact", "tep-body", 0.4, "NIT on the diagram image format choice (jpeg vs. better format for fonts)"),
    ("nature", "structure", 0.6, "flagged explicitly as a NIT about asset format, not content"),
])
# 940400750, 940401171 (jerop, self, "fixed, thanks!" / "updated the proposal, thanks...") - acks, zero-match.
add(940502435, "community", 774, [
    ("principle", "simplicity", 0.4, "agrees the object-param syntax written out is awkward"),
    ("artifact", "tep-body", 0.35, "continuing the syntax-awkwardness discussion"),
])
# 940510164 (lbernick, "thanks, this is way better than my browser example lol") - compliment/ack, zero-match.
add(940510597, "community", 774, [
    ("principle", "reusability", 0.6, "questions why you'd put a param under matrix.include rather than just use it as a regular parameter outside the matrix"),
    ("artifact", "tep-body", 0.4, "design-necessity question about the proposal"),
])
add(940523783, "community", 774, [
    ("artifact", "tep-body", 0.4, "explains the rationale (parity/clarity), citing GH Actions' matrix.include as prior art"),
    ("nature", "content", 0.4, "design rationale for an underspecified scenario"),
])
# 940539779 (abayer, "flags:... should be one of the matrix params here, right?") - clarifying question, zero-match.
add(940547064, "community", 774, [
    ("artifact", "tep-body", 0.35, "clarifies why flags is not a matrix param (has a default value)"),
])
add(1159092848, "community", 1004, [
    ("artifact", "tep-body", 0.4, "asks to update the TEP's date field"),
    ("nature", "structure", 0.55, "administrative/metadata nit, not content"),
])

# --- PR #5383: TEP-0118: matrix: add `matrix.params` field ---
add(958715683, "pipeline", 5383, [
    ("principle", "api-conventions", 0.85, "missing `// +listType=atomic` annotation causes Kubernetes API rule violation / build test failures"),
    ("artifact", "code", 0.5, "API struct field annotation"),
])
add(958718741, "pipeline", 5383, [
    ("artifact", "incremental-delivery", 0.8, "suggests keeping this PR scoped to just moving matrix params, and introducing `include` in a later PR"),
    ("nature", "magnitude", 0.5, "asks to reduce what this PR does"),
    ("artifact", "commit-message", 0.35, "asks to update commit message/PR description/title to match the reduced scope"),
])
# 959123521, 959128917 (chengjoey, self, acks after fixing per feedback) - zero-match.
add(964801740, "pipeline", 5383, [
    ("artifact", "tests", 0.75, "please add tests for this new exported function"),
])
add(964804946, "pipeline", 5383, [
    ("principle", "crd-version-policy", 0.55, "asks for the same test to be added to the v1 API version, not just v1beta1 - the informal v1/v1beta1 sync practice"),
    ("artifact", "tests", 0.6, "test coverage gap in the parallel API version"),
])
# 964864907 (chengjoey, self, "thanks, i've added this test to v1") - ack, zero-match.

# --- PR #6177: TEP-0118: Added `Matrix.Include` field in preview mode ---
add(1108023381, "pipeline", 6177, [
    ("artifact", "code", 0.4, "checking for an existing Go type to reuse before introducing a new one - code-level DRY, not the Tekton reusability design principle"),
])
add(1108030665, "pipeline", 6177, [
    ("principle", "api-conventions", 0.85, "build fails with `list_type_missing` API rule violations, missing `// +listType=atomic`"),
    ("artifact", "code", 0.5, "API struct field annotation"),
])
add(1108030963, "pipeline", 6177, [
    ("principle", "api-conventions", 0.8, "same `// +listType=atomic` annotation missing on a second field"),
    ("artifact", "code", 0.5, "API struct field annotation"),
])
# 1108706988 (EmmaMunley, self, "Thanks for the catch!") - ack, zero-match.
add(1109101906, "pipeline", 6177, [
    ("nature", "cohesion", 0.65, "questions why unrelated swagger.json changes are part of this PR"),
    ("artifact", "pr-size", 0.35, "unrelated file changes bundled into the PR"),
])

# --- PR #6188: TEP-0118: Added Matrix.Include field in preview mode ---
add(1113650387, "pipeline", 6188, [
    ("artifact", "code", 0.45, "NIT: docstring should describe the field's purpose even in preview mode"),
    ("nature", "content", 0.4, "missing explanation in a code comment"),
])
add(1113652709, "pipeline", 6188, [
    ("artifact", "code", 0.45, "same request for a brief explanatory docstring on the v1beta1 field"),
    ("nature", "content", 0.4, "missing explanation in a code comment"),
])
add(1114290776, "pipeline", 6188, [
    ("artifact", "docs", 0.5, "questions an unrelated doc weight change and asks to revert to 404"),
    ("nature", "cohesion", 0.4, "unrelated formatting/metadata change bundled in"),
])
add(1114292924, "pipeline", 6188, [
    ("artifact", "code", 0.45, "suggested docstring text clarifying Include is in preview mode and not yet supported"),
    ("nature", "content", 0.4, "docstring content suggestion"),
])
add(1114296488, "pipeline", 6188, [
    ("artifact", "code", 0.45, "same docstring suggestion applied to the v1beta1 copy"),
    ("nature", "content", 0.4, "docstring content suggestion"),
    ("principle", "crd-version-policy", 0.35, "keeping v1beta1 docstring in sync with v1"),
])
add(1114997256, "pipeline", 6188, [
    ("artifact", "incremental-delivery", 0.5, "confirms plan to add string-type validation in a subsequent PR"),
])
add(1115803335, "pipeline", 6188, [
    ("artifact", "commit-message", 0.5, "updated commit message to call out that validation will be added in a subsequent PR"),
    ("artifact", "incremental-delivery", 0.4, "documents the deferred-validation follow-up plan"),
])

# --- PR #6219: TEP-0118: Add validation for Matrix.Include.Params of type string ---
add(1116231714, "pipeline", 6219, [
    ("artifact", "code", 0.7, "questions whether these functions need to be exported since they're only used within the package"),
])
add(1116232638, "pipeline", 6219, [
    ("artifact", "code", 0.4, "suggested rename/doc-comment clarifying what the function validates"),
    ("nature", "structure", 0.4, "naming/comment clarity suggestion"),
])
add(1116234785, "pipeline", 6219, [
    ("artifact", "code", 0.7, "asks why a function was changed from unexported to exported"),
])
add(1116236474, "pipeline", 6219, [
    ("artifact", "code", 0.45, "flags a code comment as unnecessary because the code is easy to read"),
    ("nature", "structure", 0.5, "comment-necessity nit"),
])
add(1116240736, "pipeline", 6219, [
    ("artifact", "tests", 0.6, "points to an existing matrix validation test and asks new cases go there instead"),
    ("nature", "cohesion", 0.5, "avoid duplicating a parallel test file"),
])

# --- PR #6229: TEP-0118: Add exported functions for validating Matrix.Include and Matrix.Params ---
add(1117300036, "pipeline", 6229, [
    ("artifact", "tests", 0.4, "suggested wording fix for a test assertion error message"),
    ("nature", "structure", 0.35, "wording nit in a test message"),
])
add(1117300929, "pipeline", 6229, [
    ("artifact", "code", 0.4, "nit that a separate variable is redundant here"),
    ("nature", "structure", 0.5, "code redundancy nit"),
])
add(1117331080, "pipeline", 6229, [
    ("artifact", "code", 0.35, "explains the rationale for the three helper functions distinguishing matrix use cases"),
    ("nature", "content", 0.3, "design rationale for helper functions"),
])
# 1117422936 (jerop, clarifying what lbernick meant, quoting a code line) - pure clarification, zero-match.
add(1117449972, "pipeline", 6229, [
    ("principle", "crd-version-policy", 0.45, "asks for the v1 test file to be updated to match the v1beta1 change made earlier in the same PR"),
])
# 1117451929 (EmmaMunley, self, "Oh I see. Thanks!") - ack, zero-match.

# --- PR #6230: TEP-0118: Add validation for Matrix.Include.Params of type string ---
add(1117550609, "pipeline", 6230, [
    ("artifact", "code", 0.45, "flags a code comment as unnecessary because the code is clear"),
    ("nature", "structure", 0.5, "comment-necessity nit"),
])
add(1117550919, "pipeline", 6230, [
    ("artifact", "docs", 0.55, "grammar/punctuation suggestion (stray comma vs colon) in docs/matrix.md"),
    ("nature", "structure", 0.6, "punctuation nit"),
])
add(1117557625, "pipeline", 6230, [
    ("artifact", "code", 0.5, "asks to fix field keys in error paths to reference matrix.include.params correctly"),
    ("nature", "content", 0.4, "correctness of validation error field path"),
])
add(1117558657, "pipeline", 6230, [
    ("artifact", "code", 0.5, "symmetric fix: field keys should reference matrix.params, not matrix.include.params"),
    ("nature", "content", 0.4, "correctness of validation error field path"),
])
add(1117560344, "pipeline", 6230, [
    ("artifact", "tests", 0.5, "suggested fix for test-case error paths to match corrected field keys"),
    ("nature", "content", 0.35, "test correctness following field-key fix"),
])
add(1117560898, "pipeline", 6230, [
    ("artifact", "tests", 0.4, "same field-key fix applies to the other test cases"),
])
add(1117720851, "pipeline", 6230, [
    ("artifact", "code", 0.6, "error message should only apply to matrix.include.params, not all of matrix"),
    ("nature", "content", 0.45, "correctness/precision of a validation error message"),
])
add(1117722359, "pipeline", 6230, [
    ("artifact", "code", 0.6, "symmetric fix: error message should only apply to matrix.params, not all of matrix"),
    ("nature", "content", 0.45, "correctness/precision of a validation error message"),
])
add(1117724453, "pipeline", 6230, [
    ("artifact", "code", 0.45, "flags a code comment as unnecessary"),
    ("nature", "structure", 0.5, "comment-necessity nit"),
])
add(1117725555, "pipeline", 6230, [
    ("artifact", "tests", 0.7, "asks for a missing test case where the parameter is an object type"),
])
add(1117725847, "pipeline", 6230, [
    ("artifact", "incremental-delivery", 0.4, "praises incrementally adding docs alongside the functional change"),
    ("artifact", "docs", 0.35, "positive note on doc completeness for this increment"),
])

out_path = "processed/tep118/classify_part1.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
