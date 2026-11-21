# Spec registry — E2 evaluation (test-first)

## Marker & quarantine (same Option A as FR-05 contracts)
- Marker `spec` (already registered in `pyproject.toml`; `--strict-markers` on).
- Every file under `test/offline/evaluation/test_*.py` sets
  `pytestmark = pytest.mark.spec`.
- Default `pytest` excludes `spec` (`addopts -m "not integration and not spec"`);
  the spec is enabled explicitly on the impl branch via
  `pytest -m spec test/offline/evaluation`. Gate = **exact case count** (filled
  from `--collect-only` when frozen), not `>=`.
- RED on spec branch: `pytest -m spec test/offline/evaluation` → collection errors
  (`ModuleNotFoundError: egta.evaluation.*`). `py_compile`/AST prove well-formed.

## Scope (from D PR #6)
- **D#3:** sink moved to `evaluation/sink.py`; contracts/audit.py = protocols/
  Receipt/exceptions/verify only. `test_sqlite_sink.py` = real SQLite integration.
- **D#1:** `compare_runs(..., manifest: ExperimentManifest | None = None)`;
  supplied manifest's `compute_manifest_hash` must equal both sides'
  `manifest_hash` → else INCOMPLETE/MANIFEST_MISMATCH. `RunSummary` unchanged.
- **D#4:** rubric true-comparison **deferred** (debt: complete operator/threshold
  winner scoring); required now = **no misleading COMPLETE** when rubric
  observation metrics are missing (returns INCOMPLETE).
- **D#6:** `verify_chain([])` OK; `verify_chain([], anchor=...)` → `ChainBroken`
  (fail-closed).

## Files & case counts (exact from `--collect-only`)
- `test_replay.py` 10 · `test_report.py` 6 · `test_metrics.py` 5 · `test_sqlite_sink.py` 8
- **Total = 29 cases** (gate = exactly 29).

## Hash & approval
- `docs/approvals/test-hash-E2-evaluation.txt` will hold `test_content_commit`,
  `aggregate_sha256`, `spec_bundle_sha256` (tests + trace + this registry).
- Authoritative reviewed head = GitHub review `commit_id`; merge recorded
  externally. Do not push the approval file after approval.

## Dependencies
- E2 impl depends on `egta.contracts.*` (Phase-1 PR #6). **E2 impl waits for #6
  to merge**; this spec may proceed in parallel off `main`.
