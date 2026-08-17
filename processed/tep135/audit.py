# processed/tep135/audit.py
# Targeted audit (large TEP, 330 comments): low-count-value sweep against
# processed/latest/comment_classifications.jsonl, focused re-read of comments
# whose topic plausibly matches those low-count values, plus a re-read of
# first-pass PR-scoping comments that turned out to have a better-fitting
# existing value than the one first-pass used.
#
# Low-count values checked (corpus-wide, before this TEP's rows):
#   feature-gate-registration: 9   reconciler-pattern: 14   release-notes: 4
#   crd-registration: 2   tep-staging: 2   resource-labeling: 1
#   container-image-config: 0   custom-cryptography: 0   conformance: 1
# TEP-135's own topic (per-feature-flag introduction in pipeline#6790, PVC
# finalizer/lifecycle management in pipeline#6893/#6940, e2e/integration test
# support in pipeline#6927) is a strong match for feature-gate-registration
# and reconciler-pattern specifically, so those two got a deliberate re-read
# of every comment in the relevant PRs, not just a keyword scan.
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


# --- feature-gate-registration: pipeline#6790 "Introduce coschedule feature flags" ---
# First pass tagged these with artifact:tests/docs + principle:api-compatibility, but
# missed that they're specifically checklist items from the feature-gate-registration
# value's own source doc (feature-versioning.md#adding-feature-gated-api-fields):
# unit tests for flag combos, configMap-entry docs, and docs updates for a new flag.
add(1222107970, "pipeline", 6790, [
    ("artifact", "feature-gate-registration", 0.5,
     "asks for a missing unit-test case covering a specific disable-affinity-assistant/coscheduling flag combination -- the unit-test step of introducing a new feature flag"),
])
add(1235176501, "pipeline", 6790, [
    ("artifact", "feature-gate-registration", 0.55,
     "clarifies unit tests should cover all 8 flag-combination cases and return an error for invalid ones -- directly the unit-test completeness requirement for a new feature flag"),
])
add(1232769942, "pipeline", 6790, [
    ("artifact", "feature-gate-registration", 0.5,
     "'Can you please also add some markdown docs explaining in more detail what this feature is' -- the docs-update step for a newly introduced feature flag"),
])
add(1222101161, "pipeline", 6790, [
    ("artifact", "feature-gate-registration", 0.45,
     "requests a proper docs section for the configuration options in config-feature-flags.yaml rather than just linking the TEP -- configMap-entry/docs step"),
])
add(1235178679, "pipeline", 6790, [
    ("artifact", "feature-gate-registration", 0.45,
     "confirms it's worth writing a dedicated docs section for the affinity-assistant feature flag specifically"),
])

# --- feature-gate-registration: pipeline#6927 e2e/integration-test support ---
add(1264195654, "pipeline", 6927, [
    ("artifact", "feature-gate-registration", 0.4,
     "asks how the new integration test for this feature avoids interfering with other integration tests -- the alpha/beta Prow-environment integration-test step"),
])
add(1264195892, "pipeline", 6927, [
    ("artifact", "feature-gate-registration", 0.35,
     "asks to use default-value variables instead of hard-coded values in the integration test for this feature flag, so default changes don't silently break test coverage"),
])
add(1270914312, "pipeline", 6927, [
    ("artifact", "feature-gate-registration", 0.5,
     "follows an existing project pattern (linked issue #6079) for setting/reverting feature flags and running integration tests for them sequentially"),
])

# --- reconciler-pattern: pipeline#6893 "Revert PVC creation" (finalizer vs owner-ref) ---
# First pass tagged these as generic artifact:code; re-read shows they're specifically
# about a reconciler/controller garbage-collection convention (finalizers vs Kubernetes
# owner references for cleanup), which is exactly what reconciler-pattern covers.
add(1248173867, "pipeline", 6893, [
    ("artifact", "reconciler-pattern", 0.5,
     "proposes a PipelineRun finalizer to delete affinity-assistant PVCs on deletion -- a reconciler/controller cleanup-pattern choice"),
])
add(1252172648, "pipeline", 6893, [
    ("artifact", "reconciler-pattern", 0.4,
     "explains the chosen approach relies on Kubernetes owner references so PVCs are auto-deleted when the owning PipelineRun is deleted, rather than manual API calls -- a controller garbage-collection convention"),
])
add(1253003193, "pipeline", 6893, [
    ("artifact", "reconciler-pattern", 0.5,
     "concludes finalizers don't have much advantage over owner references and carry more unknowns -- resolves the finalizer-vs-owner-reference reconciler-pattern choice"),
])

# --- reconciler-pattern: pipeline#6940 "Purge finalizer and delete PVC" ---
# The whole PR is centered on finalizer manipulation for PVC cleanup; first pass tagged
# these generically as artifact:code/tests and missed the reconciler-pattern angle.
add(1268159341, "pipeline", 6940, [
    ("artifact", "reconciler-pattern", 0.5,
     "asks for an explanation of why the pvc-protection finalizer is being purged, with a link to k8s finalizer docs -- a reconciler cleanup-pattern convention"),
])
add(1268162488, "pipeline", 6940, [
    ("artifact", "reconciler-pattern", 0.4,
     "suggests using the JSON-patch 'remove' operation instead of manually rewriting the finalizers list -- a finalizer-manipulation convention"),
])
add(1268520753, "pipeline", 6940, [
    ("artifact", "reconciler-pattern", 0.4,
     "investigates whether a k8s-defined finalizer constant can be imported, finding k8s.io/kubernetes isn't recommended to import directly -- finalizer-handling convention constraint"),
])
add(1268523384, "pipeline", 6940, [
    ("artifact", "reconciler-pattern", 0.4,
     "works through whether the finalizer's index is needed to remove it via JSON patch -- finalizer-manipulation mechanics"),
])
add(1268528336, "pipeline", 6940, [
    ("artifact", "reconciler-pattern", 0.45,
     "```suggestion``` clarifying comment on why the kubernetes.io/pvc-protection finalizer is purged to allow PVC deletion while still referenced by a taskrun pod"),
])

# --- pr-size: re-read of PR#6893's refactor-scoping thread ---
# First pass tagged these only as artifact:incremental-delivery (feature-flag/partial-
# functionality framing). Re-reading them fresh, they're not about splitting a feature
# behind a flag at all -- they're specifically about keeping *this* PR small and moving
# unrelated refactoring to a separate PR, which is pr-size's own definition
# ("refactoring separated from feature work"), and a better fit than incremental-delivery.
add(1254543235, "pipeline", 6893, [
    ("artifact", "pr-size", 0.5,
     "explicitly wants to keep this PR scoped to the minimal set of changes for the revert, suggesting the sketched refactor be split into a separate PR"),
])
add(1258422969, "pipeline", 6893, [
    ("artifact", "pr-size", 0.5,
     "'I have a strong preference that refactoring changes happen first... refactoring changes that get deferred to later just get deprioritized' -- concerned refactoring won't stay separated from feature work if deferred"),
])
add(1258658590, "pipeline", 6893, [
    ("artifact", "pr-size", 0.45,
     "argues merging this PR as-is (with refactoring tracked in a separate issue) keeps it reviewable and unblocks parallel followup work"),
])
add(1258400264, "pipeline", 6893, [
    ("artifact", "pr-size", 0.4,
     "agrees to put the refactoring in a separate PR specifically to keep this one scoped"),
])

# --- release-notes: very low corpus-wide count (4) ---
add(1231207597, "community", 1025, [
    ("artifact", "release-notes", 0.3,
     "'I find your phrasing really good and useful for docs and release notes' -- affirms the TEP wording's suitability for eventual release notes, though not a request for a change"),
])

out_path = "processed/tep135/audit.jsonl"
with open(out_path, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"wrote {len(rows)} audit rows")
