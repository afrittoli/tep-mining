# processed/tep118/classify_part5.py
# Impl PRs #6345 (Apply Param and Result Replacements in Matrix), #6346 (Update Pipeline
# Conversion for Matrix Include Parameters), #6348 (Update PipelineTaskResultRefs for Matrix
# Include Parameters), #6349 (Validate Matrix Include Parameters are unique), #6418 (Update
# TaskRun Validation for Matrix Include Params)
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


# --- PR #6345: TEP-0118: Apply Param and Result Replacements in Matrix ---
add(1132879361, "pipeline", 6345, [
    ("artifact", "code", 0.55, "questions how indexing into a string param passes validation"),
    ("nature", "content", 0.5, "validation-correctness concern about test data"),
])
add(1132879522, "pipeline", 6345, [
    ("artifact", "tests", 0.55, "asks whether existing tests cover this functionality and a related test case"),
])
add(1132881007, "pipeline", 6345, [
    ("artifact", "tests", 0.45, "asks if this test case differs from the previous one"),
    ("nature", "content", 0.4, "redundant-test question"),
])
add(1132881359, "pipeline", 6345, [
    ("artifact", "tests", 0.55, "suggests testing a case where defaults are overridden"),
])
add(1132881761, "pipeline", 6345, [
    ("artifact", "tests", 0.55, "suggests separate tests for string, object, and array param replacement"),
    ("nature", "structure", 0.4, "test organization by kind"),
])
add(1132883884, "pipeline", 6345, [
    ("artifact", "code", 0.5, "asks why array and object replacements aren't supported here, suggests adding a comment"),
    ("nature", "content", 0.45, "missing explanation for a design limitation"),
])
add(1134130024, "pipeline", 6345, [
    ("artifact", "tests", 0.35, "explains which Apply* functions already have matrix test coverage and which don't"),
])
add(1134209688, "pipeline", 6345, [
    ("artifact", "code", 0.6, "explains array/object results aren't yet supported in matrix.params by design, and matrix.include.params should only get string results, citing the TEP's API-change spec"),
    ("artifact", "tep-body", 0.3, "cites the TEP's own API-change section as the source of the string-only constraint"),
    ("nature", "content", 0.5, "substantive design-constraint explanation"),
])
add(1134579128, "pipeline", 6345, [
    ("principle", "feature-graduation", 0.6, "questions why beta API fields are being enabled in a test for an alpha feature"),
    ("artifact", "tests", 0.4, "incorrect feature-gate level used in a test"),
])
add(1134615825, "pipeline", 6345, [
    ("principle", "feature-graduation", 0.3, "confirms the copy-paste error enabling beta was fixed to enable alpha instead"),
])
add(1135702134, "pipeline", 6345, [
    ("artifact", "tests", 0.5, "asks whether this example demonstrates object or string replacements, tracing through the replacement code"),
    ("nature", "content", 0.45, "semantics clarity of a test example"),
])
add(1135706123, "pipeline", 6345, [
    ("artifact", "code", 0.6, "proposes exact semantics: matrix.params gets string or array replacements, matrix.include.params gets string replacements only, with a concrete code suggestion"),
    ("nature", "content", 0.5, "substantive correctness suggestion about which replacement types apply where"),
])
add(1135754026, "pipeline", 6345, [
    ("artifact", "tests", 0.5, "asks to keep this test case but clarify it tests string replacements from object params"),
    ("nature", "content", 0.4, "test naming/clarity"),
])
add(1135760869, "pipeline", 6345, [
    ("artifact", "tests", 0.55, "asks to restore a removed test, calling it useful and confirming understanding of replacements"),
])
add(1135808160, "pipeline", 6345, [
    ("artifact", "docs", 0.55, "asks for examples demonstrating this substitution, suggests its own subsection"),
    ("nature", "content", 0.45, "doc completeness/organization"),
])
add(1136059777, "pipeline", 6345, [
    ("artifact", "docs", 0.45, "suggested wording covering array replacements from param values"),
    ("nature", "structure", 0.35, "doc wording suggestion"),
])
add(1136063106, "pipeline", 6345, [
    ("artifact", "docs", 0.55, "suggested full example distinguishing whole-array vs. indexed replacement"),
    ("nature", "content", 0.4, "concrete example addition"),
])
add(1136072753, "pipeline", 6345, [
    ("artifact", "docs", 0.55, "suggested full PipelineRun example demonstrating string replacement in matrix.include"),
    ("nature", "content", 0.4, "concrete example addition"),
])
add(1136219710, "pipeline", 6345, [
    ("artifact", "code", 0.45, "non-blocking suggestion to use an exported config helper instead of ad hoc setup, notes attempt to export it elsewhere - code-level DRY, not the Tekton reusability design principle"),
])
add(1136229098, "pipeline", 6345, [
    ("artifact", "tests", 0.4, "asks what 'override default' means in this test case"),
    ("nature", "content", 0.4, "test clarity question"),
])
add(1136232590, "pipeline", 6345, [
    ("artifact", "tests", 0.45, "test values 'param!' and 'param!!' are hard to visually distinguish, suggests clearer values"),
    ("nature", "structure", 0.4, "test data readability"),
])
add(1136236471, "pipeline", 6345, [
    ("artifact", "code", 0.5, "detailed question about whether object result values are supported for string replacement, and which combinations are actually tested"),
    ("nature", "content", 0.5, "substantive coverage/design question about supported replacement sources"),
])
add(1136275631, "pipeline", 6345, [
    ("artifact", "docs", 0.4, "suggested wording introducing the two Matrix parameter sections"),
    ("nature", "structure", 0.3, "doc wording suggestion"),
])
add(1136307389, "pipeline", 6345, [
    ("artifact", "code", 0.5, "suggests the Finally section handle replacements the same way as the Tasks section above, with a code suggestion"),
    ("principle", "consistency-with-existing", 0.4, "Finally should behave consistently with Tasks for the same replacement logic"),
])
add(1136999471, "pipeline", 6345, [
    ("artifact", "code", 0.55, "suggested comment and code documenting that only string replacements are supported now, with array replacement planned (#5925)"),
    ("artifact", "incremental-delivery", 0.3, "documents a planned future increment"),
    ("nature", "content", 0.45, "clarifying current vs. planned replacement support"),
])
add(1137325975, "pipeline", 6345, [
    ("artifact", "tests", 0.4, "suggested test value using results indexing for clarity"),
    ("nature", "structure", 0.3, "test data suggestion"),
])
add(1137326830, "pipeline", 6345, [
    ("artifact", "tests", 0.4, "suggests simplifying test values to short strings"),
    ("principle", "simplicity", 0.3, "simpler test data"),
    ("nature", "structure", 0.35, "test data simplification"),
])
add(1137327313, "pipeline", 6345, [
    ("artifact", "tests", 0.35, "same test-value simplification applied to another case"),
    ("nature", "structure", 0.3, "test data simplification"),
])
add(1137328141, "pipeline", 6345, [
    ("artifact", "tests", 0.35, "same test-value simplification applied again"),
    ("nature", "structure", 0.3, "test data simplification"),
])

# --- PR #6346: TEP-0118: Update Pipeline Conversion for Matrix Include Parameters ---
add(1132764644, "pipeline", 6346, [
    ("artifact", "code", 0.45, "suggested code using the loop index for the conversion below"),
    ("nature", "structure", 0.4, "code-shape suggestion"),
])
add(1132766986, "pipeline", 6346, [
    ("artifact", "code", 0.45, "suggested code appending via the corrected index"),
    ("nature", "structure", 0.4, "code-shape suggestion"),
])
add(1132809741, "pipeline", 6346, [
    ("artifact", "code", 0.4, "confirms the indexing fix suggested elsewhere should also apply here"),
])

# --- PR #6348: TEP-0118: Update PipelineTaskResultRefs for Matrix Include Parameters ---
add(1134638221, "pipeline", 6348, [
    ("artifact", "tests", 0.5, "asks to keep existing tests unchanged and add include-related cases after, with specific naming"),
    ("nature", "structure", 0.4, "test organization/ordering"),
])

# --- PR #6349: TEP-0118: Validate Matrix Include Parameters are unique in Matrix and Pipeline Task Parameters ---
add(1134332154, "pipeline", 6349, [
    ("artifact", "code", 0.5, "asks if matrix parameter names are fetched elsewhere and suggests a reusable matrix.getParamNames() helper - code-level DRY, not the Tekton reusability design principle"),
])
add(1134335776, "pipeline", 6349, [
    ("artifact", "tests", 0.4, "suggested test-name rename for clarity"),
    ("nature", "structure", 0.4, "test naming"),
])
add(1134336242, "pipeline", 6349, [
    ("artifact", "tests", 0.4, "suggested test-name rename for clarity"),
    ("nature", "structure", 0.4, "test naming"),
])
add(1134487816, "pipeline", 6349, [
    ("artifact", "code", 0.3, "adds matrix.getParamNames() and params.getNames() helper functions for future use, even though not yet used elsewhere"),
])

# --- PR #6418: TEP-0118: Update TaskRun Validation for Matrix Include Params ---
add(1146289578, "pipeline", 6418, [
    ("artifact", "tests", 0.65, "notes the test for m.Params was removed while adding m.Include.Params; asks that both be covered"),
    ("nature", "content", 0.45, "test-coverage regression concern"),
])
add(1146512416, "pipeline", 6418, [
    ("artifact", "code", 0.45, "nit that matrixAllParams is redundant/awkward naming, suggests matrixParams plus a docstring"),
    ("nature", "structure", 0.5, "naming and missing-docstring nit"),
])
add(1146519673, "pipeline", 6418, [
    ("artifact", "code", 0.55, "asks the author to double check this function doesn't mutate its inputs"),
    ("nature", "content", 0.5, "mutation/side-effect correctness concern"),
])
add(1146521155, "pipeline", 6418, [
    ("artifact", "code", 0.5, "asks for docstrings on the modified functions"),
    ("nature", "content", 0.4, "missing docstrings"),
])
add(1146523497, "pipeline", 6418, [
    ("artifact", "code", 0.45, "asks to update the docstring for this function"),
    ("nature", "content", 0.4, "stale docstring"),
])
add(1146538207, "pipeline", 6418, [
    ("nature", "cohesion", 0.55, "this test case tries to test many different things at once; asks to refactor into one-thing-at-a-time cases"),
    ("artifact", "tests", 0.5, "notes missing coverage for an extra object param case"),
])
add(1146543767, "pipeline", 6418, [
    ("artifact", "tests", 0.55, "asks for table-driven testing with descriptive names since these tests cover multiple things"),
    ("nature", "cohesion", 0.4, "multiple concerns tested in one case"),
])
add(1146807761, "pipeline", 6418, [
    ("artifact", "code", 0.45, "suggested docstring content for validateParams"),
    ("nature", "content", 0.4, "docstring content"),
])
add(1146810975, "pipeline", 6418, [
    ("artifact", "code", 0.45, "suggested docstring content for missingParamsNames"),
    ("nature", "content", 0.4, "docstring content"),
])
add(1146824211, "pipeline", 6418, [
    ("artifact", "code", 0.5, "asks for more detail on what 'matching the taskrun' means, notes stale reference to removed Task inputs/outputs"),
    ("nature", "content", 0.5, "docstring completeness and a stale concept reference"),
])
add(1146826026, "pipeline", 6418, [
    ("artifact", "tests", 0.4, "asks why the test switched to t.Fatalf"),
    ("nature", "content", 0.35, "test-assertion style question"),
])
add(1146830846, "pipeline", 6418, [
    ("artifact", "tests", 0.55, "not seeing what happened to the tests for invalid params"),
    ("nature", "content", 0.45, "possible test-coverage regression"),
])
add(1147604270, "pipeline", 6418, [
    ("artifact", "tests", 0.45, "nit that a pointer to an empty matrix is unnecessary; nil should work fine"),
    ("nature", "structure", 0.45, "test code simplification/idiom"),
])
add(1147608937, "pipeline", 6418, [
    ("artifact", "code", 0.5, "suggests including the received vs. specified type in the error message, links a related issue"),
    ("artifact", "incremental-delivery", 0.3, "notes this might be better addressed in a separate PR"),
    ("nature", "content", 0.45, "error message clarity improvement"),
])
add(1147611422, "pipeline", 6418, [
    ("artifact", "tests", 0.5, "asks whether two test cases cover anything not already covered by existing 'extra params' and 'invalid types' cases"),
    ("nature", "content", 0.4, "redundant-test justification"),
])

out_path = "processed/tep118/classify_part5.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
