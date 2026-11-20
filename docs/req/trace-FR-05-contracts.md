# Trace — FR-05 contracts (test-first spec)

Requirement-to-test trace for the `RunEvent` and `ExperimentManifest` contracts.
This is the **spec/test** artifact only. Implementation is delivered separately in
an implementation PR that must descend from this spec's merge commit (ancestry
verified as CI/hand evidence there).

Related records:
- **PR #1** (original development record, retained as-is, Draft, changes requested): GATE-01 ordering defect (impl `fff66d0` before tests `7df4489`).
- **DEBT-D2** (in `docs/debt-register.md` on PR #1's branch): GATE-01 process debt; closes when this spec is approved and a descendant implementation PR lands.

## What this branch is / is not

- **Is**: tests + requirement trace only (`test/offline/contracts/*`, this file, `docs/approvals/`, `docs/ai-use-log.yaml`).
- **Is not**: no `src/egta/contracts/` implementation here.
- **RED by design**: with no `src/`, both `pytest test/offline/contracts` and
  `pytest --collect-only test/offline/contracts` fail at **import**
  (`ModuleNotFoundError: egta.contracts`). `--collect-only` does NOT prove
  collectability here (collection imports the modules). The test-first signal is
  the red, not a green.
- A syntax/AST check (e.g. `python -m py_compile` + AST count of `test_*`
  functions) is the proposed CI proof that the spec is well-formed while red is
  expected. (CI wiring itself is a D+E joint task; see PR body "Batch B".)

## Test function → requirement mapping

Legend: **E** = existing (present since `7df4489`), **N** = newly added this round
(Batch A). "Dependency" notes where a test is expected RED until B/D decisions or
implementation land.

### `test/offline/contracts/test_events.py`

| Test function | Kind | Covers | Notes |
|---|---|---|---|
| `test_verify_chain_helper_is_not_vacuous` | E | NFR-08 | self-check: verifier accepts good, rejects broken |
| `test_run_event_constructs` | E | FR-05, NFR-09 | fields incl. `metrics` |
| `test_reason_code_accepts_canonical_value` | E | NFR-09 | canonical reason_code |
| `test_payload_hash_must_be_64_lowercase_hex` | E | FR-05, NFR-08 | hex format |
| `test_prev_event_hash_must_be_empty_or_64_lowercase_hex` | E | FR-05, NFR-08 | prev link format |
| `test_prev_event_hash_may_be_empty_for_first_event` | E | FR-05 | genesis event |
| `test_naive_timestamp_rejected` | E | NFR-09 | tz required |
| `test_aware_timestamp_normalized_to_utc` | E | NFR-09 | UTC normalization |
| `test_extra_field_forbidden` | E | FR-05 | `extra=forbid` |
| `test_illegal_reason_code_rejected` | E | NFR-09 | enum strictness |
| `test_hash_chain_links_and_tamper_breaks_it` | E (fixed) | FR-05, NFR-08 | **D.8 fix**: ev2 hashes its OWN content (incl. real prev link) |
| `test_recomputed_payload_hash_mismatch_is_rejected` | **N** | FR-05, NFR-08 | **payload binding**: content changed w/o hash update -> reject |
| `test_sequence_gap_is_rejected` | **N** | FR-05, NFR-08 | events [0,2] -> `ChainBroken` |
| `test_duplicate_event_id_conflict_is_rejected` | **N** | FR-05 | same id, diff content -> `DuplicateConflict` |
| `test_identical_duplicate_event_id_is_deduped_once` | **N** | FR-05, NFR-09 | identical dup collapses once |

`ChainBroken` / `DuplicateConflict` / `PayloadMismatch` are **test-local helper
exceptions**; their public placement/signature is **pending D confirmation**
(D.9). Marked "await confirmation from D on public contract".

### `test/offline/contracts/test_manifest.py`

| Test function | Kind | Covers | Notes |
|---|---|---|---|
| `test_manifest_with_all_four_variants_constructs` | E→N | FR-05, NFR-08 | **B decision**: B0/B1/B2/B3 all present |
| `test_missing_any_variant_rejected` | **N** | FR-05, NFR-08 | dependency not yet implemented (B: all four mandatory) |
| `test_empty_b0_rejected_by_validator` | E (adj) | FR-05 | validator branch (empty B0 falsy) |
| `test_bad_model_config_hash_rejected` | E | FR-05, NFR-08 | hash format |
| `test_bad_prompt_hash_rejected` | E | FR-05, NFR-08 | hash format |
| `test_naive_created_at_rejected` | E | NFR-09 | tz required |
| `test_empty_metrics_rubric_rejected` | **N** | FR-05 | dependency not yet implemented (typed rubric) |
| `test_non_dict_metrics_rubric_rejected` | E→N | FR-05 | mapping type guard |
| `test_metric_def_missing_required_field_rejected` | **N** | FR-05 | **B MetricDef**: metric/operator/threshold/verification/source/aggregation/unit mandatory |
| `test_quality_rubric_requires_three_levels_and_adjudication` | **N** | FR-05 | **B QualityRubric**: three levels/double-blind/adjudication/LLM-judge |

### `test/offline/contracts/test_metrics_serialization.py`

| Test function | Kind | Covers | Notes |
|---|---|---|---|
| `test_nan_metric_serializes_to_null_defect` | **N** | NFR-08, NFR-09 | **DEFECT**: NaN silently -> JSON null (data loss) |
| `test_inf_metric_serializes_to_null_defect` | **N** | NFR-08, NFR-09 | **DEFECT**: inf -> null |
| `test_non_serializable_metric_fails_at_serialization` | **N** | NFR-08 | non-JSON object: late failure at dump |
| `test_json_safe_metrics_roundtrip` | **N** | NFR-08 | positive roundtrip |
| `test_validation_error_type_is_pydantic` | **N** | NFR-09 | guard on error type |

## Negative cases covered by this round (Batch A)

- payload tampering / recompute mismatch -> reject (payload binding)
- sequence gap `[0,2]` -> `ChainBroken`
- duplicate `event_id` (conflict vs identical)
- non-JSON / NaN / non-finite metrics -> current behavior pinned + DEFECT flagged
- (Batch B, pending D): replay determinism, tail truncation with anchor, incompatible experiment configuration, illegal variant/rubric

## Approval

- Approval authority: **D (@ZFebron491001)** under GATE-01; author does not self-review.
- Approval binds to test content hash + final reviewed PR head + (post-approval) merge commit; see `docs/approvals/test-hash-FR-05-contracts.txt`.
- Do not push changes to the approval/hash fields after D's approval (stale-approval trap).
