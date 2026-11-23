# Trace — FR-01 evidence pack implementation (A)

Implementation trace for module A's FR-01 `build_pack` / `validate_claims`. The
frozen pack spec and its trace live in `test/offline/evidence/test_pack.py` and
`docs/req/trace-FR-01-pack.md` (PR #25); the classification-precedence spec is
`test/offline/evidence/test_pack_precedence.py` + `docs/req/trace-FR-01-pack-precedence.md`
(#51). This file does not modify them.

## Files (all within module A's allowed paths)

| File | Purpose |
|---|---|
| `src/egta/evidence/pack.py` | `build_pack`, `validate_claims`, `InvalidCitation` |
| `src/egta/evidence/hashing.py` | local canonical pack hasher (byte-identical to the risk gate's) |
| `src/egta/evidence/__init__.py` | public exports |
| `docs/evidence/FR-01/pack-impl-green.txt` | green-run evidence |

No `contracts/`, `risk_gate/`, CI or other-module change (NFR-06 / AGENTS.md §3;
`tools/check_permissions.py --role build-a` → OK).

## pack_hash without a cross-module import

`pack_hash` must equal what the risk gate recomputes, or the gate rejects the pack
as `INTEGRITY_VIOLATION`. Importing `egta.risk_gate.canonical` from production
`egta.evidence` is forbidden (NFR-06). Resolution:

- `egta.evidence.hashing.canonical_pack_hash` reproduces the risk gate's canonical
  form **byte-for-byte** inside module A.
- `build_pack` accepts an injected `hasher` callable (default = that local hasher).
- The equality is proven, not asserted: the spec test
  `test_pack_hash_matches_risk_gate_canonical` imports
  `egta.risk_gate.canonical.recompute_evidence_hash` **in the test** (tests may
  reference other modules) and checks equality over E-01/E-07/E-22/E-23. If the
  risk gate changes its canonical form, that test fails and both sides must move
  together.

## Classification precedence (see #51 trace)

`_assemble` = integrity → staleness → time → dedupe: tampered cache →
`INTEGRITY_VIOLATION`; well-formed cache → `STALE_DATA`; future cache →
`STALE_DATA` (still excluded, so INV-02 `future_items_admitted == 0` holds); future
non-cache → `FUTURE_DATA`. Pinned by `test_pack_precedence.py` (#51).

## Verification

- `pytest -m spec test/offline/evidence` → 37 passed (33 frozen + 4 precedence).
- `pytest -m "not spec" test/offline/evidence` → 13 passed (INV-02 time policy).
- `ruff` clean; `mypy src/egta/evidence` clean.
- `tools/check_permissions.py --role build-a` → OK (no violations).

## GATE-01 / CI note

CI gating of the evidence suite (`.github/workflows/ci.yml`) is E/D-owned; module A
does not edit CI. Once this implementation merges, the evidence suite can be gated
by an E/D CI change (as with #47). GATE-01 for the impl PR binds to the approved
spec commit(s) via the approval records.
