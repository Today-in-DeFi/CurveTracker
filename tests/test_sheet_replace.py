"""Tests for the replace path in GoogleSheetsExporter.export_to_sheets.

Covers the wiring, not just the pure predicate: that a guarded replace
actually skips worksheet.clear(), that a normal full run is untouched, and
that refusals are reported so the caller can set a non-zero exit code.
"""

import pytest

import curve_tracker
from curve_tracker import GoogleSheetsExporter


class FakeWorksheet:
    def __init__(self, existing_rows):
        # +1 for the header row the real sheet carries.
        self._values = [["header"]] + [["x"]] * existing_rows
        self.cleared = False
        self.written = None

    def get_all_values(self):
        return self._values

    def clear(self):
        self.cleared = True


class FakeSpreadsheet:
    title = "Curve Pool Tracker"


@pytest.fixture
def exporter_with(monkeypatch):
    """Build an exporter whose sheet I/O is stubbed out."""

    def _build(existing_rows):
        exporter = GoogleSheetsExporter.__new__(GoogleSheetsExporter)
        exporter.credentials_file = None
        exporter.last_refused_replaces = []

        worksheet = FakeWorksheet(existing_rows)
        monkeypatch.setattr(exporter, "get_client", lambda: _FakeClient(), raising=False)
        monkeypatch.setattr(
            GoogleSheetsExporter, "get_or_create_worksheet",
            lambda self, ss, name, max_coins=2: worksheet,
        )
        monkeypatch.setattr(
            curve_tracker, "set_with_dataframe",
            lambda ws, df, include_index=False: setattr(ws, "written", len(df)),
        )
        return exporter, worksheet

    return _build


class _FakeClient:
    def open(self, name):
        return FakeSpreadsheet()

    def open_by_key(self, key):
        return FakeSpreadsheet()


def pools(make_pool, n):
    return [make_pool(address=f"0x{i:040x}") for i in range(n)]


class TestGuardBlocksTruncation:
    def test_one_pool_over_a_full_tab_is_refused(self, exporter_with, make_pool):
        exporter, ws = exporter_with(existing_rows=16)
        exporter.export_to_sheets(pools(make_pool, 1), append_data=False)

        assert not ws.cleared, "clear() is unrecoverable; must not run"
        assert ws.written is None
        assert exporter.last_refused_replaces == [("Ethereum USD", 16, 1)]

    def test_force_replace_overrides_the_guard(self, exporter_with, make_pool):
        exporter, ws = exporter_with(existing_rows=16)
        exporter.export_to_sheets(pools(make_pool, 1), append_data=False,
                                  force_replace=True)

        assert ws.cleared
        assert ws.written == 1
        assert exporter.last_refused_replaces == []


class TestNormalRunIsUnaffected:
    def test_full_run_replaces_as_before(self, exporter_with, make_pool):
        """The cron path: same-size replace must still go through."""
        exporter, ws = exporter_with(existing_rows=16)
        exporter.export_to_sheets(pools(make_pool, 16), append_data=False)

        assert ws.cleared
        assert ws.written == 16
        assert exporter.last_refused_replaces == []

    def test_first_write_to_empty_tab_succeeds(self, exporter_with, make_pool):
        exporter, ws = exporter_with(existing_rows=0)
        exporter.export_to_sheets(pools(make_pool, 3), append_data=False)

        assert ws.cleared
        assert ws.written == 3


class TestRefusalsResetBetweenRuns:
    def test_stale_refusals_do_not_persist(self, exporter_with, make_pool):
        exporter, _ = exporter_with(existing_rows=16)
        exporter.export_to_sheets(pools(make_pool, 1), append_data=False)
        assert exporter.last_refused_replaces

        exporter.export_to_sheets(pools(make_pool, 16), append_data=False)
        assert exporter.last_refused_replaces == [], (
            "stale refusals would fail every later run"
        )
