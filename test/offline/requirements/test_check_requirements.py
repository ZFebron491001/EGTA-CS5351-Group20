"""Tests for tools/check_requirements.py (D1 registry checker).

The checker is generic, so these tests build tiny self-contained registries and
schemas in ``tmp_path`` rather than depending on the real ``docs/req`` files
(which live on their own PR branches). Each test asserts one rule from the
checker's contract.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_requirements.py"


def _load_tool():
    import sys

    spec = importlib.util.spec_from_file_location("check_requirements", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_requirements = _load_tool()


# A minimal schema that mirrors docs/req/req-schema.json's structural intent for
# the fields the semantic checks rely on.
MINIMAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "requirements"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "requirements": {"type": "array", "minItems": 1},
    },
}


def _req(rid: str, **overrides):
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
    return check_requirements.run(reg_path, schema_path)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_valid_registry_passes(tmp_path):
    report = _write(tmp_path, [_req("FR-01"), _req("NFR-01", type="nonfunctional")])
    assert report.ok(), report.errors
    assert report.errors == []


def test_source_reference_to_existing_id_resolves(tmp_path):
    report = _write(
        tmp_path,
        [
            _req("FR-01", source=["§3.2 FR table", "INV-01"]),
            _req("INV-01", type="invariant",
                 fit_criterion={"metric": "x", "operator": "eq", "threshold": 0,
                                "verification": "pytest test/offline/requirements -q"}),
        ],
    )
    assert report.ok(), report.errors


# --------------------------------------------------------------------------- #
# Semantic rules
# --------------------------------------------------------------------------- #

def test_duplicate_id_fails(tmp_path):
    report = _write(tmp_path, [_req("FR-01"), _req("FR-01")])
    assert not report.ok()
    assert any("duplicate id: FR-01" in e for e in report.errors)


def test_unresolved_source_reference_fails(tmp_path):
    report = _write(tmp_path, [_req("FR-01", source=["INV-99"])])
    assert not report.ok()
    assert any("references unknown id 'INV-99'" in e for e in report.errors)


def test_prose_source_is_not_treated_as_reference(tmp_path):
    # "§3.2 FR table" and "T-BUD-01" must not be parsed as requirement ids.
    report = _write(tmp_path, [_req("FR-01", source=["§3.2 FR table"], evidence=["T-BUD-01"])])
    assert report.ok(), report.errors


def test_must_without_component_fails(tmp_path):
    report = _write(tmp_path, [_req("FR-01", component=None)])
    assert not report.ok()
    assert any("has no component" in e for e in report.errors)


def test_must_without_verification_fails(tmp_path):
    fc = {"metric": "x", "operator": "gte", "threshold": 1, "verification": ""}
    report = _write(tmp_path, [_req("FR-01", fit_criterion=fc)])
    assert not report.ok()
    assert any("has no verification" in e for e in report.errors)


def test_invariant_not_zero_tolerance_fails(tmp_path):
    fc = {"metric": "x", "operator": "gte", "threshold": 0,
          "verification": "pytest test/offline/requirements -q"}
    report = _write(
        tmp_path,
        [_req("INV-01", type="invariant", fit_criterion=fc)],
    )
    assert not report.ok()
    assert any("not zero-tolerance" in e for e in report.errors)


def test_invariant_zero_tolerance_passes(tmp_path):
    fc = {"metric": "x", "operator": "eq", "threshold": 0,
          "verification": "pytest test/offline/requirements -q"}
    report = _write(tmp_path, [_req("INV-01", type="invariant", fit_criterion=fc)])
    assert report.ok(), report.errors


# --------------------------------------------------------------------------- #
# CLI behaviour
# --------------------------------------------------------------------------- #

def test_cli_exit_zero_on_pass(tmp_path):
    _write(tmp_path, [_req("FR-01")])
    rc = check_requirements.main(
        ["--registry", str(tmp_path / "requirements.yaml"),
         "--schema", str(tmp_path / "req-schema.json")]
    )
    assert rc == 0


def test_cli_exit_one_on_failure(tmp_path):
    _write(tmp_path, [_req("FR-01"), _req("FR-01")])
    rc = check_requirements.main(
        ["--registry", str(tmp_path / "requirements.yaml"),
         "--schema", str(tmp_path / "req-schema.json")]
    )
    assert rc == 1


def test_cli_json_report(tmp_path, capsys):
    _write(tmp_path, [_req("FR-01")])
    rc = check_requirements.main(
        ["--registry", str(tmp_path / "requirements.yaml"),
         "--schema", str(tmp_path / "req-schema.json"), "--json"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_missing_registry_is_an_error(tmp_path):
    schema_path = tmp_path / "req-schema.json"
    schema_path.write_text(json.dumps(MINIMAL_SCHEMA), encoding="utf-8")
    report = check_requirements.run(tmp_path / "nope.yaml", schema_path)
    assert not report.ok()
    assert any("registry not found" in e for e in report.errors)
