# processed/tep135/classify_part1.py
# Proposal PR comments (community#1017, #1025) -- 38 comments total.
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


# --- community#1017 ---
add(1183613063, "community", 1017, [
    ("principle", "feature-justification", 0.4,
     "'Any reason to tackle this one right now ? (aka I see less use-case than the one above)' -- questions whether this configuration is needed now"),
    ("artifact", "tep-body", 0.5, "questioning scope of a proposed configuration option in the TEP"),
])
# 1183613197 "👍🏼" -- pure emoji ack, zero-match
add(1183614189, "community", 1017, [
    ("artifact", "tep-body", 0.6, "asks whether 'affinity-assistant' terminology should still be used given it disappears elsewhere for 'coscheduling'"),
    ("nature", "content", 0.5, "terminology/naming consistency question about the TEP text"),
    ("principle", "consistency-with-existing", 0.4, "flags inconsistent terminology within the same document"),
])
add(1183616080, "community", 1017, [
    ("artifact", "tep-body", 0.7,
     "raises a design robustness concern: heavy load (20 PipelineRuns/min) with few nodes (5-6) would cause timeouts"),
    ("nature", "content", 0.6, "substantive scaling/robustness concern about the proposed design"),
])
# 1183618383 "Do we have an issue to track this ?" -- procedural coordination, zero-match
add(1183649478, "community", 1017, [
    ("artifact", "tep-body", 0.5, "responds to the terminology/label concern, explains placeholder pod is an implementation detail"),
    ("nature", "content", 0.5, "explains rationale for keeping existing labels"),
    ("principle", "consistency-with-existing", 0.4, "argues for keeping existing labels rather than introducing new ones"),
])
# 1183649822 "yup it's in the previous paragraph!" -- pointer/ack, zero-match
add(1183659007, "community", 1017, [
    ("artifact", "tep-body", 0.6,
     "explains which cluster-operator scenario (autoscaler + many nodes) the coschedule-pipelineruns option targets, responding to the timeout concern"),
    ("nature", "content", 0.6, "substantive design rationale for a configuration option"),
])
add(1183699367, "community", 1017, [
    ("artifact", "tep-body", 0.5, "justifies including the isolation config option in the initial implementation given low effort"),
    ("nature", "content", 0.5, "substantive scoping rationale"),
    ("principle", "feature-justification", 0.4, "argues the configuration option is worth including now"),
])
# 1183881621 "Fair" -- pure ack, zero-match
add(1184065721, "community", 1017, [
    ("artifact", "tep-body", 0.6,
     "notes the isolation mode assumes a cluster that can autoscale nodes, suggests documenting that assumption"),
    ("nature", "content", 0.6, "flags a missing assumption that should be documented"),
])

# --- community#1025 ---
add(1224479864, "community", 1025, [
    ("artifact", "tep-body", 0.6, "```suggestion``` rewording the chart's introductory sentence"),
    ("nature", "content", 0.5, "clarifies which flag combination the chart is summarizing"),
])
add(1224481087, "community", 1025, [
    ("artifact", "tep-body", 0.6, "'I think it's worth noting that we may want to consider making \"coschedule-pipelineruns\" the default value in the future'"),
    ("nature", "content", 0.6, "substantive design note about future default value"),
])
add(1224482049, "community", 1025, [
    ("artifact", "tep-body", 0.7,
     "'Another con of this alternative is that it's not clear what the behavior should be if...' -- flags an ambiguity/gap in the design table"),
    ("nature", "content", 0.6, "identifies unspecified behavior in the proposed design"),
])
# 1226653458 / 1226653845 / 1226654143 "Updated!" x3 -- acks, zero-match
add(1227749034, "community", 1025, [
    ("artifact", "tep-body", 0.7,
     "'I was expecting this to be \"N/A: invalid\" like in the flip case of AA enabled and coschedule disabled' -- argues the flag-interaction table is asymmetric/inconsistent"),
    ("nature", "content", 0.7, "substantive design consistency argument about the flag-interaction matrix"),
    ("principle", "consistency-with-existing", 0.5, "expects symmetric handling of the flag combination given the flipped case"),
])
add(1227751327, "community", 1025, [
    ("artifact", "tep-body", 0.6, "'Why is it that a v1.0 release could shorten the deprecation timeframe for the flag?'"),
    ("nature", "content", 0.6, "questions the deprecation-timeline rationale"),
    ("principle", "deprecation-handling", 0.6, "directly questions the flag's deprecation timeframe"),
])
add(1228152985, "community", 1025, [
    ("artifact", "tep-body", 0.6, "explains the backward-compatibility rationale for the default behavior during migration"),
    ("nature", "content", 0.6, "substantive backward-compatibility explanation"),
    ("principle", "api-compatibility", 0.7,
     "'If it is \"N/A: invalid\", it is a violation of backward compatibility for users disable AA today'"),
])
# 1228155427 "@lbernick, could you please help give more insights about v1.0 release?" -- forwards a question, zero-match
add(1228172719, "community", 1025, [
    ("artifact", "tep-body", 0.6, "long explanation of semver reasoning for backward-incompatible changes and the v1.0 boundary"),
    ("nature", "content", 0.7, "detailed substantive reasoning about semver and API stability guarantees"),
    ("principle", "api-compatibility", 0.8,
     "explicit discussion of semver.org's backward-compatibility guarantees before/after v1.0.0"),
    ("principle", "deprecation-handling", 0.5, "concludes the flag should be removed after an appropriate deprecation period"),
])
add(1230101967, "community", 1025, [
    ("artifact", "tep-body", 0.7, "proposes a simpler flag-interaction matrix, fearing the current one is confusing"),
    ("nature", "content", 0.7, "substantive alternative design proposal"),
    ("principle", "simplicity", 0.7, "'A simpler matrix could be as follows' -- explicitly argues for a simpler alternative"),
])
add(1230168276, "community", 1025, [
    ("artifact", "tep-body", 0.6, "endorses the simpler alternative design and links a shared doc with the reworked chart"),
    ("nature", "content", 0.6, "substantive design discussion, comparing two proposals"),
    ("principle", "simplicity", 0.4, "'I actually perfer this way of thinking better!' -- prefers the simpler framing"),
])
add(1230693796, "community", 1025, [
    ("artifact", "tep-body", 0.4, "follow-up noting the '1.0 part' text is still present despite the thread being marked resolved"),
    ("nature", "content", 0.3, "flags outstanding TEP text that needs updating"),
])
add(1231018163, "community", 1025, [
    ("artifact", "tep-body", 0.7, "rephrases the chart in terms of user actions, comparing both proposed matrices in detail"),
    ("nature", "content", 0.7, "substantive comparison of two competing designs from a user-action perspective"),
    ("principle", "simplicity", 0.5, "'I personally find Quan's original proposal less confusing' -- weighs which is simpler for users"),
])
# 1231207597 "Sounds good... It's ok for me to keep the current plan." -- mostly agreement/close-out, zero-match
# 1231222492 "Thanks for your inputs!... can you approve this PR" -- mostly procedural close-out, zero-match
add(1231236770, "community", 1025, [
    ("artifact", "tep-body", 0.6, "raises naming concern about the 'coscheduling' flag name and its values, proposes 'coexist' alternative"),
    ("nature", "structure", 0.5, "naming/labeling concern rather than functional substance"),
    ("principle", "consistency-with-existing", 0.4, "notes most values start with 'coschedule-' prefix while the flag itself doesn't match"),
])
# 1231255456 "Sorry, I missed this part, I have cleaned up the 1.0 stuff" -- ack/fix confirmation, zero-match
add(1231274942, "community", 1025, [
    ("artifact", "tep-body", 0.5, "continues the naming discussion, weighs how 'coexist'+'all-pipelineruns' could be misread"),
    ("nature", "structure", 0.5, "naming-clarity concern"),
])
add(1231296806, "community", 1025, [
    ("artifact", "tep-body", 0.5, "proposes a flag/value naming scheme that avoids repeating 'coschedule'"),
    ("nature", "structure", 0.6, "naming suggestion to reduce redundancy"),
    ("principle", "simplicity", 0.4, "avoiding repetition in flag/value naming"),
])
# 1231298319 "wouldn't mind agreeing on the final naming on the implementation PR" -- procedural deferral, zero-match
add(1231313015, "community", 1025, [
    ("artifact", "tep-body", 0.5, "'maybe pipelineruns instead of pipelines' -- naming precision suggestion"),
    ("nature", "structure", 0.5, "naming precision suggestion"),
])
add(1231365027, "community", 1025, [
    ("artifact", "tep-staging", 0.5,
     "proposes merging the TEP as-is and deferring the naming discussion to the implementation PR"),
    ("nature", "content", 0.3, "defers a design detail to a follow-up PR to keep the TEP moving"),
])
add(1231464006, "community", 1025, [
    ("artifact", "tep-body", 0.4, "expresses concern the naming discussion not be forgotten, given reliance on the existing feature flag"),
    ("nature", "content", 0.4, "flag-transition/migration concern"),
    ("principle", "deprecation-handling", 0.35, "concern about a smooth transition for cluster operators relying on the existing flag"),
])
# 1231472484 "we can move the discussion on the naming to here [link]" -- procedural redirect, zero-match
# 1231560035 "can I mark this thread as resolved for now?" -- procedural, zero-match

out_path = "processed/tep135/classify_part1.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
