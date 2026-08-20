# processed/tep135/classify_part4.py
# Implementation PRs pipeline#6819 "implement per-pipelinerun coscheduling" (25)
# and pipeline#6929 "coschedule isolate pipelinerun" (11) -- 36 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR6819 = 6819
PR6929 = 6929

add(1229731738, "pipeline", PR6819, [
    ("artifact", "code", 0.6, "notes repeated logic between createOrUpdateAffinityAssistantsPerWorkspace and createOrUpdateAffinityAssistants, suggests a merged helper with a mode argument"),
    ("nature", "content", 0.5, "substantive suggestion to consolidate duplicated logic"),
    ("nature", "structure", 0.4, "code-structure refactor to remove duplication"),
])
add(1229736896, "pipeline", PR6819, [
    ("artifact", "incremental-delivery", 0.4, "asks whether #6790 should merge first and this PR rebase onto it, rather than submitting with a TODO"),
    ("nature", "self-containedness", 0.5, "questions the dependency/sequencing between this PR and #6790"),
])
add(1229742878, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "'can you add a docstring for this function?'"),
    ("nature", "content", 0.4, "missing docstring"),
])
add(1229749445, "pipeline", PR6819, [
    ("artifact", "code", 0.6, "'it seems like wb is a redundant argument. could pr.spec.workspaces be used instead?'"),
    ("nature", "content", 0.5, "questions a redundant function argument"),
    ("principle", "simplicity", 0.4, "argues for removing redundant parameters"),
])
add(1229777579, "pipeline", PR6819, [
    ("artifact", "incremental-delivery", 0.4, "'is there a way to implement support for cleanup within this PR?' -- questions deferring cleanup to a later PR"),
    ("nature", "content", 0.4, "asks whether scope should expand to include cleanup now"),
])
add(1230024264, "pipeline", PR6819, [
    ("artifact", "incremental-delivery", 0.6,
     "explains the PR-split plan: this PR and #6790 land in parallel with nothing consumed yet, a follow-up PR glues them together"),
    ("nature", "content", 0.6, "substantive explanation of the PR-splitting strategy"),
    ("nature", "self-containedness", 0.4, "each PR adds implementation but nothing is consumed yet, by design"),
])
add(1230048000, "pipeline", PR6819, [
    ("artifact", "code", 0.4, "notes merging the two functions would save duplicate code but requires #6790 to merge first"),
    ("nature", "content", 0.4, "weighs a refactor against PR sequencing"),
    ("nature", "self-containedness", 0.3, "dependency on another PR merging first"),
])
add(1230066833, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "favors merging #6790 first if it simplifies this PR, or introducing the behavior type here instead"),
    ("nature", "content", 0.5, "substantive design/sequencing suggestion"),
    ("principle", "simplicity", 0.4, "explicitly frames the choice in terms of which path is simpler"),
])
add(1230067582, "pipeline", PR6819, [
    ("nature", "structure", 0.4, "'please link to tracking issues when leaving TODOs in comments' -- TODO formatting convention"),
    ("artifact", "code", 0.3, "defers to author's judgment on PR splits but asks for issue-linked TODOs"),
])
# 1232338782 "I have introduced AffinityAssitantBehavior in this PR and merged the 2 functions, PTAL!" -- routine update, zero-match
# 1232339159 "Thanks! Tracking issue added to the TODOs" -- ack, zero-match
# 1232339652 "Good catch on this one, I've cleaned up the function signature." -- ack, zero-match
add(1232376316, "pipeline", PR6819, [
    ("artifact", "incremental-delivery", 0.5, "plans to implement cleanup logic for coscheduling-pipelinerun mode in a separate PR, adds a TODO"),
    ("nature", "content", 0.4, "scoping decision to defer cleanup logic"),
])
add(1232435654, "pipeline", PR6819, [
    ("artifact", "code", 0.6, "proposes a concrete refactor (loop collecting claims/claimTemplates, then a switch on behavior)"),
    ("nature", "content", 0.5, "substantive alternative implementation"),
    ("nature", "structure", 0.4, "restructures control flow"),
])
add(1232437062, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "'can you please make sure the docstring documents all the function args?'"),
    ("nature", "content", 0.4, "docstring completeness"),
])
add(1232540307, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "explains why the proposed refactor works for the per-pipelinerun case but not per-workspace (needs a per-item creation loop)"),
    ("nature", "content", 0.5, "substantive explanation of why a suggested simplification doesn't fully apply"),
])
add(1232551736, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "'can you have another for loop inside the switch statement?'"),
    ("nature", "content", 0.4, "concrete implementation suggestion"),
])
# 1232736217 "Refactored further based on the comment, PTAL!" -- ack, zero-match
add(1237633512, "pipeline", PR6819, [
    ("artifact", "code", 0.3, "'typo: respctively->respectively'"),
    ("nature", "structure", 0.5, "pure spelling/formatting nit"),
])
add(1237652184, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "'do we need to use the errorutils.NewAggregate(errs) from the original code? It seems to be used to filter out nil from the errs'"),
    ("nature", "content", 0.5, "questions necessity of existing error-handling utility"),
])
add(1238686761, "pipeline", PR6819, [
    ("artifact", "code", 0.5, "explains NewAggregate also formats multiple errors for readability, with an example"),
    ("nature", "content", 0.5, "substantive rationale for keeping the utility"),
])
# 1238687891 "Good catch, fixed!" -- ack, zero-match
add(1246831717, "pipeline", PR6819, [
    ("artifact", "code", 0.4, "clarifies NewAggregate is still used elsewhere and errors remain aggregated at the right level"),
    ("nature", "content", 0.4, "clarifying follow-up explanation"),
])
# 1246842832 "Oh sorry, I was wrong... I think we can resolve this" -- ack, zero-match
# 1246843546 "No worried! ❤️" -- ack, zero-match

# --- pipeline#6929 ---
add(1265328077, "pipeline", PR6929, [
    ("artifact", "code", 0.4, "'What's the reason for this change?' -- clarity question"),
    ("nature", "content", 0.4, "asks for rationale behind an unexplained change"),
])
add(1265331723, "pipeline", PR6929, [
    ("artifact", "code", 0.5, "'why is this no longer using the label selector? Is the reason because the label is not accurate for coschedule = pipelineruns?'"),
    ("nature", "content", 0.5, "substantive question about a behavior change"),
])
add(1265493115, "pipeline", PR6929, [
    ("artifact", "code", 0.5, "explains label selector is still used, but with a different scheduling term type depending on mode"),
    ("nature", "content", 0.5, "substantive clarification of scheduling behavior"),
])
add(1265495192, "pipeline", PR6929, [
    ("artifact", "code", 0.4, "explains the function now needs aaBehavior to determine anti-affinity terms"),
    ("nature", "content", 0.3, "brief rationale for a new parameter"),
])
add(1265496498, "pipeline", PR6929, [
    ("artifact", "code", 0.6, "suggests passing aaBehavior directly into one function rather than threading affinity through multiple calls"),
    ("nature", "content", 0.5, "substantive simplification of the call chain"),
    ("nature", "structure", 0.4, "reduces how far a parameter is threaded through function calls"),
    ("principle", "simplicity", 0.3, "argues for a less convoluted call chain"),
])
add(1265501890, "pipeline", PR6929, [
    ("artifact", "code", 0.4, "suggests a clarifying comment on why a term is required for isolate-pipelineruns but optional otherwise"),
    ("nature", "content", 0.4, "requests explanatory comment for a mode-dependent requirement"),
])
add(1265503461, "pipeline", PR6929, [
    ("artifact", "code", 0.3, "```suggestion``` variable rename '(nit)'"),
    ("nature", "structure", 0.4, "pure naming nit"),
])
add(1265512212, "pipeline", PR6929, [
    ("artifact", "code", 0.5, "explains preference to keep aaBehavior-related logic resolved in one function so affinityAssistantStatefulSet stays single-responsibility"),
    ("nature", "content", 0.5, "substantive design rationale, open to change but not viewed as required"),
])
# 1265529224 "Sure, I have added some comments here" -- ack, zero-match
add(1265542773, "pipeline", PR6929, [
    ("artifact", "code", 0.7,
     "'I prefer the previous behavior. The new behavior adds more logic to tests, making them more brittle, and makes [functions] less readable by adding a new argument'"),
    ("nature", "content", 0.6, "substantive pushback preferring the prior, simpler behavior"),
    ("nature", "structure", 0.4, "flags readability cost of the new function argument, asks for docstring update if kept"),
    ("principle", "simplicity", 0.4, "explicit preference for the less complex prior behavior"),
])
# 1265693696 "SGTM, I have reverted to the previous behavior! And also a somewhat related fix: [PR link]" -- routine resolution, zero-match

out_path = "processed/tep135/classify_part4.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
