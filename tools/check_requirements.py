#!/usr/bin/env python3
"""Requirement registry checker for D1 (docs/req/requirements.yaml).

Two layers, in order:

1. Structural (JSON Schema): ``docs/req/req-schema.json`` validates required
   fields, enums and threshold types. A YAML that passes here is structurally
   sound, not necessarily a good requirement.
2. Semantic: rules JSON Schema cannot express — unique ids, every cross-reference
   to another requirement id resolves, every Must entry is bound to a component
   and a verification, every invariant is at zero tolerance, and the component
   value is drawn from the schema's enum.

Exit code is 0 only when both layers pass. ``--json`` emits a machine-readable
report (used by the GATE-03 CI job and by E when wiring the gates).

Usage::

    python tools/check_requirements.py
    python tools/check_requirements.py --registry docs/req/requirements.yaml \\
        --schema docs/req/req-schema.json --json

The tool is generic: it does not hard-code this repository's registry contents,
only the rules. Point it at any registry/schema pair with the flags.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ID_PATTERN = re.compile(r"^(?:FR|NFR|INV|GOV|GATE|SUB)-\d{2}$")
# A source/evidence token counts as a requirement-id reference only if it is a
# bare id (exact full match). Strings like "§3.2 FR table", "T-BUD-01",
# "FR-01..FR-05" or "FR-01 is the parent" are prose/artefact/range refs.


@dataclass
class Report:
    """Collected findings from both check layers."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.errors


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_schema(registry: Any, schema: Any, report: Report) -> None:
    """Layer 1: validate the registry against the JSON Schema."""
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - guarded by a clear message
        report.errors.append(
            "jsonschema is not installed; run: python -m pip install jsonschema "
            "(it is a documented dev dependency for the GATE-03 check)"
        )
        return

    try:
        validator = jsonschema.Draft202012Validator(schema)
        validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        # The schema itself is invalid: report it instead of letting a traceback
        # escape. A broken schema is a configuration error, not a registry error.
        report.errors.append(f"[schema] the JSON Schema is itself invalid: {exc.message}")
        return

    # Sort by path so the first error is stable and easy to act on.
    errors = sorted(validator.iter_errors(registry), key=lambda e: list(e.path))
    for err in errors:
        location = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.errors.append(f"[schema] {location}: {err.message}")


def _requirement_ids(registry: Any) -> list[str]:
    reqs = registry.get("requirements") if isinstance(registry, dict) else None
    if not isinstance(reqs, list):
        return []
    # Only string ids participate in uniqueness/reference checks; a non-string id
    # is a schema error and is reported by the schema layer (see the guard in
    # check_semantics), not coerced here.
    return [r["id"] for r in reqs if isinstance(r, dict) and isinstance(r.get("id"), str)]


def _referenced_ids(values: list[str]) -> list[str]:
    """Return the entries in *values* that are exactly a bare requirement id.

    Uses a full match, not a prefix test: prose such as ``"FR-01 is the parent
    requirement"`` or a range like ``"FR-01..FR-05"`` must not be mistaken for a
    single-id reference (that would raise a false 'unknown id' error).
    """
    return [
        v for v in values
        if isinstance(v, str) and ID_PATTERN.fullmatch(v)
    ]


def check_semantics(registry: Any, report: Report) -> None:
    """Layer 2: rules JSON Schema cannot express."""
    if not isinstance(registry, dict) or not isinstance(registry.get("requirements"), list):
        report.errors.append("[semantic] registry has no 'requirements' list")
        return

    reqs = [r for r in registry["requirements"] if isinstance(r, dict)]

    # 0. Guard: a non-string (or missing) id is a schema error. Report it as a
    #    structured semantic error and exclude it from the id-based checks below
    #    so we never crash on the malformed entry.
    for index, req in enumerate(reqs):
        rid = req.get("id")
        if not isinstance(rid, str):
            report.errors.append(
                f"[semantic] requirements/{index}: id must be a string, got "
                f"{type(rid).__name__} ({rid!r})"
            )

    ids = _requirement_ids(registry)
    id_set = set(ids)

    # 1. Unique ids.
    seen: set[str] = set()
    for rid in ids:
        if rid in seen:
            report.errors.append(f"[semantic] duplicate id: {rid}")
        seen.add(rid)

    # 2. Every id matches the naming pattern (schema also checks, kept for the
    #    cross-reference resolver below to be meaningful).
    for rid in ids:
        if not ID_PATTERN.fullmatch(rid):
            report.errors.append(f"[semantic] malformed id: {rid!r}")

    # 3. Cross-references resolve: any source/evidence token that looks like an id
    #    must exist. Governance/gate/submission ids may be referenced too.
    for req in reqs:
        rid = req.get("id", "<no-id>")
        for field_name in ("source", "evidence"):
            values = req.get(field_name) or []
            if not isinstance(values, list):
                continue
            for token in _referenced_ids(values):
                if token not in id_set:
                    report.errors.append(
                        f"[semantic] {rid}.{field_name} references unknown id {token!r}"
                    )

    # 4. Every Must entry is bound to a component and a verification.
    for req in reqs:
        rid = req.get("id", "<no-id>")
        if req.get("priority") != "Must":
            continue
        if not req.get("component"):
            report.errors.append(f"[semantic] {rid} is Must but has no component")
        fc = req.get("fit_criterion") or {}
        if not fc.get("verification"):
            report.errors.append(f"[semantic] {rid} is Must but has no verification")

    # 5. Every invariant is at zero tolerance (operator eq, threshold 0).
    for req in reqs:
        if req.get("type") != "invariant":
            continue
        rid = req.get("id", "<no-id>")
        fc = req.get("fit_criterion") or {}
        if fc.get("operator") != "eq" or fc.get("threshold") != 0:
            report.errors.append(
                f"[semantic] {rid} is an invariant but is not zero-tolerance "
                f"(operator={fc.get('operator')!r}, threshold={fc.get('threshold')!r}; "
                "expected operator 'eq', threshold 0)"
            )

    # 6. Component value is in the schema enum (schema enforces this too; a
    #    warning here keeps the message readable if the schema is relaxed).
    allowed_components = {
        "evidence", "contracts", "budget", "deliberation", "risk_gate",
        "evaluation", "adapters", "app", "governance", "repo", "submission",
    }
    for req in reqs:
        comp = req.get("component")
        if comp is not None and comp not in allowed_components:
            report.warnings.append(
                f"[semantic] {req.get('id', '<no-id>')} uses unknown component {comp!r}"
            )

    # 7. The id prefix and the type must agree (D review of #15 item 2). The
    #    schema also enforces this via conditionals; keeping it here too means a
    #    relaxed/old schema cannot let a misclassified entry through, and the
    #    checker stays correct standalone.
    prefix_to_type = {
        "FR": "functional",
        "NFR": "nonfunctional",
        "INV": "invariant",
        "GOV": "governance",
        "GATE": "gate",
        "SUB": "submission",
    }
    for req in reqs:
        rid = req.get("id")
        if not isinstance(rid, str) or not ID_PATTERN.fullmatch(rid):
            continue  # reported above (non-string / malformed id)
        prefix = rid.split("-", 1)[0]
        expected_type = prefix_to_type.get(prefix)
        actual_type = req.get("type")
        if expected_type is not None and actual_type is not None and actual_type != expected_type:
            report.errors.append(
                f"[semantic] {rid}: type {actual_type!r} does not match its id prefix "
                f"{prefix!r} (expected {expected_type!r})"
            )


def run(registry_path: Path, schema_path: Path) -> Report:
    report = Report()
    if not registry_path.is_file():
        report.errors.append(f"registry not found: {registry_path}")
        return report
    if not schema_path.is_file():
        report.errors.append(f"schema not found: {schema_path}")
        return report

    try:
        registry = _load_yaml(registry_path)
    except yaml.YAMLError as exc:
        report.errors.append(f"registry is not valid YAML: {exc}")
        return report
    try:
        schema = _load_json(schema_path)
    except (json.JSONDecodeError, OSError) as exc:
        report.errors.append(f"schema is not valid JSON: {exc}")
        return report

    check_schema(registry, schema, report)

    # Short-circuit: if the structural layer already failed (and not because the
    # schema itself was invalid), the semantic pass over a knowingly-malformed
    # registry can only produce noisy, misleading follow-on errors.
    bad_schema = any("[schema] the JSON Schema is itself invalid" in e for e in report.errors)
    if report.errors and not bad_schema:
        return report

    check_semantics(registry, report)
    return report


def _print_human(report: Report, registry_path: Path) -> None:
    if report.ok():
        print(f"OK: {registry_path} passed schema and semantic checks.")
    else:
        print(f"FAIL: {registry_path} has {len(report.errors)} error(s):")
        for err in report.errors:
            print(f"  - {err}")
    for warn in report.warnings:
        print(f"  warning: {warn}")


def _print_json(report: Report, registry_path: Path) -> None:
    print(
        json.dumps(
            {
                "registry": str(registry_path),
                "ok": report.ok(),
                "errors": report.errors,
                "warnings": report.warnings,
            },
            indent=2,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the D1 requirement registry.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("docs/req/requirements.yaml"),
        help="path to the requirement registry (default: docs/req/requirements.yaml)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("docs/req/req-schema.json"),
        help="path to the JSON Schema (default: docs/req/req-schema.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable JSON report instead of human text",
    )
    args = parser.parse_args(argv)

    report = run(args.registry, args.schema)
    if args.json:
        _print_json(report, args.registry)
    else:
        _print_human(report, args.registry)
    return 0 if report.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
