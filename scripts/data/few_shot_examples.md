# Worked examples

Example 1 - a comment with matches in multiple facets. Note that `evidence` is a tight
paraphrase of the specific part that justifies the match, never the whole comment copied
verbatim:

Comment: "This should handle `k8serrors.IsNotFound` as a no-op, in case we have dueling
deletes."

Good output:

```json
{"comment_id": 605675529, "matches": [
  {"facet": "artifact", "value": "reconciler-pattern", "confidence": 0.6,
   "evidence": "suggests handling k8serrors.IsNotFound as a no-op for the dueling-deletes case"},
  {"facet": "artifact", "value": "code", "confidence": 0.5,
   "evidence": "a correctness fix to the deletion error-handling code"},
  {"facet": "nature", "value": "content", "confidence": 0.55,
   "evidence": "substantive correctness suggestion, not a style nit"}
]}
```

Bad output (do not do this): `evidence: "This should handle k8serrors.IsNotFound as a no-op,
in case we have dueling deletes."` - this is the comment, not an analysis of it.

Example 2 - a comment with zero matches. This is the normal, expected outcome for most
comments, not a failure to find something:

Comment: "lgtm, thanks!"

Good output:

```json
{"comment_id": 999999001, "matches": []}
```

Do not invent a match just to produce output - an empty matches list is a complete,
correct answer here.

Example 3 - a comment where nothing in the taxonomy fits, so it goes to `candidates`
instead of being forced into an existing value:

Comment: "wdyt about setting DeleteOptions.Preconditions.UID to avoid possible mixups if
two runs end up having the same name?"

Good output:

```json
{"results": [{"comment_id": 999999002, "matches": [
    {"facet": "artifact", "value": "code", "confidence": 0.6,
     "evidence": "suggests a UID precondition to avoid deleting the wrong object on a name collision"}
]}],
"candidates": [{"comment_id": 999999002,
    "fragment": "avoid possible mixups if two runs end up having the same name",
    "candidate_facet": "principle",
    "candidate_value": "concurrency-safety",
    "candidate_description": "Whether code defends against races between concurrent operations rather than assuming single-actor execution."}]}
```

Note this comment gets BOTH a normal match (the code-level suggestion) AND a candidate
(the underlying principle nothing in the taxonomy names yet) - the two are not exclusive.
