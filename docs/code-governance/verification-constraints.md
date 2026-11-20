# Verification Constraints

# Implements: FR-05, NFR-08, NFR-09

## Failure-sample accounting (E1 / FR-05)

### Principle
Missing, failing, or rejected runs are recorded, never deleted. Deletion or
silent omission of a failure sample is itself a defect (GATE-05: failing evidence
may not be removed to make a check pass).

### Run states and the success denominator
Each case is classified into exactly one terminal state:

| State | Meaning | Counts in success-rate denominator? |
|---|---|---|
| `OK` | Run completed and produced a rating/decision | **Yes** (numerator if correct, else miss) |
| `HOLD` | Valid "do not trade" decision | **Yes** — treat as a normal outcome, not as success/failure by itself |
| `BLOCKED` | System refused by policy (risk gate, evidence, invalid output) | **No** |
| `INCOMPLETE` | Budget/deadline/provider shortage cut the run short | **No** |
| `REVIEW` | Insufficient/unparseable evidence or rating; needs human review | **No** |
| `FAILED` | Unexpected error/crash | **No** (reported separately as reliability events) |

- `BLOCKED`, `INCOMPLETE`, `REVIEW`, and `FAILED` **do not enter the success-rate
  denominator**. They are reported as their own counts and rates so a run cannot
  inflate success by being blocked, nor be hidden by being excluded.
- The denominator for **success rate** is therefore `|OK| + |HOLD|` per variant
  per case set. Pair reports must state numerator, denominator, and every
  excluded count explicitly.

### Missing comparison results
If any required variant/result for a pair is `INCOMPLETE`, `BLOCKED`, `REVIEW`,
or `FAILED`, the pair is marked **`incomplete`** — it is **not** a win for any
variant and is excluded from win-rate denominators, while still listed.

### No deletion / no survivorship bias
- Raw events, run records, and failure logs are append-only evidence; nothing is
  pruned to improve metrics.
- Ablation and baseline arms are counted on the **same** case set; a case lost by
  one arm cannot be dropped from another's results.
- Every aggregate reports total attempted, per-state counts, and excluded
  samples, so excluded failures remain visible.

### Evidence
Per-case records carry `run_id`, `variant`, `state`, `reason_code` (for
non-OK), so a reader can reconstruct the excluded set. This aligns with
NFR-09 (observability) and NFR-08 (reproducibility).
