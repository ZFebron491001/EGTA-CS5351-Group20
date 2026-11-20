# Spec registry — FR-05 contracts (test-first)

Registry for the `@pytest.mark.spec` test range (per execution_plan:372 bootstrap:
red tests are validated as "expected failure" on the branch without implementation,
recorded here as the not-yet-enabled range; the implementation PR enables them).

## Marker & enablement

- Marker: `spec` — registered in `pyproject.toml` `[tool.pytest.ini_options].markers`
  (`--strict-markers` is active, so an unregistered marker fails).
- Every file under `test/offline/contracts/test_*.py` sets
  `pytestmark = pytest.mark.spec`.
- **Not enabled on `main`/spec as a gate:** `testpaths = ["tests"]` does not collect
  `test/offline/contracts` by default, so the spec's red does not break `main`.
  The implementation PR **enables** this range (runs it as a required check). We
  do **not** rely on `testpaths` omission as the quarantine mechanism at merge
  time; this registry records the intended enablement boundary explicitly.
- Deselect/verify: `pytest -m spec test/offline/contracts` (runs only spec tests).

## Expected-RED reason

On the spec branch (no `src/`), importing `egta.contracts.audit` /
`egta.contracts.evaluation` fails (`ModuleNotFoundError: egta.contracts...`).
That import failure is the test-first signal. `--collect-only` is **not** a green
proof here (collection imports modules); CI proves well-formedness via
`py_compile` + AST test-count, not green collection.

## Coverage

- 7 test files, 60 test functions, 90 cases.
- RED-dep (expected red until implementation): four-variant manifest, unknown
  variant, typed `metrics_rubric` (MetricDef 7 fields), `quality_rubric`
  (4 fields / levels≥3 / bool), non-finite/non-JSON metrics rejection,
  audit exceptions/Receipt/AuditSink/anchor, evaluation INCOMPLETE status,
  compare_runs mismatch, replay determinism/offline.
- PENDING (B): code/policy mismatch (manifest lacks `code_hash`/`policy_hash`);
  `quality_rubric` placement confirmed separate field (adjust to B if reverted).

## Hash & approval

- Test content hash + `test_content_commit`: see
  `docs/approvals/test-hash-FR-05-contracts.txt`.
- Authoritative reviewed head = GitHub review `commit_id`.
- Merge commit recorded in this registry / CI artifact / PR comment after merge.

## Verification evidence

- Spec branch: `pytest test/offline/contracts` → collection errors
  (`ModuleNotFoundError: egta`), **RED by design**.
- `py_compile test/offline/contracts/*.py` → exit 0; AST = 60 test functions.
- `ruff check .` → green.
- Full spec-satisfying implementation built in `/tmp` (audit/evaluation/manifest/
  events-with-validator) → `pytest test/offline/contracts` → **90 passed**. This
  proves each new test turns green when its contract is implemented (red is due
  to unimplemented contracts, not bad tests).
