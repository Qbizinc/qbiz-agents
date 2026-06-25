"""Gate 1 — Component 2, Output Validator.

Covers the mechanical output checks: format/schema, hallucinated-tool detection against the
per-agent allowlist, and out-of-scope system references. Also exercises both partial-output
policies — `validate_output` (reject-and-re-prompt, raises) and `inspect_output` (strip-and-log,
returns violations).
"""

import pytest

from qbiz_harness import (
    OutputRejectedError,
    ValidationResult,
    check_format,
    check_scope,
    check_tool_calls,
    inspect_output,
    validate_output,
)


# --- format / schema -------------------------------------------------------------------------


def test_check_format_accepts_matching_object():
    schema = {"summary": str, "count": int}
    assert check_format({"summary": "ok", "count": 3}, schema) == []


def test_check_format_parses_json_string():
    schema = {"summary": str}
    assert check_format('{"summary": "ok"}', schema) == []


def test_check_format_flags_invalid_json():
    result = check_format("not json{", {"summary": str})
    assert [v.kind for v in result] == ["format"]
    assert "not valid JSON" in result[0].detail


def test_check_format_flags_missing_and_mistyped_fields():
    schema = {"summary": str, "count": int}
    violations = check_format({"count": "three"}, schema)
    kinds_details = {v.detail for v in violations}
    assert any("missing required field 'summary'" in d for d in kinds_details)
    assert any("field 'count' is str, expected int" in d for d in kinds_details)


def test_check_format_rejects_bool_for_int_field():
    # bool is a subtype of int — a True slipping into an int field is a real bug, so flag it.
    violations = check_format({"count": True}, {"count": int})
    assert violations and "bool" in violations[0].detail


def test_check_format_flags_non_object_response():
    assert check_format("[1, 2, 3]", {"k": str})[0].detail.startswith("expected an object")


# --- hallucinated tool calls ----------------------------------------------------------------


def test_check_tool_calls_passes_allowed_tools():
    assert check_tool_calls(["send_message"], {"send_message", "add_reaction"}) == []


def test_check_tool_calls_flags_tool_outside_allowlist():
    violations = check_tool_calls(["delete_everything"], {"send_message"})
    assert [v.kind for v in violations] == ["hallucinated_tool"]
    assert "delete_everything" in violations[0].detail


# --- out-of-scope systems -------------------------------------------------------------------


def test_check_scope_flags_unpermitted_system():
    violations = check_scope(["prod_db"], {"staging_db"})
    assert [v.kind for v in violations] == ["out_of_scope"]
    assert "prod_db" in violations[0].detail


# --- opt-in: only the checks the caller supplies data for run --------------------------------


def test_inspect_runs_only_opted_in_checks():
    # No schema, no systems given → only the tool check runs, and it passes.
    result = inspect_output(
        {"anything": "goes"},
        requested_tools=["send_message"],
        allowed_tools={"send_message"},
    )
    assert isinstance(result, ValidationResult)
    assert result.ok


def test_tool_check_skipped_when_allowlist_absent():
    # requested_tools given but no allowlist → caller didn't opt in, so nothing is flagged.
    assert inspect_output({}, requested_tools=["mystery_tool"]).ok


# --- partial-output policy: the two call-site behaviours -------------------------------------


def test_validate_output_raises_on_violation_for_reprompt():
    with pytest.raises(OutputRejectedError) as exc:
        validate_output(
            {"count": "three"},
            expected_schema={"count": int},
            requested_tools=["nope"],
            allowed_tools={"send_message"},
        )
    msg = str(exc.value)
    assert "format" in msg and "hallucinated_tool" in msg  # both violations summarised


def test_validate_output_returns_response_when_clean():
    payload = {"summary": "all good"}
    assert validate_output(payload, expected_schema={"summary": str}) is payload


def test_inspect_output_collects_all_violations_for_strip_and_log():
    result = inspect_output(
        {"count": "three"},
        expected_schema={"count": int},
        requested_tools=["rogue_tool"],
        allowed_tools={"send_message"},
        referenced_systems=["prod_db"],
        permitted_systems={"staging_db"},
    )
    assert not result.ok
    assert {v.kind for v in result.violations} == {"format", "hallucinated_tool", "out_of_scope"}
