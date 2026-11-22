# Trace — D1 requirement-registry checker (`tools/check_requirements.py`)

Requirement-to-test trace for the D1 checker. Split per GATE-01:

- **Spec PR** (`spec/D1-check-requirements`): `test/offline/requirements/` only,
  expected RED because the tool is absent. Approved test hash recorded in
  `docs/approvals/test-hash-D1-check-requirements.txt`.
- **Implementation PR** (`feat/D1-check-requirements`): adds
  `tools/check_requirements.py` + CI wiring + CODEOWNERS, and descends from the
  spec PR's merge commit.

## Requirements covered

| Req | How this checker satisfies it |
|---|---|
| NFR-10 (governance/maintainability) | Requirement changes are structurally + semantically validated in one runnable check, so a broken registry cannot be merged silently. |
| GATE-03 (schema gate) | This is the schema gate's executable core: `--registry`/`--schema` plus `--json` for CI; E wires it into the gate after merge. |
| FR-01 / INV-02 (A's entries) | Validates A's own registry entries (fit criterion present, references resolve, invariants zero-tolerance). |

## Test function → rule mapping

| Test function | Rule |
|---|---|
| `test_valid_registry_passes` | happy path: both layers pass |
| `test_source_reference_to_existing_id_resolves` | exact id reference resolves |
| `test_duplicate_id_fails` | unique ids |
| `test_unresolved_source_reference_fails` | unknown id reference |
| `test_prose_source_is_not_treated_as_reference` | `§…` / `T-BUD-01` not parsed as ids |
| `test_prefix_prose_is_not_treated_as_reference` | `FR-01 is…`, `FR-01..FR-05`, `GATE-03 and GATE-05` not parsed (exact fullmatch, D item 5) |
| `test_exact_id_token_still_resolves` | bare id still validated |
| `test_non_string_id_is_reported_not_crashing` | non-string id → structured schema error, no TypeError (D item 5) |
| `test_semantic_guard_handles_non_string_id_in_isolation` | semantic-layer guard for non-string id (D item 5) |
| `test_missing_required_field_fails_schema` | schema layer names the missing field; short-circuits (D item 6) |
| `test_invalid_schema_reports_without_traceback` | bad schema reported, not raised (D item 6) |
| `test_must_without_component_fails` | Must bound to a component |
| `test_must_without_verification_fails` | Must bound to a verification |
| `test_invariant_not_zero_tolerance_fails` | invariant zero tolerance |
| `test_invariant_zero_tolerance_passes` | zero-tolerance invariant accepted |
| `test_cli_exit_zero_on_pass` / `test_cli_exit_one_on_failure` / `test_cli_json_report` | CLI contract for CI |
| `test_missing_registry_is_an_error` | missing file is a structured error |

## Expected state per branch

| Branch | `pytest test/offline/requirements` | CI `offline spec suites` |
|---|---|---|
| spec (tool absent) | RED — tool missing, tests fail | `requirements` suite N/A (tool file absent) |
| impl (tool present) | 19 passed | `requirements` suite runs, expects 19 passed |

## Deferred dependencies (not yet GATE-03 enabled)

- `docs/req/requirements.yaml` (#9) and `docs/req/req-schema.json` (#15) are not
  yet on `main`. Until they land, the default command
  `python tools/check_requirements.py` reports `registry not found`; running it
  against the branch artifacts passes (`OK`, exit 0). This trace does **not**
  claim GATE-03 is enabled — it claims the checker that GATE-03 will run exists
  and is tested.
- CI wiring is included in the impl PR, but the `requirements` suite only reports
  once the tool is present on the branch that adds it.
