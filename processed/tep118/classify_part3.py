# processed/tep118/classify_part3.py
# Impl PR #6237: TEP-0118: Add validation for matrix combination count with matrix.include params
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


add(1120759194, "pipeline", 6237, [
    ("artifact", "code", 0.5, "flags that an empty string should be a valid parameter value, an edge case in the validation logic"),
    ("nature", "content", 0.4, "correctness of a validation edge case"),
])
add(1120926632, "pipeline", 6237, [
    ("artifact", "code", 0.5, "suggests using the standard library's slices.Contains() instead of a hand-written function - code-level DRY, not the Tekton reusability design principle"),
])
add(1122299827, "pipeline", 6237, [
    ("artifact", "code", 0.6, "argues combination count should just take len(pt.Matrix.Include) and separate the empty-name validation into its own check"),
    ("principle", "simplicity", 0.45, "simpler separation of concerns instead of folding an edge case into the count logic"),
    ("nature", "content", 0.45, "substantive design pushback on validation logic"),
])
add(1122301816, "pipeline", 6237, [
    ("artifact", "code", 0.4, "suggested rewording of a code comment describing what's iterated"),
    ("nature", "structure", 0.35, "comment wording nit"),
])
add(1122305232, "pipeline", 6237, [
    ("artifact", "docs", 0.55, "suggested doc addition clarifying combination count includes both Matrix.Params and Matrix.Include.Params"),
    ("nature", "content", 0.45, "missing documentation detail"),
])
add(1122516969, "pipeline", 6237, [
    ("artifact", "code", 0.35, "follows up asking whether an empty-string param name is valid"),
    ("nature", "content", 0.3, "continuing the empty-param-name validation question"),
])
add(1123225800, "pipeline", 6237, [
    ("artifact", "code", 0.4, "confirms empty param name should not be valid but unsure if validated, asks author to check and open a follow-up PR"),
    ("artifact", "incremental-delivery", 0.5, "proposes deferring the missing validation to a separate PR"),
])
add(1124609072, "pipeline", 6237, [
    ("artifact", "incremental-delivery", 0.45, "confirms no such validation exists and offers to open a separate PR to add it"),
])
add(1124634220, "pipeline", 6237, [
    ("nature", "cohesion", 0.65, "questions whether doc changes here are just auto-formatting; ideally this PR includes only doc changes relevant to the functional change"),
    ("artifact", "docs", 0.4, "unrelated doc formatting churn"),
])
add(1124640580, "pipeline", 6237, [
    ("artifact", "tests", 0.5, "asks whether this test case covers anything a similarly named existing test case doesn't"),
    ("nature", "content", 0.4, "redundant-test justification"),
])
add(1124646782, "pipeline", 6237, [
    ("artifact", "code", 0.45, "suggests removing a confusing comment that describes a map variable without explaining why"),
    ("nature", "structure", 0.5, "comment quality/necessity"),
])
add(1124657585, "pipeline", 6237, [
    ("artifact", "code", 0.5, "suggests moving a code block upward for readability, with a code sample"),
    ("nature", "structure", 0.55, "code readability/ordering suggestion"),
])
add(1127039152, "pipeline", 6237, [
    ("artifact", "docs", 0.35, "explains the doc auto-formatting was confirmed acceptable by the team"),
    ("nature", "cohesion", 0.3, "addressing the earlier concern about unrelated formatting churn"),
])
add(1127069079, "pipeline", 6237, [
    ("nature", "cohesion", 0.55, "questions whether doc layout was unintentionally changed by this PR, doesn't look like pure formatting"),
    ("artifact", "docs", 0.45, "unexpected doc layout changes"),
])
add(1127087222, "pipeline", 6237, [
    ("artifact", "code", 0.5, "variable is actually a map of name to value, not a list of names - suggests renaming for clarity"),
    ("nature", "structure", 0.5, "naming clarity"),
])
add(1127089979, "pipeline", 6237, [
    ("artifact", "code", 0.55, "wonders if a shared extractParamMap helper would be cleaner, and suggests renaming extractParamValuesFromParams to extractValues - code-level DRY, not the Tekton reusability design principle"),
    ("nature", "structure", 0.4, "naming consistency"),
])
add(1127096098, "pipeline", 6237, [
    ("artifact", "code", 0.3, "agrees with and restates the rationale for dropping the redundant 'FromParams' from the function name"),
    ("nature", "structure", 0.3, "naming rationale agreement"),
])
add(1127099941, "pipeline", 6237, [
    ("artifact", "code", 0.5, "consider extracting a separate countNewCombinationsFromInclude function"),
    ("nature", "structure", 0.45, "function decomposition suggestion"),
])
add(1127100621, "pipeline", 6237, [
    ("artifact", "code", 0.5, "consider extracting a separate countGeneratedCombinations function"),
    ("nature", "structure", 0.45, "function decomposition suggestion"),
])
add(1127114415, "pipeline", 6237, [
    ("artifact", "code", 0.35, "explains the purpose of this logic with a concrete non-existent-arch combination example"),
    ("nature", "content", 0.3, "clarifying design rationale"),
])
add(1127125862, "pipeline", 6237, [
    ("artifact", "code", 0.55, "asks whether a duplicated include combination is counted once or twice - an unresolved edge case"),
    ("nature", "content", 0.5, "correctness of a validation edge case"),
])
add(1127130077, "pipeline", 6237, [
    ("artifact", "code", 0.6, "notes the function has three separate code paths and suggests simplifying by extracting a params-count function and overwriting based on include"),
    ("principle", "simplicity", 0.4, "simplify the branching logic"),
    ("nature", "structure", 0.5, "refactor suggestion for readability"),
])
add(1127134094, "pipeline", 6237, [
    ("artifact", "code", 0.6, "provides a full concrete refactor of countParamCombinations/CountCombinations"),
    ("nature", "structure", 0.5, "detailed refactor suggestion"),
])
add(1127144199, "pipeline", 6237, [
    ("artifact", "code", 0.4, "raises uncertainty about whether a duplicated include parameter is valid, asks for confirmation"),
    ("nature", "content", 0.35, "unresolved design question flagged by the author"),
])
add(1127194369, "pipeline", 6237, [
    ("artifact", "code", 0.55, "asks whether duplicate-param validation exists upstream, and argues for consistency with how params validation works elsewhere"),
    ("principle", "consistency-with-existing", 0.5, "wants duplicate-handling to be consistent with existing params behavior"),
    ("nature", "content", 0.45, "substantive validation-consistency concern"),
])
add(1127197875, "pipeline", 6237, [
    ("artifact", "code", 0.5, "suggests paramMap construction move into countNewCombinationsFromInclude, and that hasInclude check becomes redundant"),
    ("nature", "structure", 0.45, "code structure/redundancy"),
])
add(1127198735, "pipeline", 6237, [
    ("artifact", "code", 0.5, "suggests making countNewCombinationsFromInclude a member function instead of passing m.Include as a param"),
    ("nature", "structure", 0.45, "function-shape suggestion"),
])
add(1127199715, "pipeline", 6237, [
    ("artifact", "code", 0.5, "same member-function suggestion applies to a similar function"),
    ("nature", "structure", 0.4, "function-shape suggestion"),
])
add(1127403404, "pipeline", 6237, [
    ("artifact", "incremental-delivery", 0.4, "notes a follow-up PR (#6308) was created implementing the duplicate-params validation gap identified earlier"),
])
add(1127957238, "pipeline", 6237, [
    ("artifact", "incremental-delivery", 0.6, "clarifies a rename should happen in a separate commit/PR since it's unrelated to this change"),
    ("nature", "cohesion", 0.55, "unrelated rename bundled into this PR"),
])
add(1127959766, "pipeline", 6237, [
    ("artifact", "code", 0.4, "minor suggested refactor of the combination-count accumulation"),
    ("nature", "structure", 0.3, "small code-shape suggestion"),
])
add(1127961069, "pipeline", 6237, [
    ("artifact", "code", 0.4, "suggested guard-clause reorganization of the function"),
    ("nature", "structure", 0.35, "control-flow restructuring suggestion"),
])
add(1127962650, "pipeline", 6237, [
    ("artifact", "code", 0.4, "suggests removing a line as unnecessary"),
    ("nature", "structure", 0.35, "dead/unneeded code removal"),
])
add(1127964378, "pipeline", 6237, [
    ("artifact", "code", 0.45, "suggested guard-clause addition for the zero-params case"),
    ("nature", "structure", 0.3, "control-flow restructuring suggestion"),
])
add(1128042784, "pipeline", 6237, [
    ("artifact", "code", 0.4, "defends why a check is necessary to correctly handle the Include-only edge case"),
    ("nature", "content", 0.35, "design-correctness defense of an edge-case check"),
])
add(1128065602, "pipeline", 6237, [
    ("artifact", "code", 0.5, "walks through the math showing two code paths are logically equivalent, suggests moving the check for a performance win instead"),
    ("nature", "content", 0.4, "logical-equivalence argument about validation branches"),
])
add(1128071626, "pipeline", 6237, [
    ("artifact", "code", 0.45, "suggested guard-clause reorganization with concrete code"),
    ("nature", "structure", 0.4, "control-flow restructuring suggestion"),
])
add(1128080366, "pipeline", 6237, [
    ("artifact", "code", 0.4, "suggested rename to countGeneratedCombinationsFromParams for clarity"),
    ("nature", "structure", 0.35, "naming suggestion"),
])
add(1128245683, "pipeline", 6237, [
    ("artifact", "code", 0.4, "clarifies a condition isn't strictly necessary but reasonably avoids an extra function call"),
    ("nature", "content", 0.35, "performance/necessity clarification"),
])

out_path = "processed/tep118/classify_part3.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
