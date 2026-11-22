# Trace — D1 requirement-registry checker (`tools/check_requirements.py`)

Requirement-to-test trace for the D1 checker. Split per GATE-01:

- **Spec PR** (`spec/D1-check-requirements`, #30): `test/offline/requirements/`
  only, expected RED because the tool is absent. Approved test hash in
  `docs/approvals/test-hash-D1-check-requirements.txt` (`actual_cases: 24`).
- **Implementation PR** (`feat/D1-check-requirements`, #31): adds
  `tools/check_requirements.py` + CI wiring + CODEOWNERS, and descends from the
  spec PR's merge commit.

Merge order (A): **#15 (schema) → #30 (spec) → #31 (impl)**. The 4 real-schema
tests need `docs/req/req-schema.json` from #15, so #31 builds on #15 and stays
Draft until #15 merges.

## Requirements covered

| Req | How this checker satisfies it |
|---|---|
| NFR-10 (governance/maintainability) | Requirement changes are structurally + semantically validated in one runnable check, so a broken registry cannot be merged silently. |
| GATE-03 (schema gate) | This is the schema gate's executable core: `--registry`/`--schema` plus `--json` for CI; E wires it into the gate after merge. |
| FR-01 / INV-02 (A's entries) | Validates A's own registry entries (fit criterion present, references resolve, invariants zero-tolerance). |

## Test function → rule mapping (20 functions, 24 cases)

| Test function | Rule |
|---|---|
| `test_valid_registry_passes` | happy path: both layers pass |
| `test_source_reference_to_existing_id_resolves` | exact id reference resolves |
| `test_duplicate_id_fails` | unique ids |
| `test_unresolved_source_reference_fails` | unknown id reference |
| `test_prose_source_is_not_treated_as_reference` | `§…` / `T-BUD-01` not parsed as ids |
| `test_prefix_prose_is_not_treated_as_reference` | `FR-01 is…`, `FR-01..FR-05`, `GATE-03 and GATE-05` not parsed (exact fullmatch, D #27 item 5) |
| `test_exact_id_token_still_resolves` | bare id still validated |
| `test_non_string_id_is_reported_not_crashing` | non-string id → structured error, no TypeError (D #27 item 5) |
| `test_missing_required_field_fails_schema` | schema layer names the missing field; short-circuits (D #27 item 6) |
| `test_invalid_schema_reports_without_traceback` | bad schema reported, not raised (D #27 item 6) |
| `test_must_without_component_fails` | Must bound to a component |
| `test_must_without_verification_fails` | Must bound to a verification |
| `test_invariant_not_zero_tolerance_fails` | invariant zero tolerance |
| `test_invariant_zero_tolerance_passes` | zero-tolerance invariant accepted |
| `test_id_prefix_type_mismatch_fails` | FR-01 + governance rejected by the checker (D #15 item 2) |
| `test_id_prefix_type_match_passes` | matching id+type accepted |
| `test_real_schema_rejects_bad_ids` | real schema rejects `XFR-01` / `FR-011` / `" FR-01"` (D #15 items 1,6) |
| `test_real_schema_rejects_bad_owner_and_metric` | real schema rejects `Alice` / `A+Z` / `x y` (D #15 items 1,6) |
| `test_real_schema_rejects_id_type_mismatch` | real schema rejects FR-01 + governance (D #15 items 2,6) |
| `test_real_schema_accepts_valid_entry` | real schema accepts a valid FR-01 entry |

The 4 `test_real_schema_*` cases load `docs/req/req-schema.json` (from #15), not
`MINIMAL_SCHEMA`, so the anchored patterns and id-type conditionals are covered.

## Expected state per branch

| Branch | `pytest test/offline/requirements` | CI `offline spec suites` |
|---|---|---|
| spec (#30, tool and schema absent) | RED — 24 failed (tool missing), collection OK | `requirements` suite N/A (tool file absent) |
| impl (#31, tool + #15 schema present) | 24 passed | `requirements` suite runs, expects 24 passed |

## Deferred dependencies (not yet GATE-03 enabled)

- `docs/req/requirements.yaml` (#9) and `docs/req/req-schema.json` (#15) are not
  yet on `main`. Until they land, the default command
  `python tools/check_requirements.py` reports `registry not found`; running it
  against the branch artifacts passes (`OK`, exit 0). This trace does **not**
  claim GATE-03 is enabled — it claims the checker that GATE-03 will run exists
  and is tested.
- CI wiring ships in the impl PR; the `requirements` suite only reports once the
  tool is present on the branch that adds it.
