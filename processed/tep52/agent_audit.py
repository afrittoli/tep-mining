# processed/tep52/audit.py
# Exhaustive re-read audit for TEP-52 (small TEP, full re-read used per the
# documented ideal rather than the targeted-audit shortcut for large TEPs).
#
# Deliberately checked for security / crd-version-policy / deprecation-handling /
# feature-graduation given the TEP's cleanup/deletion topic: grepped the full
# comment text for flag|alpha|beta|opt-in|default|deprecat|version|backward|
# compat|security|attack|threat|conform|graduat and re-read every hit in context.
# No genuine matches found for any of those four values in this TEP's comments -
# an honest zero, not a gap in reading. Two other real misses were found instead.

import json

rows = []


def add(comment_id, repo, pr_number, tags):
    """tags: list of (facet, value, confidence, evidence) - same shape as classify.py"""
    for facet, value, confidence, evidence in tags:
        rows.append({
            "repo": repo, "pr_number": pr_number, "comment_id": comment_id,
            "facet": facet, "value": value, "confidence": confidence,
            "evidence": evidence, "source_pass": "audit",
        })


# Missed match 1: community#347, 581417527 (bobcatfish) was tagged tep-body/content
# on first pass, but the second half of the comment - "i could imagine folks might
# be using other tools that might integrate with the k8s API and it might not be
# reasonable to expect they can update those tools to use the Result API as the
# source of truth" - is a genuine api-compatibility concern (external consumers
# relying on k8s API objects persisting), not just a design-clarification question.
add(581417527, "community", 347, [
    ("principle", "api-compatibility", 0.5,
     "raises that external tools integrating via the k8s API may not be able to "
     "switch to the Results API as source of truth once completed Runs are deleted "
     "- a backward-compatibility concern for existing consumers"),
])

# Missed match 2: results#103, 605675061 (imjasonh) was tagged reconciler-pattern/
# content on first pass. Re-read: "Any reason to prefer EnqueueKeyAfter instead of
# EnqueueAfter which can just take the whole object?" is not just an API-usage
# question, it's explicitly questioning whether a more roundabout mechanism was
# chosen over the simpler one that does the same job - a simplicity-principle match.
add(605675061, "results", 103, [
    ("principle", "simplicity", 0.45,
     "questions why the more roundabout EnqueueKeyAfter was used instead of "
     "EnqueueAfter, which 'can just take the whole object' directly"),
])

out_path = "processed/tep52/audit.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"wrote {len(rows)} audit rows")
