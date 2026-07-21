"""Tests for the data-quality exit code.

A degraded run used to exit 0, so cron reported success while writing
incomplete data. Exit 2 now means "ran to completion, but some data is
missing or was rejected", kept distinct from 1 (hard failure).
"""

from curve_tracker import EXIT_DATA_QUALITY


def test_data_quality_code_is_distinct_from_success_and_failure():
    assert EXIT_DATA_QUALITY not in (0, 1)


class TestSkippedPoolsAreReported:
    """The CLI reads exporter.last_skipped to decide its exit code, so the
    exporter must actually populate it."""

    def test_clean_append_reports_nothing_skipped(self, exporter, make_pool):
        exporter.append_to_history([make_pool()])
        assert exporter.last_skipped == []

    def test_rejected_pool_is_reported(self, exporter, make_pool):
        exporter.append_to_history([make_pool(tvl=float("nan"))])
        assert len(exporter.last_skipped) == 1
        name, reasons = exporter.last_skipped[0]
        assert name == "reUSD/scrvUSD"
        assert reasons

    def test_report_resets_between_runs(self, exporter, make_pool):
        exporter.append_to_history([make_pool(tvl=float("nan"))])
        assert exporter.last_skipped
        exporter.append_to_history([make_pool()])
        assert exporter.last_skipped == [], "stale skips would fail every later run"

    def test_outage_snapshot_is_reported_as_skipped(self, exporter, make_pool):
        exporter.append_to_history([make_pool(tvl=5_000_000)])
        exporter.append_to_history([make_pool(tvl=0)], degraded_sources=["Curve"])
        assert len(exporter.last_skipped) == 1
