# processed/tep135/classify_part3.py
# Implementation PRs pipeline#6790 "Introduce coschedule feature flags" (28)
# and pipeline#6818 "Add affinity assistant cleanup unit tests" (2) -- 30 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR6790 = 6790
PR6818 = 6818

add(1222101161, "pipeline", PR6790, [
    ("artifact", "docs", 0.6,
     "'I think it would be good to write a section of docs explaining the configuration options... the TEP audience is developers, while our docs audience is cluster operators'"),
    ("nature", "content", 0.6, "substantive request for user-facing docs distinct from the TEP"),
])
add(1222101527, "pipeline", PR6790, [
    ("artifact", "code", 0.4, "```suggestion``` adding a 'still under development' note comment"),
    ("nature", "content", 0.3, "clarifies feature status in a code comment"),
])
add(1222104446, "pipeline", PR6790, [
    ("artifact", "code", 0.6,
     "questions the ordering/validity of introducing 'coschedule-workspaces' relative to the TEP's stated migration plan, and which flag combos should be dis/allowed"),
    ("nature", "content", 0.6, "substantive question about matching implementation sequencing to the TEP-specified migration plan"),
    ("principle", "consistency-with-existing", 0.4, "checks the implementation matches the TEP's documented sequencing"),
])
add(1222106230, "pipeline", PR6790, [
    ("artifact", "code", 0.5, "suggests moving functionality to a more appropriate existing package"),
    ("nature", "structure", 0.4, "code organization / placement, not scoped to this PR"),
])
add(1222107970, "pipeline", PR6790, [
    ("artifact", "tests", 0.6, "'can you also add the case where disable-affinity-assistant is false and coscheduling is disabled?'"),
    ("nature", "content", 0.5, "test coverage gap for a specific flag combination"),
])
add(1222111948, "pipeline", PR6790, [
    ("artifact", "code", 0.4, "'could you also add a TODO here?' with a link to related code"),
    ("nature", "content", 0.3, "requests a TODO marker for related follow-up work"),
])
add(1222169517, "pipeline", PR6790, [
    ("artifact", "code", 0.6, "works through the migration-strategy understanding and asks why a specific flag combo must be disallowed"),
    ("nature", "content", 0.7, "detailed substantive reasoning about backward-compatible migration behavior"),
    ("principle", "api-compatibility", 0.4, "reasoning centers on preserving backward-compatible behavior during migration"),
])
add(1222247145, "pipeline", PR6790, [
    ("artifact", "code", 0.6, "explains why the disable-affinity-assistant + coschedule-workspaces combo is ambiguous, argues to preserve default backward-compatible behavior"),
    ("nature", "content", 0.6, "substantive design reasoning"),
    ("principle", "api-compatibility", 0.6, "'we should preserve backwards compatibility with existing default behavior'"),
])
add(1223156537, "pipeline", PR6790, [
    ("artifact", "tep-body", 0.4, "decides to update the default value of 'coscheduling' and states intent to update the TEP to clarify"),
    ("nature", "content", 0.4, "design decision affecting the documented default"),
])
# 1232765919 "SGTM, I can resolve this in a separate PR" -- procedural deferral, zero-match
# 1232766245 "TODO added to the cleanup function" -- routine ack, zero-match
add(1232766805, "pipeline", PR6790, [
    ("artifact", "tests", 0.3, "explains the flagged combination is already invalid/validated elsewhere, so no test case needed here"),
    ("nature", "content", 0.4, "clarifying rationale for test scope"),
])
# 1232767193 "SGTM, I have added a section for explaination." -- routine ack, zero-match
# 1232767565 "The TEP change is merged... /hold cancel" -- procedural, zero-match
add(1232769227, "pipeline", PR6790, [
    ("artifact", "code", 0.4, "```suggestion``` editing docstring wording for CoscheduleWorkspaces constant"),
    ("nature", "content", 0.3, "minor docstring wording fix"),
])
add(1232769942, "pipeline", PR6790, [
    ("artifact", "docs", 0.6, "'Can you please also add some markdown docs explaining in more detail what this feature is and why someone would want to use it'"),
    ("nature", "content", 0.5, "requests more detailed user-facing docs"),
])
add(1232773698, "pipeline", PR6790, [
    ("artifact", "code", 0.7,
     "argues GetAffinityAssistantBehavior should return an error for invalid combinations rather than silently returning empty string, to fail fast"),
    ("nature", "content", 0.7, "substantive correctness/robustness argument about error handling"),
])
# 1234473114 "Good catch.. Fixed" -- ack, zero-match
add(1234474004, "pipeline", PR6790, [
    ("artifact", "docs", 0.3, "clarifying question: doc vs code comment for the added detail"),
    ("nature", "content", 0.3, "clarification of where content should live"),
])
add(1234475862, "pipeline", PR6790, [
    ("artifact", "tests", 0.5, "explains difficulty testing an invalid-configmap scenario given validation happens at parse time; adds error return type"),
    ("nature", "content", 0.5, "substantive explanation of a testing limitation"),
])
add(1235176501, "pipeline", PR6790, [
    ("artifact", "tests", 0.6, "clarifies tests should cover all 8 flag combinations and return an error for invalid ones"),
    ("nature", "content", 0.6, "specific coverage expectation"),
])
add(1235178679, "pipeline", PR6790, [
    ("artifact", "docs", 0.6, "confirms it's worth writing a dedicated docs section for the affinity assistant, links existing docs"),
    ("nature", "content", 0.5, "substantive docs scoping"),
])
add(1237593707, "pipeline", PR6790, [
    ("artifact", "tests", 0.6,
     "explains SetFeatureFlags/OnConfigChanged doesn't return an error so invalid combos can't be asserted this way; argues existing feature_flags tests already cover it"),
    ("nature", "content", 0.6, "substantive rationale about test coverage responsibility"),
])
add(1237640879, "pipeline", PR6790, [
    ("artifact", "docs", 0.5, "asks to defer the docs write-up to a follow-up PR that adds e2e support"),
    ("artifact", "incremental-delivery", 0.4, "proposes splitting docs into a later PR alongside the feature's e2e follow-up"),
    ("nature", "content", 0.4, "scoping/sequencing request"),
])
add(1238385881, "pipeline", PR6790, [
    ("artifact", "docs", 0.5, "'I think the docs make the most sense in this PR, as this PR is where the user facing configuration options have been introduced'"),
    ("artifact", "incremental-delivery", 0.3, "weighs whether docs should land with this PR or be deferred"),
    ("nature", "content", 0.4, "substantive scoping opinion, open to either"),
])
# 1238387496 "ah ok, sg" -- ack, zero-match
add(1238387756, "pipeline", PR6790, [
    ("artifact", "tests", 0.4, "'can you handle this error with t.Fatalf?'"),
    ("nature", "structure", 0.3, "test error-handling convention nit"),
])
# 1244141355 "Sure, added." -- ack, zero-match

# --- pipeline#6818 ---
add(1227263484, "pipeline", PR6818, [
    ("artifact", "tests", 0.6, "'curious why would we want to remove the cleanups here? ... this seems to test both creation and deletion'"),
    ("nature", "content", 0.5, "questions a test-coverage reduction"),
])
add(1227323130, "pipeline", PR6818, [
    ("artifact", "tests", 0.5, "reconsiders and keeps the cleanup coverage in this test, explaining the creation-to-deletion scenario is better covered by UT than E2E"),
    ("nature", "content", 0.5, "substantive rationale for test scope decision"),
])

out_path = "processed/tep135/classify_part3.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
