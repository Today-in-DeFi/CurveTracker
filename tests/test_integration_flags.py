"""Tests for the tri-state --stakedao/--beefy/--convex flags.

These were store_true, so an unset flag and an explicit "off" were both
False. add_pool only writes a flag when it is not None, so "false" could
never be recorded from the CLI -- it had to be hand-edited into pools.json.
"""

import curve_tracker


def parse(argv):
    """Parse args the way main() does, without running the tracker."""
    import argparse

    parser = argparse.ArgumentParser()
    for name in ('stakedao', 'beefy', 'convex'):
        parser.add_argument(f'--{name}', action=argparse.BooleanOptionalAction,
                            default=None)
    return parser.parse_args(argv)


class TestTriState:
    def test_unset_is_none(self):
        assert parse([]).stakedao is None

    def test_flag_is_true(self):
        assert parse(['--stakedao']).stakedao is True

    def test_negated_flag_is_false(self):
        """The case store_true could not express."""
        assert parse(['--no-stakedao']).stakedao is False

    def test_flags_are_independent(self):
        args = parse(['--stakedao', '--no-beefy'])
        assert (args.stakedao, args.beefy, args.convex) == (True, False, None)


class TestRealParserAcceptsNegation:
    """Guards against the real CLI drifting from the helper above."""

    def test_cli_help_lists_no_variants(self):
        import subprocess
        import sys
        from pathlib import Path

        root = Path(curve_tracker.__file__).parent
        out = subprocess.run(
            [sys.executable, "curve_tracker.py", "--help"],
            cwd=root, capture_output=True, text=True, timeout=60,
        ).stdout
        for name in ('--no-stakedao', '--no-beefy', '--no-convex'):
            assert name in out, f"{name} missing from CLI"


class TestAddPoolRecordsFalse:
    """add_pool writes a flag only when it is not None."""

    def test_false_is_written(self, tmp_path):
        from pool_manager import PoolManager

        config = tmp_path / "pools.json"
        config.write_text('{"pools": []}')
        manager = PoolManager(str(config))
        manager.add_pool(chain="ethereum", pool="0xabc", comment="t",
                         beefy_enabled=False, validate=False)

        entry = manager.list_pools()[0]
        assert entry["beefy_enabled"] is False

    def test_none_is_omitted(self, tmp_path):
        from pool_manager import PoolManager

        config = tmp_path / "pools.json"
        config.write_text('{"pools": []}')
        manager = PoolManager(str(config))
        manager.add_pool(chain="ethereum", pool="0xabc", comment="t",
                         beefy_enabled=None, validate=False)

        assert "beefy_enabled" not in manager.list_pools()[0]
