from pathlib import Path

from scripts.validate_conventions import _validate_facets, _validate_parents, main

VALID_VALUE = {
    "value": "simplicity",
    "description": "Prefer the simplest solution.",
    "provenance": "seeded",
    "source": "design-principles.md#simplicity",
}


def _facets(*values: dict) -> dict:
    return {"principle": {"description": "why it matters", "values": list(values)}}


def test_valid_facets_has_no_errors() -> None:
    assert _validate_facets(_facets(VALID_VALUE)) == []


def test_facets_must_be_a_mapping() -> None:
    errors = _validate_facets([])
    assert len(errors) == 1
    assert "non-empty mapping" in errors[0]


def test_empty_facets_is_an_error() -> None:
    errors = _validate_facets({})
    assert len(errors) == 1


def test_facet_missing_description() -> None:
    errors = _validate_facets({"principle": {"values": [VALID_VALUE]}})
    assert any("missing a facet-level 'description'" in e for e in errors)


def test_facet_missing_values_key() -> None:
    errors = _validate_facets({"principle": {"description": "d"}})
    assert any("missing 'values'" in e for e in errors)


def test_facet_with_empty_values_list_is_valid() -> None:
    assert _validate_facets({"nature": {"description": "d", "values": []}}) == []


def test_value_missing_required_key() -> None:
    bad = {k: v for k, v in VALID_VALUE.items() if k != "source"}
    errors = _validate_facets(_facets(bad))
    assert any("missing key(s)" in e and "source" in e for e in errors)


def test_value_empty_description() -> None:
    bad = {**VALID_VALUE, "description": ""}
    errors = _validate_facets(_facets(bad))
    assert any("'description' must be non-empty" in e for e in errors)


def test_value_invalid_provenance() -> None:
    bad = {**VALID_VALUE, "provenance": "invented"}
    errors = _validate_facets(_facets(bad))
    assert any("'provenance' must be one of" in e for e in errors)


def test_duplicate_value_names_in_same_facet() -> None:
    errors = _validate_facets(_facets(VALID_VALUE, VALID_VALUE))
    assert any("duplicate value name" in e for e in errors)


def test_parent_resolves_within_facet() -> None:
    child = {**VALID_VALUE, "value": "child", "parent": "simplicity"}
    assert _validate_facets(_facets(VALID_VALUE, child)) == []


def test_parent_not_found_in_facet() -> None:
    child = {**VALID_VALUE, "value": "child", "parent": "does-not-exist"}
    errors = _validate_facets(_facets(child))
    assert any("not found in this facet" in e for e in errors)


def test_parent_cannot_reference_itself() -> None:
    self_parent = {**VALID_VALUE, "parent": "simplicity"}
    errors = _validate_facets(_facets(self_parent))
    assert any("cannot reference itself" in e for e in errors)


def test_parent_cycle_detected() -> None:
    a = {**VALID_VALUE, "value": "a", "parent": "b"}
    b = {**VALID_VALUE, "value": "b", "parent": "a"}
    errors = _validate_parents("facets.principle", {"a": a, "b": b})
    assert any("parent cycle" in e for e in errors)


def test_main_validates_the_real_seed_taxonomy_file() -> None:
    real_file = Path(__file__).parent.parent / "conventions" / "seed-taxonomy.yaml"
    rc = main([str(real_file)])
    assert rc == 0


def test_main_missing_file_errors() -> None:
    rc = main(["conventions/does-not-exist.yaml"])
    assert rc == 1


def test_main_invalid_yaml_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("facets: [this is not\n  valid: yaml: at all")
    rc = main([str(bad)])
    assert rc == 1


def test_main_multiple_files(tmp_path: Path) -> None:
    good = tmp_path / "good.yaml"
    good.write_text(
        "facets:\n"
        "  principle:\n"
        "    description: d\n"
        "    values:\n"
        "      - value: simplicity\n"
        "        description: d\n"
        "        provenance: seeded\n"
        "        source: s\n"
    )
    missing = tmp_path / "missing.yaml"

    rc = main([str(good), str(missing)])

    assert rc == 1
