"""TST-001: StableRef parse, stringify, validation tests."""

import pytest

from contexta.common.errors import ValidationError
from contexta.contract.refs import (
    CORE_STABLE_REF_COMPONENT_COUNTS,
    CORE_STABLE_REF_KINDS,
    StableRef,
    validate_core_stable_ref,
    validate_stable_ref_field,
    validate_stable_ref_kind,
)


# ---------------------------------------------------------------------------
# StableRef construction
# ---------------------------------------------------------------------------

class TestStableRefConstruct:
    def test_valid_kind_and_value(self):
        ref = StableRef(kind="project", value="my-proj")
        assert ref.kind == "project"
        assert ref.value == "my-proj"

    def test_text_property(self):
        ref = StableRef(kind="run", value="my-proj.run-01")
        assert ref.text == "run:my-proj.run-01"

    def test_str_is_text(self):
        ref = StableRef(kind="project", value="my-proj")
        assert str(ref) == "project:my-proj"

    def test_components_split_on_dot(self):
        ref = StableRef(kind="run", value="proj.run-01")
        assert ref.components == ("proj", "run-01")

    def test_to_dict(self):
        ref = StableRef(kind="project", value="my-proj")
        d = ref.to_dict()
        assert d == {"kind": "project", "value": "my-proj"}

    def test_frozen_immutable(self):
        ref = StableRef(kind="project", value="my-proj")
        with pytest.raises((AttributeError, TypeError)):
            ref.kind = "run"  # type: ignore[misc]

    def test_multi_component_value(self):
        ref = StableRef(kind="stage", value="my-proj.run-01.train")
        assert len(ref.components) == 3


# ---------------------------------------------------------------------------
# StableRef.parse
# ---------------------------------------------------------------------------

class TestStableRefParse:
    def test_parse_valid(self):
        ref = StableRef.parse("project:my-proj")
        assert ref.kind == "project"
        assert ref.value == "my-proj"

    def test_parse_multi_component(self):
        ref = StableRef.parse("run:my-proj.run-01")
        assert ref.components == ("my-proj", "run-01")

    def test_parse_rejects_no_colon(self):
        with pytest.raises(ValidationError, match="one ':'"):
            StableRef.parse("projectmy-proj")

    def test_parse_rejects_multiple_colons(self):
        with pytest.raises(ValidationError):
            StableRef.parse("project:a:b")

    def test_parse_rejects_non_string(self):
        with pytest.raises(ValidationError):
            StableRef.parse(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Kind validation
# ---------------------------------------------------------------------------

class TestStableRefKindValidation:
    def test_invalid_kind_blank(self):
        with pytest.raises(ValidationError, match="blank"):
            StableRef(kind="", value="val")

    def test_invalid_kind_uppercase(self):
        with pytest.raises(ValidationError):
            StableRef(kind="Project", value="val")

    def test_invalid_kind_starts_with_digit(self):
        with pytest.raises(ValidationError):
            StableRef(kind="1project", value="val")

    def test_kind_with_underscore_allowed(self):
        ref = StableRef(kind="my_kind", value="val")
        assert ref.kind == "my_kind"


# ---------------------------------------------------------------------------
# Value validation
# ---------------------------------------------------------------------------

class TestStableRefValueValidation:
    def test_invalid_value_blank(self):
        with pytest.raises(ValidationError):
            StableRef(kind="project", value="")

    def test_invalid_value_with_space(self):
        with pytest.raises(ValidationError):
            StableRef(kind="project", value="my proj")

    def test_invalid_value_with_underscore(self):
        with pytest.raises(ValidationError):
            StableRef(kind="project", value="my_proj")

    def test_invalid_value_double_dot(self):
        with pytest.raises(ValidationError):
            StableRef(kind="project", value="a..b")

    def test_invalid_value_leading_dot(self):
        with pytest.raises(ValidationError):
            StableRef(kind="project", value=".abc")

    def test_component_too_long(self):
        long_component = "a" * 64
        with pytest.raises(ValidationError):
            StableRef(kind="project", value=long_component)


# ---------------------------------------------------------------------------
# validate_core_stable_ref
# ---------------------------------------------------------------------------

class TestValidateCoreStableRef:
    def test_project_one_component(self):
        ref = StableRef(kind="project", value="my-proj")
        result = validate_core_stable_ref(ref)
        assert result is ref

    def test_run_two_components(self):
        ref = StableRef(kind="run", value="my-proj.run-01")
        validate_core_stable_ref(ref)  # no exception

    def test_project_two_components_fails(self):
        ref = StableRef(kind="project", value="my-proj.extra")
        with pytest.raises(ValidationError, match="expects 1"):
            validate_core_stable_ref(ref)

    def test_non_core_kind_passes_through(self):
        ref = StableRef(kind="custom", value="some.value")
        result = validate_core_stable_ref(ref)
        assert result is ref


# ---------------------------------------------------------------------------
# validate_stable_ref_kind
# ---------------------------------------------------------------------------

class TestValidateStableRefKind:
    def test_matching_kind(self):
        ref = StableRef(kind="project", value="my-proj")
        validate_stable_ref_kind(ref, "project", field_name="project_ref")

    def test_wrong_kind_raises(self):
        ref = StableRef(kind="run", value="my-proj.run-01")
        with pytest.raises(ValidationError, match="mismatch"):
            validate_stable_ref_kind(ref, "project", field_name="project_ref")

    def test_sequence_of_allowed_kinds(self):
        ref = StableRef(kind="artifact", value="my-proj.run-01.model")
        validate_stable_ref_kind(ref, ("artifact", "record"), field_name="subject_ref")


# ---------------------------------------------------------------------------
# validate_stable_ref_field
# ---------------------------------------------------------------------------

class TestValidateStableRefField:
    def test_project_ref_field(self):
        ref = StableRef(kind="project", value="my-proj")
        validate_stable_ref_field(ref, "project_ref")

    def test_run_ref_field(self):
        ref = StableRef(kind="run", value="my-proj.run-01")
        validate_stable_ref_field(ref, "run_ref")

    def test_unknown_field_raises(self):
        ref = StableRef(kind="project", value="my-proj")
        with pytest.raises(ValidationError, match="Unknown"):
            validate_stable_ref_field(ref, "nonexistent_field")

    def test_field_kind_mismatch_raises(self):
        ref = StableRef(kind="run", value="my-proj.run-01")
        with pytest.raises(ValidationError):
            validate_stable_ref_field(ref, "project_ref")
