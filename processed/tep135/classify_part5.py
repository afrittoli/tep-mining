# processed/tep135/classify_part5.py
# Implementation PR pipeline#6892 "Update Affinity Assistant documentation" -- 41 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR = 6892

add(1248115160, "pipeline", PR, [
    ("artifact", "docs", 0.5, "```suggestion``` clarifying which modes are still under development"),
    ("nature", "content", 0.3, "clarifies feature-availability status in user docs"),
])
add(1248115649, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'Would it make sense to create a separate docs md file for the affinity assistant? it's a bit buried here'"),
    ("nature", "structure", 0.5, "documentation organization/placement"),
])
add(1248115922, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'worth noting that with this mode, you can only mount 1 pvc backed workspace to each taskrun'"),
    ("nature", "content", 0.6, "missing behavioral detail in the docs"),
])
add(1248116897, "pipeline", PR, [
    ("artifact", "docs", 0.7,
     "suggests rewriting to focus less on implementation details ('we really don't have to mention the affinity assistant at all')"),
    ("nature", "content", 0.7, "substantive reframing of the docs toward user-facing behavior over internals"),
])
add(1248117561, "pipeline", PR, [
    ("artifact", "docs", 0.5, "'should this be a description of the isolate-pipelineruns mode?' -- clarity question"),
    ("nature", "content", 0.4, "questions whether the text describes the right mode"),
])
add(1248118676, "pipeline", PR, [
    ("artifact", "docs", 0.5, "suggests including a linked proposal-PR writeup in addition to the table"),
    ("nature", "content", 0.4, "requests additional explanatory content"),
])
add(1248119158, "pipeline", PR, [
    ("artifact", "docs", 0.4, "'can you also link to affinity assistant docs here?'"),
    ("nature", "content", 0.3, "cross-link request between docs"),
])
add(1248159784, "pipeline", PR, [
    ("artifact", "docs", 0.3, "questions whether a separate docs file is really needed"),
    ("nature", "content", 0.3, "pushback on doc-file organization suggestion"),
])
# 1248159994 "Ahh sorry. Fix..." -- ack, zero-match
# 1248160167 "SGTM, added in the new file" -- ack, zero-match
# 1248160453 "Good catch, fixed." -- ack, zero-match
# 1248160654 "Sure, links added" -- ack, zero-match
# 1248161247 "Added a paragraph for it, PTAL" -- ack, zero-match
# 1248161421 "👍, I have rephrased the paragrah" -- ack, zero-match
# 1248161700 "👍. I have added a new file for affinity assistant" -- ack, zero-match
add(1248170092, "pipeline", PR, [
    ("artifact", "docs", 0.5, "```suggestion``` on deprecation wording for disable-affinity-assistant"),
    ("nature", "content", 0.4, "clarifies deprecation-related doc wording"),
    ("principle", "deprecation-handling", 0.4, "wording concerns the flag's future deprecation"),
])
add(1248170518, "pipeline", PR, [
    ("artifact", "docs", 0.6, "```suggestion``` rewriting user migration instructions in detail"),
    ("nature", "content", 0.5, "substantive rewrite of user-facing migration guidance"),
])
add(1248170895, "pipeline", PR, [
    ("artifact", "docs", 0.4, "'coscheduling = disabled is OK right?' -- doc accuracy check"),
    ("nature", "content", 0.4, "verifies a specific documented claim"),
])
add(1248171155, "pipeline", PR, [
    ("artifact", "docs", 0.5, "```suggestion``` on scale-recommendation wording"),
    ("nature", "content", 0.4, "clarifies a scale-related recommendation"),
])
add(1248172102, "pipeline", PR, [
    ("artifact", "docs", 0.4, "'nit: can you make sure to use consistent capitalization for PVC, PipelineRun, and TaskRun?'"),
    ("nature", "structure", 0.5, "capitalization consistency nit"),
    ("principle", "consistency-with-existing", 0.3, "consistent terminology capitalization"),
])
add(1248172618, "pipeline", PR, [
    ("artifact", "docs", 0.4, "clarifies the intended direction of a cross-link between two docs pages"),
    ("nature", "content", 0.3, "clarification of prior request"),
])
# 1248211097 "Oh sorry, just fixed" -- ack, zero-match
# 1248211637 "Updated" -- ack, zero-match
add(1248213278, "pipeline", PR, [
    ("artifact", "docs", 0.4, "clarifies a specific flag-combo case and why an explanatory note was kept minimal"),
    ("nature", "content", 0.4, "doc-accuracy clarification"),
])
add(1253237957, "pipeline", PR, [
    ("artifact", "docs", 0.7,
     "flags that non-functional modes are documented as if live on tekton.dev, suggests commenting out or moving to a contributor-focused README/godoc instead"),
    ("artifact", "incremental-delivery", 0.6, "concerns documentation marking partial/not-yet-functional capability as if complete"),
    ("nature", "content", 0.7, "substantive concern about publishing docs for non-functional user-facing behavior"),
])
add(1253246915, "pipeline", PR, [
    ("artifact", "docs", 0.6, "asks for a clearer explanation of what 'Incompatible' means between Affinity Assistants and PodTemplates"),
    ("nature", "content", 0.6, "substantive clarity gap about documented behavior"),
])
add(1253249355, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'How can I figure out if I previously accepted the default behavior?' -- unclear from a user's perspective"),
    ("nature", "content", 0.5, "user-facing clarity gap"),
])
add(1253253982, "pipeline", PR, [
    ("artifact", "docs", 0.5, "notes the flag names seem to conflict conceptually and suggests looking into renaming"),
    ("nature", "structure", 0.6, "flag-naming clarity concern"),
    ("principle", "consistency-with-existing", 0.4, "flag semantics appear to conflict with each other"),
])
add(1253262336, "pipeline", PR, [
    ("artifact", "docs", 0.6, "suggests making the warning more prominent (placement, emoji, bold) and classifying stability level per mode"),
    ("nature", "structure", 0.5, "visual prominence/formatting of a warning"),
    ("principle", "feature-graduation", 0.5,
     "'We should also try and classify all of these with their stability level to set expectations around breaking changes (by default users will assume stable)'"),
])
add(1253266236, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'This is the first mention of migration - when is this happening?'"),
    ("nature", "content", 0.5, "doc lacks context for a term introduced without explanation"),
])
add(1253269916, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'I don't know what this table is supposed to be telling me... Are these the config map values?'"),
    ("nature", "content", 0.6, "table lacks explanation for a first-time reader"),
])
add(1253273749, "pipeline", PR, [
    ("artifact", "docs", 0.6, "'Might be worth including the expected config map values somewhere and how they map to the modes above'"),
    ("nature", "content", 0.5, "missing mapping between config values and modes"),
])
add(1258758031, "pipeline", PR, [
    ("artifact", "docs", 0.5, "recaps the naming/default-value/migration discussion history for the reviewer"),
    ("nature", "content", 0.6, "substantive recap of prior design discussion"),
    ("principle", "feature-graduation", 0.5, "'This feature is added as an alpha feature, I think we can collect more user feedback before promoting it to beta'"),
])
add(1258932364, "pipeline", PR, [
    ("artifact", "incremental-delivery", 0.4, "proposes merging the docs PR only after the feature is fully implemented"),
    ("nature", "content", 0.3, "sequencing decision between docs and implementation completeness"),
])
add(1258933908, "pipeline", PR, [
    ("artifact", "docs", 0.5, "explains Affinity Assistant vs PodTemplate affinity precedence, with a code link"),
    ("nature", "content", 0.5, "substantive answer to the earlier 'incompatible' clarity gap"),
])
add(1258934354, "pipeline", PR, [
    ("artifact", "docs", 0.4, "updated the docs to show default configmap settings explicitly"),
    ("nature", "content", 0.4, "addresses the earlier table-clarity gap"),
])
add(1258934794, "pipeline", PR, [
    ("artifact", "docs", 0.4, "'Added 9 month deprecation time to this part'"),
    ("nature", "content", 0.4, "adds a concrete deprecation timeframe to the docs"),
    ("principle", "deprecation-handling", 0.5, "documents a specific 9-month deprecation window"),
])
# 1258935532 "switched the order of the chart and the notes... PTAL" -- minor reordering ack, zero-match
# 1258935636 "Please see the above comment" -- ack, zero-match
add(1258936287, "pipeline", PR, [
    ("artifact", "docs", 0.4, "commits to adding stability levels for different modes"),
    ("nature", "content", 0.4, "responds to the stability-level documentation request"),
    ("principle", "feature-graduation", 0.5, "agrees to document per-mode stability levels"),
])
add(1271113939, "pipeline", PR, [
    ("artifact", "docs", 0.6, "removes WIP warnings and holds the PR until the feature is fully implemented, adds per-mode stability levels including the alpha-feature list"),
    ("nature", "content", 0.6, "substantive update aligning docs with feature readiness"),
    ("principle", "feature-graduation", 0.6, "adds the feature to the documented alpha-feature list with stability levels"),
    ("artifact", "incremental-delivery", 0.4, "holds the docs PR until the underlying feature PR (#6927) is merged"),
])

out_path = "processed/tep135/classify_part5.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
