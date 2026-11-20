# Trace — FR-05 contracts (test-first spec)

Requirement-to-test trace for the FR-05 contracts. **Spec/test only.** The
implementation (`src/egta/contracts/{events,audit,evaluation,manifest}.py`) is
delivered in an implementation PR that must descend from this spec's merge commit
(ancestry verified as CI/hand evidence there).

Public contract definitions: `docs/req/contracts-summary.md`.
Related: **PR #1** (original development record; DEBT-D2 = GATE-01 process debt).

**Status:** 7 test files, **60 test functions → 90 cases**. On this branch the
imports of `egta.contracts.audit` / `egta.contracts.evaluation` fail
(`ModuleNotFoundError`) = **RED by design**. `--collect-only` is NOT a valid green
proof here (collection imports modules); CI uses `py_compile` + an AST check +
`@pytest.mark.spec` (registered in `pyproject.toml`).

## Test function → requirement mapping

Legend: **E** existing, **N** new this round, **fx** fixed this round. "RED-dep"
= expected RED until a specific unimplemented contract lands.

### `test_events.py` (16) — RunEvent + public audit helpers
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_run_event_constructs` | E | FR-05, NFR-09 | fields incl. metrics |
| `test_reason_code_accepts_canonical_value` | E | NFR-09 | reason_code |
| `test_payload_hash_must_be_64_lowercase_hex` | E | FR-05, NFR-08 | format |
| `test_prev_event_hash_must_be_empty_or_64_lowercase_hex` | E | FR-05, NFR-08 | prev format |
| `test_prev_event_hash_may_be_empty_for_first_event` | E | FR-05 | genesis |
| `test_naive_timestamp_rejected` | E | NFR-09 | tz required |
| `test_aware_timestamp_normalized_to_utc` | E | NFR-09 | UTC |
| `test_extra_field_forbidden` | E | FR-05 | extra=forbid |
| `test_illegal_reason_code_rejected` | E | NFR-09 | enum |
| `test_recompute_payload_hash_is_deterministic` | N | FR-05, NFR-08 | canonical digest |
| `test_verify_payload_rejects_recomputed_mismatch` | N fx | FR-05, NFR-08 | payload binding (D.8) |
| `test_hash_chain_links_and_tamper_breaks_it` | E fx | FR-05, NFR-08 | tamper -> PayloadMismatch |
| `test_chain_link_break_is_chainbroken` | N | FR-05, NFR-08 | link break -> ChainBroken |
| `test_sequence_gap_is_chainbroken` | N | FR-05, NFR-08 | [0,2] -> ChainBroken |
| `test_dedupe_identical_events_collapses_once` | N | FR-05 | dedupe_events |
| `test_dedupe_conflicting_event_id_raises` | N | FR-05 | DuplicateConflict |

### `test_audit.py` (14) — public audit contract
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_audit_public_protocols_importable` | N | FR-05 | AuditSink/AuditReader |
| `test_exceptions_share_base` | N | FR-05 | AuditContractError base |
| `test_chainbroken_signature` | N | FR-05, NFR-09 | (run_id, expected, actual, reason) |
| `test_duplicateconflict_signature` | N | FR-05 | (run_id, event_id, existing, incoming) |
| `test_payloadmismatch_signature` | N | FR-05 | (run_id, event_id, stored, recomputed) |
| `test_auditunavailable_signature` | N | FR-05 | (run_id, operation, cause) |
| `test_receipt_has_exactly_twelve_fields` | N | NFR-09 | D's 12 fields |
| `test_receipt_rejects_extra_field` | N | NFR-09 | extra=forbid |
| `test_full_chain_with_correct_anchor_passes` | N | NFR-08 | anchor ok |
| `test_tail_truncation_detected_with_anchor` | N | NFR-08 | tail truncation |
| `test_audit_sink_same_id_same_content_returns_existing_receipt` | N | FR-05, NFR-09 | idempotent |
| `test_audit_sink_same_id_diff_content_rejected` | N | FR-05 | DuplicateConflict |
| `test_audit_sink_append_is_idempotent` | N | FR-05, NFR-09 | idempotency |
| `test_audit_sink_read_returns_events_in_order` | N | NFR-09 | AuditReader.read |

### `test_metrics_serialization.py` (5)
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_non_finite_metric_rejected` [nan/inf/-inf] | N | NFR-08 | reject at construction |
| `test_non_json_object_metric_rejected` | N | NFR-08 | reject at construction |
| `test_nested_non_finite_metric_rejected` | N | NFR-08 | nested NaN |
| `test_json_safe_metrics_roundtrip` | N | NFR-08 | positive |
| `test_validation_error_type_is_pydantic` | N | NFR-09 | error type guard |

### `test_manifest.py` (15) — B's decisions
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_manifest_with_all_four_variants_constructs` | N | FR-05, NFR-08 | B0-B3 |
| `test_non_empty_b1_b2_b3_positive` | N | FR-05 | non-empty B1-B3 |
| `test_missing_any_variant_rejected` [B0-B3] | N | FR-05 | RED-dep: four mandatory |
| `test_unknown_variant_key_rejected` | N | FR-05 | RED-dep: reject B9 |
| `test_empty_b0_rejected_by_validator` | E | FR-05 | empty B0 |
| `test_bad_model_config_hash_rejected` | E | FR-05, NFR-08 | hash format |
| `test_bad_prompt_hash_rejected` | E | FR-05, NFR-08 | hash format |
| `test_naive_created_at_rejected` | E | NFR-09 | tz |
| `test_empty_metrics_rubric_rejected` | N | FR-05 | RED-dep: typed rubric |
| `test_non_dict_metrics_rubric_rejected` | E | FR-05 | mapping |
| `test_metric_def_missing_required_field_rejected` [7] | N | FR-05 | RED-dep: MetricDef 7 fields |
| `test_quality_rubric_positive` | N | FR-05 | quality_rubric positive |
| `test_quality_rubric_missing_field_rejected` [4] | N | FR-05 | RED-dep: QualityRubric |
| `test_quality_rubric_requires_three_levels` | N | FR-05 | RED-dep: levels>=3 |
| `test_quality_rubric_illegal_bool_rejected` | N | FR-05 | RED-dep: bool type |

### `test_evaluation_result.py` (4) — status, not exception
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_completion_status_members` | N | FR-05, NFR-09 | COMPLETE/INCOMPLETE/BLOCKED/REVIEW/FAILED |
| `test_incomplete_reason_members` | N | FR-05 | MANIFEST/SNAPSHOT/MODEL/PROMPT/CODE/MISSING_RESULT |
| `test_incomplete_result_does_not_raise` | N | FR-05 | INCOMPLETE is data |
| `test_complete_result_has_no_incomplete_reason` | N | FR-05 | COMPLETE -> None |

### `test_comparison.py` (2) — incompatible manifest -> INCOMPLETE
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_mismatch_yields_incomplete_not_win` [snapshot/model/prompt] | N | FR-05 | RED-dep: compare_runs; not a win |
| `test_matching_inputs_are_comparable` | N | FR-05 | positive |

(code/policy mismatch: **PENDING (B)** — manifest has no code_hash/policy_hash yet.)

### `test_replay.py` (4) — replay determinism
| Test | Kind | Covers | Notes |
|---|---|---|---|
| `test_replay_is_deterministic` | N | NFR-08 | same input -> same state |
| `test_replay_is_independent_of_input_order` | N | NFR-08 | orders by (run_id, sequence) |
| `test_replay_is_offline_no_llm` | N | NFR-08 | no network/model |
| `test_replay_dedupes_identical_events_once` | N | NFR-08 | dedupe |

## Note on scope (avoiding overstatement)
Duplicate handling is enforced through the public `AuditSink.append` / `dedupe_events`
(not scattered ad-hoc checks); rubric validation through the independent
`quality_rubric` field. These are stated once, per contract, not claimed as
multiple separate guarantees.

## Approval
D (@ZFebron491001) under GATE-01; author does not self-review. Binding:
`docs/approvals/test-hash-FR-05-contracts.txt` (test_content_commit + aggregate)
+ GitHub review commit_id (authoritative head) + external registry (merge commit).
