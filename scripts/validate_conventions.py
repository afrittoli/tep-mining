#!/usr/bin/env python3
# Copyright 2026 The Tekton Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Validate conventions/*.yaml structural invariants.

Nothing else in this pipeline's CI enforces these — a broken conventions/seed-taxonomy.yaml
(bad YAML, a missing required key, a provenance value outside the three allowed states, a
parent reference that doesn't resolve or forms a cycle, two values in the same facet sharing a
name) would otherwise pass ruff/mypy/pytest/markdownlint untouched.

Usage:
    uv run scripts/validate_conventions.py conventions/seed-taxonomy.yaml
    uv run scripts/validate_conventions.py conventions/*.yaml
"""

import argparse
import sys
from pathlib import Path

from ruamel.yaml import YAML, YAMLError

REQUIRED_VALUE_KEYS = {"value", "description", "provenance", "source"}
VALID_PROVENANCE = {"seeded", "discovered", "suggested"}


def _load_yaml(path: Path) -> dict | None:
    """The parsed document, or None (with an error already printed) if it doesn't parse."""
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        print(f"{path}: invalid YAML: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"{path}: top-level document must be a mapping", file=sys.stderr)
        return None
    return data


def _validate_facets(facets: object, facet_name_prefix: str = "facets") -> list[str]:
    """Returns error strings for every invariant violated across all facets; empty means valid."""
    errors: list[str] = []
    if not isinstance(facets, dict) or not facets:
        return [f"top-level '{facet_name_prefix}' must be a non-empty mapping"]

    for facet_name, facet in facets.items():
        where_facet = f"{facet_name_prefix}.{facet_name}"
        if not isinstance(facet, dict):
            errors.append(f"{where_facet}: must be a mapping")
            continue
        if not facet.get("description"):
            errors.append(f"{where_facet}: missing a facet-level 'description'")

        values = facet.get("values")
        if values is None:
            errors.append(f"{where_facet}: missing 'values' (use [] if empty)")
            continue
        if not isinstance(values, list):
            errors.append(f"{where_facet}.values: must be a list")
            continue

        seen: dict[str, dict] = {}
        for i, v in enumerate(values):
            where = f"{where_facet}.values[{i}]"
            if not isinstance(v, dict):
                errors.append(f"{where}: must be a mapping")
                continue

            missing = REQUIRED_VALUE_KEYS - v.keys()
            if missing:
                errors.append(f"{where} ({v.get('value', '?')}): missing key(s) {sorted(missing)}")
                continue

            name = v["value"]
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{where}: 'value' must be a non-empty string")
                continue
            if not v.get("description"):
                errors.append(f"{where} ({name}): 'description' must be non-empty")
            if not v.get("source"):
                errors.append(f"{where} ({name}): 'source' must be non-empty")

            provenance = v.get("provenance")
            if provenance not in VALID_PROVENANCE:
                errors.append(
                    f"{where} ({name}): 'provenance' must be one of "
                    f"{sorted(VALID_PROVENANCE)}, got {provenance!r}"
                )

            if name in seen:
                errors.append(f"{where_facet}: duplicate value name {name!r}")
            else:
                seen[name] = v

        errors.extend(_validate_parents(where_facet, seen))

    return errors


def _validate_parents(where_facet: str, seen: dict[str, dict]) -> list[str]:
    """`parent` must resolve to another value in the same facet, and chains must not cycle."""
    errors: list[str] = []
    for name, v in seen.items():
        parent = v.get("parent")
        if parent is None:
            continue
        if parent == name:
            errors.append(f"{where_facet}.{name}: 'parent' cannot reference itself")
        elif parent not in seen:
            errors.append(f"{where_facet}.{name}: 'parent' {parent!r} not found in this facet")

    for name in seen:
        visited = {name}
        current = seen[name].get("parent")
        while current is not None and current in seen:
            if current in visited:
                errors.append(f"{where_facet}: parent cycle involving {name!r}")
                break
            visited.add(current)
            current = seen[current].get("parent")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate conventions/*.yaml structural invariants"
    )
    parser.add_argument("paths", nargs="+", help="conventions/*.yaml files to validate")
    args = parser.parse_args(argv)

    ok = True
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"ERROR: {path} not found", file=sys.stderr)
            ok = False
            continue

        data = _load_yaml(path)
        if data is None:
            ok = False
            continue

        errors = _validate_facets(data.get("facets"))
        if errors:
            ok = False
            print(f"{path}: {len(errors)} error(s)")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"{path}: OK")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
