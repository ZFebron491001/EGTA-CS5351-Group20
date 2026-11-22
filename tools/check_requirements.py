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
# bare id. Strings like "§3.2 FR table" or "T-BUD-01" are prose/artefact refs.
_REF_PREFIXES = ("FR-", "NFR-", "INV-", "GOV-", "GATE-", "SUB-")


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

    validator = jsonschema.Draft202012Validator(schema)
    # Sort by path so the first error is stable and easy to act on.
    errors = sorted(validator.iter_errors(registry), key=lambda e: list(e.path))
    for err in errors:
        location = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.errors.append(f"[schema] {location}: {err.message}")


def _requirement_ids(registry: Any) -> list[str]:
    reqs = registry.get("requirements") if isinstance(registry, dict) else None
    if not isinstance(reqs, list):
        return []
    return [r["id"] for r in reqs if isinstance(r, dict) and "id" in r]


def _referenced_ids(values: list[str]) -> list[str]:
    """Return the entries in *values* that are bare requirement ids."""
    return [v for v in values if isinstance(v, str) and v.startswith(_REF_PREFIXES)]


def check_semantics(registry: Any, report: Report) -> None:
    """Layer 2: rules JSON Schema cannot express."""
    if not isinstance(registry, dict) or not isinstance(registry.get("requirements"), list):
        report.errors.append("[semantic] registry has no 'requirements' list")
        return

    reqs = [r for r in registry["requirements"] if isinstance(r, dict)]
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
        if not ID_PATTERN.match(rid):
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


def run(registry_path: Path, schema_path: Path) -> Report:
    report = Report()
    if not registry_path.is_file():
        report.errors.append(f"registry not found: {registry_path}")
        return report
    if not schema_path.is_file():
        report.errors.append(f"schema not found: {schema_path}")
        return report

    registry = _load_yaml(registry_path)
    schema = _load_json(schema_path)
    check_schema(registry, schema, report)
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
