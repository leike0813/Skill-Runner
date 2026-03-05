from server.services.platform.run_file_filter_service import (
    RunFileFilterService,
)


def test_non_debug_allowlist_is_explicit_only():
    service = RunFileFilterService()
    assert service.include_in_non_debug_bundle("result/result.json") is True
    assert service.include_in_non_debug_bundle("artifacts/report.txt") is True
    assert service.include_in_non_debug_bundle(".audit/stdout.1.log") is False
    assert service.include_in_non_debug_bundle("uploads/input.txt") is False


def test_debug_denylist_filters_node_modules():
    service = RunFileFilterService()
    assert service.include_in_debug_bundle("workspace/node_modules/pkg/index.js") is False
    assert service.include_in_debug_bundle("node_modules/pkg/index.js") is False
    assert service.include_in_debug_bundle("artifacts/report.txt") is True


def test_run_explorer_path_rejects_filtered_ancestors():
    service = RunFileFilterService()
    assert service.path_allowed_for_run_explorer("workspace/node_modules/pkg/index.js") is False
    assert service.path_allowed_for_run_explorer("artifacts/result.txt") is True
