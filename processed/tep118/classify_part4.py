# processed/tep118/classify_part4.py
# Impl PR #6248 (Enable pipeline to handle matrix include params) and
# PR #6341 (Implement Fanning Out logic to support Matrix Include Parameters in a Task Run)
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


# --- PR #6248: TEP-0118: Enable pipeline to handle matrix include params ---
add(1122213319, "pipeline", 6248, [
    ("artifact", "code", 0.6, "flags leftover debugging evidence in the diff"),
    ("nature", "content", 0.4, "stray debug artifact left in the code"),
])
add(1122227690, "pipeline", 6248, [
    ("principle", "crd-version-policy", 0.55, "asks to add the same test for the v1beta1 API version"),
    ("artifact", "tests", 0.55, "test coverage gap in the parallel API version"),
])
add(1122234764, "pipeline", 6248, [
    ("artifact", "code", 0.35, "please remove the empty line"),
    ("nature", "structure", 0.5, "formatting nit"),
])
add(1122239538, "pipeline", 6248, [
    ("artifact", "tests", 0.5, "asks about Finally tasks and whether a test case is needed to cover that path"),
    ("nature", "content", 0.4, "possible missing test scenario"),
])
add(1122259459, "pipeline", 6248, [
    ("artifact", "tests", 0.45, "asks whether validation logic added in this PR is actually covered by these tests"),
    ("nature", "content", 0.4, "test-to-code coverage mapping question"),
])
add(1131324348, "pipeline", 6248, [
    ("artifact", "tests", 0.55, "questions why round-trip conversion tests were deleted; they might be helpful for newly added cases"),
    ("principle", "crd-version-policy", 0.4, "concerns a v1/v1beta1 round-trip conversion test setup"),
    ("artifact", "incremental-delivery", 0.3, "suggests refactoring in a separate PR if necessary"),
])
add(1131378519, "pipeline", 6248, [
    ("artifact", "code", 0.4, "questions whether the HasInclude condition check is needed here"),
    ("nature", "structure", 0.4, "unnecessary-condition nit"),
])
add(1131406130, "pipeline", 6248, [
    ("nature", "cohesion", 0.65, "reconciler changes don't feel related to the current PR's title/description"),
    ("artifact", "pr-description", 0.4, "scope mismatch between PR description and actual changes"),
])
add(1131664181, "pipeline", 6248, [
    ("artifact", "code", 0.45, "this doesn't actually change the Matrix object, so the iteration could be removed"),
    ("nature", "structure", 0.4, "unnecessary iteration"),
])
add(1132372013, "pipeline", 6248, [
    ("artifact", "code", 0.4, "nit that this check might also be removed"),
    ("nature", "structure", 0.4, "unnecessary-condition nit"),
])

# --- PR #6341: TEP-0118: Implement Fanning Out logic to support Matrix Include Parameters in a Task Run ---
add(1132456899, "pipeline", 6341, [
    ("artifact", "code", 0.5, "wonders if this function can be replaced by just using Params directly"),
    ("principle", "simplicity", 0.35, "avoid an extra abstraction layer"),
])
add(1132457445, "pipeline", 6341, [
    ("artifact", "code", 0.5, "asks whether a String-type check is needed here for StringVal"),
    ("nature", "content", 0.4, "type-safety validation gap"),
])
add(1132520909, "pipeline", 6341, [
    ("artifact", "code", 0.35, "explains the rationale for a param mapping to simplify key/value lookup and merging"),
    ("nature", "content", 0.3, "design rationale"),
])
add(1132562960, "pipeline", 6341, [
    ("artifact", "code", 0.45, "suggested loop refactor"),
    ("nature", "structure", 0.4, "code-shape suggestion"),
])
add(1132628518, "pipeline", 6341, [
    ("artifact", "code", 0.5, "questions whether the refactor is actually cleaner than what existed before"),
    ("principle", "simplicity", 0.35, "pushback on whether the change reduces or adds complexity"),
])
add(1132643247, "pipeline", 6341, [
    ("artifact", "code", 0.3, "acknowledges confusion from reusing similar naming (combination vs combinations)"),
    ("nature", "structure", 0.3, "naming clarity"),
])
add(1132659278, "pipeline", 6341, [
    ("artifact", "code", 0.4, "agrees an earlier version of this code was cleaner before being asked to change it"),
    ("principle", "simplicity", 0.3, "preference for the simpler prior version"),
])
add(1132891355, "pipeline", 6341, [
    ("artifact", "docs", 0.5, "suggested wording clarifying Matrix.Include takes string-typed parameters only"),
    ("nature", "structure", 0.35, "doc wording suggestion"),
])
add(1132891521, "pipeline", 6341, [
    ("artifact", "docs", 0.45, "asks if this block can be removed"),
    ("nature", "cohesion", 0.3, "unnecessary doc content"),
])
add(1132892163, "pipeline", 6341, [
    ("artifact", "docs", 0.5, "suggested wording for describing explicit combinations via Matrix.Include"),
    ("nature", "structure", 0.35, "doc wording suggestion"),
])
add(1132892449, "pipeline", 6341, [
    ("artifact", "docs", 0.5, "suggests removing irrelevant workspaces from the example"),
    ("nature", "cohesion", 0.4, "irrelevant content in a doc example"),
])
add(1132892671, "pipeline", 6341, [
    ("artifact", "docs", 0.5, "suggested wording clarifying what the example Pipeline demonstrates"),
    ("nature", "content", 0.3, "doc example clarity"),
])
add(1132893028, "pipeline", 6341, [
    ("artifact", "docs", 0.55, "suggests explicitly listing the generated combinations in bullets"),
    ("nature", "content", 0.45, "doc completeness/clarity"),
])
add(1132894994, "pipeline", 6341, [
    ("artifact", "docs", 0.6, "notes the TEP has a clear example covering many cases and all cases should be reflected in the docs"),
    ("nature", "content", 0.5, "doc completeness measured against the source TEP"),
])
add(1132897635, "pipeline", 6341, [
    ("artifact", "code", 0.4, "suggested function rename to extractStringParamVals"),
    ("nature", "structure", 0.4, "naming suggestion"),
])
add(1132898254, "pipeline", 6341, [
    ("artifact", "code", 0.4, "suggested function rename to fanOutExplicitCombinations"),
    ("nature", "structure", 0.4, "naming suggestion"),
])
add(1133003222, "pipeline", 6341, [
    ("artifact", "code", 0.65, "identifies that combinations generated from include aren't persisted when both params and include are used, proposes persisting and comparing to replace values"),
    ("nature", "content", 0.55, "substantive correctness/design issue in the fan-out algorithm"),
])
add(1133004461, "pipeline", 6341, [
    ("artifact", "code", 0.35, "links a reference implementation addressing the persistence issue raised above"),
])
add(1133004890, "pipeline", 6341, [
    ("artifact", "code", 0.5, "asks how this differs from combination generation happening earlier in the function"),
    ("nature", "content", 0.4, "possible redundant logic"),
])
add(1133006867, "pipeline", 6341, [
    ("artifact", "tests", 0.35, "notes all unit tests introduced in this PR pass against the proposed reference implementation"),
])
add(1134474180, "pipeline", 6341, [
    ("artifact", "code", 0.4, "suggested docstring for the contains method"),
    ("nature", "structure", 0.35, "docstring clarity"),
])
add(1134474854, "pipeline", 6341, [
    ("artifact", "code", 0.4, "suggested docstring for addNewCombination"),
    ("nature", "structure", 0.35, "docstring clarity"),
])
add(1134496673, "pipeline", 6341, [
    ("artifact", "code", 0.35, "renamed function to shouldAddNewCombination with rationale that the old name implied mutation"),
    ("nature", "structure", 0.35, "naming rationale"),
])
add(1137582789, "pipeline", 6341, [
    ("artifact", "docs", 0.55, "asks for the generated combinations from this include example to be added"),
    ("nature", "content", 0.45, "doc completeness"),
])
add(1137584009, "pipeline", 6341, [
    ("artifact", "docs", 0.45, "suggests putting the simpler example first"),
    ("nature", "structure", 0.4, "doc ordering for readability"),
    ("principle", "simplicity", 0.3, "lead with the simpler case"),
])
add(1137584455, "pipeline", 6341, [
    ("artifact", "docs", 0.45, "questions whether this example is redundant with the previous one"),
    ("nature", "cohesion", 0.4, "redundant doc content"),
])
add(1137588265, "pipeline", 6341, [
    ("artifact", "docs", 0.6, "proposes restructuring the explanation of include semantics into the section where include is first introduced"),
    ("nature", "content", 0.55, "substantive doc restructuring for clarity"),
])
add(1137589091, "pipeline", 6341, [
    ("artifact", "docs", 0.5, "the yaml document separator is confusing to include within an example pipeline spec"),
    ("nature", "structure", 0.4, "example clarity"),
])
add(1137589636, "pipeline", 6341, [
    ("nature", "cohesion", 0.6, "asks whether formatting changes can be removed from this PR"),
    ("artifact", "pr-size", 0.35, "unrelated formatting changes bundled in"),
])
add(1137592419, "pipeline", 6341, [
    ("artifact", "tests", 0.45, "asks how expectedParams differs from want, suggesting redundant test variables"),
    ("nature", "content", 0.4, "test clarity"),
])
add(1137593284, "pipeline", 6341, [
    ("artifact", "tests", 0.4, "suggested test-name rename for clarity"),
    ("nature", "structure", 0.4, "test naming"),
])
add(1137595337, "pipeline", 6341, [
    ("principle", "feature-graduation", 0.65, "questions what 'preview mode' means and suggests describing this as an alpha feature, added to the alpha features table instead"),
    ("artifact", "feature-gate-registration", 0.5, "asks for the feature to be listed in the alpha features table"),
    ("artifact", "docs", 0.4, "terminology/documentation of the feature's maturity stage"),
])
add(1137601736, "pipeline", 6341, [
    ("artifact", "code", 0.45, "suggests trimming the function's return values to only what's used"),
    ("nature", "structure", 0.4, "function signature cleanup"),
])
add(1137602508, "pipeline", 6341, [
    ("artifact", "tests", 0.4, "flags a line that can be removed, should have been caught in an earlier PR"),
    ("nature", "structure", 0.35, "leftover cleanup"),
])
add(1137706178, "pipeline", 6341, [
    ("artifact", "code", 0.35, "explains where this function is used elsewhere via sortedCombination, with code"),
    ("nature", "content", 0.3, "clarifying explanation of function usage"),
])
add(1137706474, "pipeline", 6341, [
    ("artifact", "tests", 0.4, "pushes back asking why this should be removed rather than treated as adding a new combination"),
    ("nature", "content", 0.35, "design pushback on a suggested removal"),
])
add(1137711111, "pipeline", 6341, [
    ("artifact", "tests", 0.5, "clarifies FanOut() doesn't mutate the input matrix, explaining why the next line's behavior is correct"),
    ("nature", "content", 0.5, "correcting a misunderstanding about mutation semantics affecting test correctness"),
])
add(1137746925, "pipeline", 6341, [
    ("principle", "feature-graduation", 0.4, "agrees preview-mode language can now be removed"),
    ("artifact", "docs", 0.35, "updates terminology to reflect the feature's maturity"),
])
add(1137751056, "pipeline", 6341, [
    ("artifact", "tests", 0.5, "suggests simplifying the test case with concrete replacement code"),
    ("principle", "simplicity", 0.35, "reduce test boilerplate"),
    ("nature", "structure", 0.4, "test simplification"),
])
add(1137764860, "pipeline", 6341, [
    ("artifact", "tests", 0.35, "agrees a test can be simplified but wants to confirm with the original author first"),
])
add(1138652588, "pipeline", 6341, [
    ("artifact", "tests", 0.4, "agrees the flagged test line should be removed, likely missed in a previous review"),
])
add(1138745325, "pipeline", 6341, [
    ("artifact", "code", 0.5, "asks if this function can return Params instead of Combinations"),
    ("nature", "content", 0.4, "return-type/API design question"),
])
add(1138784940, "pipeline", 6341, [
    ("artifact", "code", 0.35, "confirms FanOut() now calls an unexported toParams() before returning"),
])
add(1149621640, "pipeline", 6341, [
    ("nature", "cohesion", 0.6, "flags a compiled debug binary (__debug_bin) accidentally committed"),
    ("artifact", "pr-size", 0.4, "stray build artifact bundled into the PR"),
])
add(1149622344, "pipeline", 6341, [
    ("artifact", "docs", 0.4, "asks for a descriptive name for this example file since it will sit alongside other example pipelineruns"),
    ("nature", "structure", 0.45, "naming convention for example files"),
])
add(1149738788, "pipeline", 6341, [
    ("nature", "cohesion", 0.65, "this cleanup is unrelated to the change and isn't applied in the v1 files; asks to remove and open a separate PR for both v1beta1 and v1"),
    ("artifact", "incremental-delivery", 0.55, "asks for the cleanup to move to its own PR"),
    ("principle", "crd-version-policy", 0.5, "cleanup should be applied consistently to both v1beta1 and v1"),
])
add(1149740369, "pipeline", 6341, [
    ("artifact", "docs", 0.4, "asks to update the description of an example file"),
    ("nature", "content", 0.35, "example description accuracy"),
])
add(1149897330, "pipeline", 6341, [
    ("nature", "cohesion", 0.4, "notes the unrelated-cleanup concern applies to all similar changes in this file"),
    ("principle", "crd-version-policy", 0.3, "continuation of the apply-consistently-to-both-versions point"),
])
add(1150778625, "pipeline", 6341, [
    ("artifact", "incremental-delivery", 0.5, "confirms deferring the params cleanup to another PR"),
])
add(1150906083, "pipeline", 6341, [
    ("artifact", "incremental-delivery", 0.35, "confirms a follow-up PR (#6446) was opened based on this one"),
])
add(1151033937, "pipeline", 6341, [
    ("artifact", "pr-description", 0.55, "asks to update the PR description to drop an outdated statement"),
])
add(1151037003, "pipeline", 6341, [
    ("artifact", "code", 0.5, "questions whether an assignment is needed given overwriteCombinations already updates combinations, asks for confirmation"),
    ("nature", "content", 0.45, "correctness question about mutation/assignment semantics"),
])
add(1151062605, "pipeline", 6341, [
    ("artifact", "code", 0.6, "explains a value receiver won't propagate mutation, needs a pointer receiver, with a concrete fix; not blocking"),
    ("nature", "content", 0.5, "substantive Go semantics correctness point about receiver types"),
])
add(1151065707, "pipeline", 6341, [
    ("artifact", "code", 0.45, "NIT that this creates an unnecessary, confusing call chain, not a blocker"),
    ("nature", "structure", 0.5, "readability/complexity nit"),
])
add(1152248346, "pipeline", 6341, [
    ("artifact", "incremental-delivery", 0.3, "confirms a separate PR (#6463) was opened for the flagged receiver-type fix"),
])

out_path = "processed/tep118/classify_part4.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
