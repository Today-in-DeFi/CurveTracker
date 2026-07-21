"""Tests for the Google Sheets auto-export guard.

A targeted `--pool` run used to auto-export whenever credentials were on
disk. Export replaces a tab's whole contents, so a one-pool query silently
replaced the full tab with a single row. Auto-export now requires that the
run covered a full pool config; --export-sheets still forces it.
"""

from curve_tracker import should_auto_export


class TestFullRunExports:
    def test_full_run_with_credentials_exports(self):
        assert should_auto_export(True, True, True)


class TestPartialRunDoesNotExport:
    def test_subset_run_never_auto_exports(self):
        assert not should_auto_export(False, True, True), (
            "a targeted run would replace the tab with a partial set"
        )


class TestPrerequisites:
    def test_missing_credentials_blocks_export(self):
        assert not should_auto_export(True, False, True)

    def test_unavailable_sheets_library_blocks_export(self):
        assert not should_auto_export(True, True, False)
