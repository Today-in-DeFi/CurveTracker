"""Tests for history-file integrity.

A truncated history file used to be replaced with an empty structure, then
reported as `✅ Updated history` at exit 0 -- months of append-only data
gone permanently, from a single killed run. Writes are now atomic so the
truncation is far less likely, and an unreadable file is a hard stop rather
than a reason to start over.
"""

import json
import os

import pytest

from json_exporter import CurveDataExporter, HistoryCorruptedError, _atomic_write_json


@pytest.fixture
def exporter_dir(tmp_path):
    return CurveDataExporter(output_dir=str(tmp_path / "data"))


def history_path(exporter):
    return os.path.join(exporter.output_dir, "curve_pools_history.json")


class TestCorruptHistoryIsNotDestroyed:
    def test_corrupt_history_raises_instead_of_wiping(self, exporter_dir, make_pool):
        path = history_path(exporter_dir)
        with open(path, "w") as f:
            f.write('{"pools": {"a": {"snapshots": [1,2,3]')  # truncated

        with pytest.raises(HistoryCorruptedError):
            exporter_dir.append_to_history([make_pool()])

    def test_corrupt_history_contents_are_preserved(self, exporter_dir, make_pool):
        """The bytes must survive somewhere -- they are unrecoverable otherwise."""
        path = history_path(exporter_dir)
        truncated = '{"pools": {"a": {"snapshots": [1,2,3]'
        with open(path, "w") as f:
            f.write(truncated)

        with pytest.raises(HistoryCorruptedError):
            exporter_dir.append_to_history([make_pool()])

        quarantined = [p for p in os.listdir(exporter_dir.output_dir)
                       if ".corrupt_" in p]
        assert len(quarantined) == 1
        with open(os.path.join(exporter_dir.output_dir, quarantined[0])) as f:
            assert f.read() == truncated

    def test_valid_history_still_appends(self, exporter_dir, make_pool):
        exporter_dir.append_to_history([make_pool()])
        exporter_dir.append_to_history([make_pool()])

        with open(history_path(exporter_dir)) as f:
            history = json.load(f)
        snapshots = next(iter(history["pools"].values()))["snapshots"]
        assert len(snapshots) == 2

    def test_missing_history_is_created_normally(self, exporter_dir, make_pool):
        """Absent is not corrupt -- a first run must still work."""
        exporter_dir.append_to_history([make_pool()])
        assert os.path.exists(history_path(exporter_dir))


class TestAtomicWrite:
    def test_contents_are_written(self, tmp_path):
        target = str(tmp_path / "out.json")
        _atomic_write_json(target, {"a": 1})
        with open(target) as f:
            assert json.load(f) == {"a": 1}

    def test_existing_file_survives_a_failed_write(self, tmp_path, monkeypatch):
        """A crash mid-write must leave the old file intact, not truncated."""
        target = str(tmp_path / "out.json")
        _atomic_write_json(target, {"original": True})

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("json_exporter.json.dump", boom)
        with pytest.raises(OSError):
            _atomic_write_json(target, {"replacement": True})

        with open(target) as f:
            assert json.load(f) == {"original": True}

    def test_no_temp_files_are_left_behind(self, tmp_path, monkeypatch):
        target = str(tmp_path / "out.json")

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("json_exporter.json.dump", boom)
        with pytest.raises(OSError):
            _atomic_write_json(target, {"a": 1})

        assert [p for p in os.listdir(tmp_path) if p.startswith(".tmp_")] == []
