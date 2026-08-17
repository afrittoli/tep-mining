# processed/tep118/audit.py
#
# Targeted audit (per "Scoping the audit at scale" in prompts/classify_review_comments.md):
# for a TEP this size (315 comments), used the low-count-value grep sweep plus a re-read of
# comments flagged to itself during first pass as touching design-constraint / API-evolution
# language, rather than an exhaustive re-read of all 239 tagged comments.
#
# Low-count-value sweep (grep -c against processed/latest/comment_classifications.jsonl):
# checked conformance (1), custom-cryptography (0), authoring-vs-runtime (11),
# feature-justification (7), security/supply-chain-compliance/deprecation-handling,
# container-image-config (0), resource-labeling (1), approval-process (2), tep-staging (2),
# functionality (4), release-notes (4) - keyword search (backward/compat/breaking/deprecat/
# security/crypto/conformance/runtime/release notes/resource label/container image/approv/
# staging/functionality) across the full comment corpus for this TEP found no real, honest
# matches beyond what first pass already captured. This TEP's comments are almost entirely
# either fan-out/validation code review or matrix.md doc review, not TEP-process or security
# topics, so a zero finding for those values here is expected, not a miss.
#
# crd-version-policy (22 in corpus before this TEP) and feature-graduation (74 before) both
# already got solid real representation from first-pass classification (9 and 4 rows
# respectively) - this TEP's dual v1/v1beta1 implementation and "preview mode" -> "alpha
# feature" terminology debate are a good natural source for both, as expected going in.
#
# Genuine audit finding: re-reading the "we don't yet support X, but plan to Y" design-scope
# comments turned up a real missed principle - api-compatibility (0 rows in the corpus before
# this TEP) - which first pass missed because it tagged these purely as
# artifact:code/incremental-delivery without registering the additive-capability-roadmap
# framing as an API-compatibility-policy concern in its own right.
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


add(1134209688, "pipeline", 6345, [
    ("principle", "api-compatibility", 0.45,
     "explains matrix.params doesn't yet support array results and matrix.include.params is "
     "string-only by design ('we do not yet (but want to) support array results in "
     "matrix.params'); frames the current restriction as a deliberate, conservative starting "
     "point with room to grow additively, not a permanent limitation - an additive-capability "
     "roadmap statement, which is what the API compatibility policy is about"),
])
add(1136999471, "pipeline", 6345, [
    ("principle", "api-compatibility", 0.4,
     "suggested code comment 'Only string replacements ... are supported. We plan to support "
     "array replacements from array results soon (#5925)' documents today's supported surface "
     "as a subset with a named follow-up issue for additive expansion later"),
])

out_path = "processed/tep118/audit.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"wrote {len(rows)} audit rows")
