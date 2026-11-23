"""Contract tests for tools/check_requirements.py (D1 registry checker).

These tests exercise the checker through its CLI/`--json` boundary, not by
importing its module. That keeps this file **collectable on the spec branch**
where the tool does not exist yet: every test then fails cleanly (the subprocess
cannot run the tool) instead of aborting collection. On the implementation
branch the tool is present and the same tests pass (GATE-01: spec RED -> impl
green, test bytes unchanged).

Each test builds a tiny self-contained registry + schema in ``tmp_path`` so the
suite does not depend on the ``#9``/``#15`` artifacts being on ``main``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "tools" / "check_requirements.py"


# A minimal schema that mirrors docs/req/req-schema.json's structural intent and
# validates each requirement item, so the schema layer's core behaviour is
# exercised (not just the top-level object).
MINIMAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "requirements"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "requirements": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "id", "type", "statement", "priority", "component",
                    "fit_criterion", "evidence", "source", "owner",
                ],
                "properties": {
                    "id": {
                        "type": "string",
                        "pattern": "^(FR|NFR|INV|GOV|GATE|SUB)-[0-9]{2}$",
                    },
                    "priority": {"enum": ["Must", "Should", "Could", "Won't"]},
                    "fit_criterion": {
                        "type": "object",
                        "required": ["metric", "operator", "threshold", "verification"],
                    },
                },
            },
        },
    },
}


def _req(rid, **overrides):
    base = {
        "id": rid,
        "type": "functional",
        "statement": "A testable statement for the requirement entry.",
        "priority": "Must",
        "component": "evidence",
        "fit_criterion": {
            "metric": "some_metric",
            "operator": "gte",
            "threshold": 1,
            "verification": "pytest test/offline/requirements -q",
        },
        "evidence": ["E-01"],
        "source": ["§3.2 FR table"],
        "tradeoff": None,
        "owner": "A",
        "supplied_by": "A",
        "status": "draft_from_plan",
    }
    base.update(overrides)
    return base


def _write(tmp_path: Path, requirements: list, schema=None):
    registry = {"schema_version": "1.0", "requirements": requirements}
    reg_path = tmp_path / "requirements.yaml"
    schema_path = tmp_path / "req-schema.json"
    reg_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    schema_path.write_text(json.dumps(schema or MINIMAL_SCHEMA), encoding="utf-8")
    return reg_path, schema_path


def _run(reg_path: Path, schema_path: Path):
    """Run the checker via its CLI and return (returncode, parsed json report)."""
    proc = subprocess.run(
        [
            sys.executable, str(TOOL),
            "--registry", str(reg_path),
            "--schema", str(schema_path),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"ok": False, "errors": ["<no json output>"], "raw": proc.stdout + proc.stderr}
    return proc.returncode, report


def _report(tmp_path, requirements, schema=None):
    reg, sch = _write(tmp_path, requirements, schema)
    return _run(reg, sch)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_valid_registry_passes(tmp_path):
    rc, report = _report(tmp_path, [_req("FR-01"), _req("NFR-01", type="nonfunctional")])
    assert rc == 0
    assert report["ok"] is True
    assert report["errors"] == []


def test_source_reference_to_existing_id_resolves(tmp_path):
    rc, report = _report(
        tmp_path,
        [
            _req("FR-01", source=["§3.2 FR table", "INV-01"]),
            _req("INV-01", type="invariant",
                 fit_criterion={"metric": "x", "operator": "eq", "threshold": 0,
                                "verification": "pytest test/offline/requirements -q"}),
        ],
    )
    assert rc == 0, report
    assert report["ok"] is True


# --------------------------------------------------------------------------- #
# Semantic rules
# --------------------------------------------------------------------------- #

def test_duplicate_id_fails(tmp_path):
    rc, report = _report(tmp_path, [_req("FR-01"), _req("FR-01")])
    assert rc == 1
    assert any("duplicate id: FR-01" in e for e in report["errors"])


def test_unresolved_source_reference_fails(tmp_path):
    rc, report = _report(tmp_path, [_req("FR-01", source=["INV-99"])])
    assert rc == 1
    assert any("references unknown id 'INV-99'" in e for e in report["errors"])


def test_prose_source_is_not_treated_as_reference(tmp_path):
    # "§3.2 FR table" and "T-BUD-01" must not be parsed as requirement ids.
    rc, report = _report(tmp_path, [_req("FR-01", source=["§3.2 FR table"], evidence=["T-BUD-01"])])
    assert rc == 0, report


def test_prefix_prose_is_not_treated_as_reference(tmp_path):
    # Strings that START with an id-ish prefix but are not a bare id (prose,
    # ranges) must not raise a false "unknown id" error. This is the exact case
    # a startswith() check gets wrong.
    tokens = [
        "FR-01 is the parent requirement",
        "FR-01..FR-05",
        "GATE-03 and GATE-05",
        "NFR-10 etc",
    ]
    rc, report = _report(tmp_path, [_req("FR-01", source=tokens, evidence=tokens)])
    assert rc == 0, report


def test_exact_id_token_still_resolves(tmp_path):
    # A bare id token (exact match) is still validated.
    rc, report = _report(tmp_path, [_req("FR-01", source=["NFR-99"])])
    assert rc == 1
    assert any("references unknown id 'NFR-99'" in e for e in report["errors"])


def test_non_string_id_is_reported_not_crashing(tmp_path):
    # Through the full run(): the checker returns a structured report instead of
    # raising a TypeError on a non-string id.
    rc, report = _report(tmp_path, [_req(123)])
    assert rc == 1
    assert any("id" in e for e in report["errors"])


# --------------------------------------------------------------------------- #
# Schema layer
# --------------------------------------------------------------------------- #

def test_missing_required_field_fails_schema(tmp_path):
    # Drop a required field and assert the schema layer names it.
    req = _req("FR-01")
    del req["statement"]
    rc, report = _report(tmp_path, [req])
    assert rc == 1
    assert any("[schema]" in e and "statement" in e for e in report["errors"])
    # Short-circuit: a structural failure should not also emit semantic noise.
    assert not any("[semantic]" in e for e in report["errors"])


def test_invalid_schema_reports_without_traceback(tmp_path):
    # A schema that is not itself valid JSON Schema must be reported, not raised.
    broken_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"requirements": {"type": "not-a-real-type"}},
    }
    rc, report = _report(tmp_path, [_req("FR-01")], schema=broken_schema)
    assert rc == 1
    assert any("JSON Schema is itself invalid" in e for e in report["errors"])


# --------------------------------------------------------------------------- #
# Must / invariant rules
# --------------------------------------------------------------------------- #

def test_must_without_component_fails(tmp_path):
    rc, report = _report(tmp_path, [_req("FR-01", component=None)])
    assert rc == 1
    assert any("has no component" in e for e in report["errors"])


def test_must_without_verification_fails(tmp_path):
    fc = {"metric": "x", "operator": "gte", "threshold": 1, "verification": ""}
    rc, report = _report(tmp_path, [_req("FR-01", fit_criterion=fc)])
    assert rc == 1
    assert any("has no verification" in e for e in report["errors"])


def test_invariant_not_zero_tolerance_fails(tmp_path):
    fc = {"metric": "x", "operator": "gte", "threshold": 0,
          "verification": "pytest test/offline/requirements -q"}
    rc, report = _report(tmp_path, [_req("INV-01", type="invariant", fit_criterion=fc)])
    assert rc == 1
    assert any("not zero-tolerance" in e for e in report["errors"])


def test_invariant_zero_tolerance_passes(tmp_path):
    fc = {"metric": "x", "operator": "eq", "threshold": 0,
          "verification": "pytest test/offline/requirements -q"}
    rc, report = _report(tmp_path, [_req("INV-01", type="invariant", fit_criterion=fc)])
    assert rc == 0, report


# --------------------------------------------------------------------------- #
# CLI contract
# --------------------------------------------------------------------------- #

def test_cli_exit_zero_on_pass(tmp_path):
    reg, sch = _write(tmp_path, [_req("FR-01")])
    rc, _report_ = _run(reg, sch)
    assert rc == 0


def test_cli_exit_one_on_failure(tmp_path):
    reg, sch = _write(tmp_path, [_req("FR-01"), _req("FR-01")])
    rc, _report_ = _run(reg, sch)
    assert rc == 1


def test_cli_json_report(tmp_path):
    reg, sch = _write(tmp_path, [_req("FR-01")])
    rc, report = _run(reg, sch)
    assert rc == 0
    assert report["ok"] is True
    assert report["errors"] == []
    assert "registry" in report


def test_missing_registry_is_an_error(tmp_path):
    reg, sch = _write(tmp_path, [_req("FR-01")])
    rc, report = _run(tmp_path / "nope.yaml", sch)
    assert rc == 1
    assert any("registry not found" in e for e in report["errors"])


# --------------------------------------------------------------------------- #
# id-prefix / type linkage (D #15 item 2)
# --------------------------------------------------------------------------- #

def test_id_prefix_type_mismatch_fails(tmp_path):
    # FR-01 declared as governance must be rejected (the schema also enforces
    # this; the checker must too, so a relaxed schema cannot let it through).
    rc, report = _report(tmp_path, [_req("FR-01", type="governance")])
    assert rc == 1
    assert any("does not match its id prefix" in e for e in report["errors"])


def test_id_prefix_type_match_passes(tmp_path):
    rc, report = _report(tmp_path, [_req("GOV-01", type="governance")])
    assert rc == 0, report


# --------------------------------------------------------------------------- #
# Regression against the REAL schema (D #15 item 6)
#
# These load docs/req/req-schema.json (the real schema from #15), not the local
# MINIMAL_SCHEMA, so the anchored patterns and id-type conditionals are covered.
# On the spec branch the real schema is not present yet (it lands with #15), so
# these fail like the rest of the suite (expected RED); once #15 and the tool are
# on the branch they pass.
# --------------------------------------------------------------------------- #

REAL_SCHEMA = REPO_ROOT / "docs" / "req" / "req-schema.json"


def _real_schema_report(tmp_path, requirements):
    real = json.loads(REAL_SCHEMA.read_text(encoding="utf-8"))
    reg, sch = _write(tmp_path, requirements, schema=real)
    return _run(reg, sch)


def test_real_schema_rejects_bad_ids(tmp_path):
    for bad in ("XFR-01", "FR-011", " FR-01"):
        rc, report = _real_schema_report(tmp_path, [_req(bad)])
        assert rc == 1, f"{bad!r} should be rejected by the real schema"
        assert any("[schema]" in e for e in report["errors"]), bad


def test_real_schema_rejects_bad_owner_and_metric(tmp_path):
    # Each bad value must be rejected by the SCHEMA layer specifically (a
    # `[schema]` error), not merely by some other checker failure.
    for bad_owner in ("Alice", "A+Z"):
        rc, report = _real_schema_report(tmp_path, [_req("FR-01", owner=bad_owner)])
        assert rc == 1, bad_owner
        assert any("[schema]" in e for e in report["errors"]), bad_owner

    bad_metric = _req("FR-01")
    bad_metric["fit_criterion"]["metric"] = "x y"
    rc, report = _real_schema_report(tmp_path, [bad_metric])
    assert rc == 1, "x y"
    assert any("[schema]" in e for e in report["errors"]), "x y"


def test_real_schema_rejects_id_type_mismatch(tmp_path):
    rc, report = _real_schema_report(tmp_path, [_req("FR-01", type="governance")])
    assert rc == 1
    assert any("[schema]" in e for e in report["errors"])


def test_real_schema_accepts_valid_entry(tmp_path):
    rc, report = _real_schema_report(tmp_path, [_req("FR-01")])
    assert rc == 0, report
