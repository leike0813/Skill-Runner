from __future__ import annotations

from typing import Any, Mapping, Sequence


def _is_mapping_subset(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in actual:
            return False
        actual_value = actual[key]
        if isinstance(expected_value, Mapping):
            if not isinstance(actual_value, Mapping):
                return False
            if not _is_mapping_subset(expected_value, actual_value):
                return False
        elif isinstance(expected_value, list):
            if not isinstance(actual_value, list):
                return False
            if expected_value != actual_value:
                return False
        else:
            if actual_value != expected_value:
                return False
    return True


def assert_event_subsequence(
    actual_events: Sequence[Mapping[str, Any]],
    expected_events: Sequence[Mapping[str, Any]],
) -> None:
    cursor = 0
    for expected in expected_events:
        matched = False
        while cursor < len(actual_events):
            if _is_mapping_subset(expected, actual_events[cursor]):
                matched = True
                cursor += 1
                break
            cursor += 1
        if not matched:
            raise AssertionError(f"Expected event subsequence item not found: {expected!r}")


def assert_event_types_absent(
    actual_events: Sequence[Mapping[str, Any]],
    absent_types: Sequence[str],
) -> None:
    actual_types = {str(event.get("type")) for event in actual_events}
    for type_name in absent_types:
        if type_name in actual_types:
            raise AssertionError(f"Unexpected event type present: {type_name}")


def assert_diagnostics_match(
    actual_events: Sequence[Mapping[str, Any]],
    expected_diagnostics: Sequence[Mapping[str, Any]],
) -> None:
    diagnostics = [
        event
        for event in actual_events
        if str(event.get("type") or "") == "diagnostic.warning"
    ]
    for expected in expected_diagnostics:
        if not any(_is_mapping_subset(expected, actual) for actual in diagnostics):
            raise AssertionError(f"Expected diagnostic warning not found: {expected!r}")


def assert_outcome_semantics(
    actual_outcome: Mapping[str, Any],
    expected_outcome: Mapping[str, Any],
) -> None:
    if not _is_mapping_subset(expected_outcome, actual_outcome):
        raise AssertionError(
            "Outcome semantic assertion failed.\n"
            f"Expected subset: {expected_outcome!r}\n"
            f"Actual outcome: {actual_outcome!r}"
        )
