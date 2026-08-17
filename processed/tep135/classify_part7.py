# processed/tep135/classify_part7.py
# Implementation PR pipeline#6921 "Refactor CreatePVCsForWorkspaces" -- 20 comments.
import json

rows = []


def add(comment_id, repo, pr_number, tags):
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence,
        })


PR = 6921

add(1261638785, "pipeline", PR, [
    ("artifact", "code", 0.6, "'Rather than separating the error and the reason for the error, why not use sentinel errors?' with a Go blog link and example"),
    ("nature", "content", 0.5, "substantive suggestion to use a standard Go error-handling pattern"),
    ("nature", "structure", 0.3, "error-representation convention"),
])
add(1261640051, "pipeline", PR, [
    ("artifact", "code", 0.6, "suggests CreatePVCFromVolumeClaimTemplate return the created PVC directly instead of rebuilding a PersistentVolumeClaimVolumeSource"),
    ("nature", "content", 0.5, "substantive API-shape suggestion between two functions"),
])
add(1261640638, "pipeline", PR, [
    ("artifact", "code", 0.5, "'I don't think it's necessary to use errorutils.NewAggregate for only a single err'"),
    ("nature", "content", 0.4, "questions unnecessary use of an aggregation utility"),
    ("principle", "simplicity", 0.3, "avoiding an unneeded abstraction for a single error"),
])
add(1261642013, "pipeline", PR, [
    ("artifact", "code", 0.5, "'I'm confused about this sentence; is this meant as an explanation of why we pass the created PVCs... instead of the volumeclaimtemplates?'"),
    ("nature", "content", 0.5, "flags an unclear explanatory comment"),
])
add(1261644978, "pipeline", PR, [
    ("artifact", "code", 0.5, "'can this conditional logic be simplified?'"),
    ("nature", "content", 0.4, "asks to simplify conditional logic"),
    ("principle", "simplicity", 0.4, "explicit simplification request"),
])
add(1261646753, "pipeline", PR, [
    ("artifact", "code", 0.4, "'maybe a better name for this function could be \"GeneratePVCNameFromWorkspaceBinding\"?'"),
    ("nature", "structure", 0.5, "function-naming suggestion"),
])
add(1261692787, "pipeline", PR, [
    ("artifact", "code", 0.4, "pushes back: 'is there any difference? I personally don't find it hard to read'"),
    ("nature", "content", 0.4, "disagreement about whether the current form is unclear"),
])
add(1264185432, "pipeline", PR, [
    ("artifact", "code", 0.6,
     "detailed confusion about why only claimTemplate.Name is passed rather than the full PVC spec, suggests the function take a list of pvc names instead"),
    ("nature", "content", 0.5, "substantive API-clarity concern"),
])
add(1272747508, "pipeline", PR, [
    ("artifact", "code", 0.5, "confirms investigation that only the claim name is needed and refactors accordingly"),
    ("nature", "content", 0.5, "substantive resolution of the earlier API-clarity concern"),
])
# 1272751640 "Thanks for the suggestion! Changed to sentinel error (this part overlaps with #6927)!" -- routine fix confirmation, zero-match
# 1272752338 "Yeah you are right. I rephrased this comment and the comment below, hoping it is less confusing now." -- routine fix, zero-match
add(1272752834, "pipeline", PR, [
    ("artifact", "code", 0.3, "'I refactored this part a bit. It is not really simplified but I found it is easier to read for me'"),
    ("nature", "content", 0.3, "light rationale for a readability-motivated refactor"),
])
# 1272752952 "SGTM, function name changed" -- ack, zero-match
# 1272753592 "This test is copied from #6927" -- attribution note, zero-match
# 1272753973 "This part is copied from #6927" -- attribution note, zero-match
# 1272756888 "Changed to sentinel error" -- ack, zero-match
add(1272817148, "pipeline", PR, [
    ("artifact", "code", 0.5, "'nit: I suggest if len(claimNames) != 0 ... since what you have here differentiates between a nil slice and empty slice which I don't think is intentional'"),
    ("nature", "structure", 0.4, "nil-vs-empty-slice convention nit"),
    ("nature", "content", 0.3, "flags likely-unintentional behavior difference"),
])
add(1272820715, "pipeline", PR, [
    ("artifact", "code", 0.5, "'nit: this log is misleading since this function doesn't create PVCs; can you rephrase or remove?'"),
    ("nature", "content", 0.5, "flags a misleading log message"),
])
# 1273643366 "Thanks, fixed" -- ack, zero-match
# 1273643423 "Removed" -- ack, zero-match

out_path = "processed/tep135/classify_part7.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
comments = set((r["repo"], r["pr_number"], r["comment_id"]) for r in rows)
print(f"wrote {len(rows)} rows across {len(comments)} comments to {out_path}")
