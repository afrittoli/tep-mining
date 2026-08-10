# Sub-Task 8 classification cost log

Tracks the volume processed per TEP so we can reason about whether the AI-classification
approach stays cost-viable as we scale toward full corpus coverage, and compare against a
traditional-ML alternative if this ever gets expensive enough to matter.

This session has no tool access to its own token/dollar usage, so the columns below are a
proxy (comment count and comment-body character count, which is most of the input token cost)
rather than an authoritative `$` figure. To get real dollar figures, run Claude Code's `/cost`
command at TEP boundaries and record the delta in the "session $ (from /cost)" column — that
turns this proxy into a real $/comment rate over time.

Log starts at TEP-84; TEP-33 and TEP-29 predate this tracking and aren't backfilled.

| TEP | repo | comments (total) | comments classified (non-zero) | first-pass rows | audit rows | comment-body chars | passes | session $ (from /cost) |
|---|---|---|---|---|---|---|---|---|
| TEP-84 | chains | 178 | 138 | 336 | 19 | 40,395 | first-pass + audit | - |
| TEP-109 | chains | 172 | 151 | 374 | 1 | 35,111 | first-pass + audit | - |
| TEP-9 | triggers | 128 | 107 | 253 | 7 | 21,474 | first-pass + audit | - |
| TEP-26 | triggers | 123 | 107 | 267 | 0 | 26,762 | first-pass + audit | - |
