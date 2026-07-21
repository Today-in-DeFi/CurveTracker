"""Tests for the pre-write sanity gate.

The history file is append-only, so anything this gate lets through is
permanent. These tests pin both directions: that bad values are rejected,
and — just as important — that legitimate edge cases are not.
"""

import json

import pytest

from json_exporter import MAX_PLAUSIBLE_APY, MAX_PLAUSIBLE_TVL, check_pool_sanity


class TestRejectsBadValues:
    def test_nan_tvl_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(tvl=float("nan")))
        assert any("nan" in p for p in problems)

    def test_infinite_apy_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(beefy_apy=float("inf")))
        assert any("beefy_apy" in p for p in problems)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("tvl", -1.0),
            ("stakedao_tvl", -1.0),
            ("beefy_tvl", -1.0),
            ("convex_tvl", -100.0),
            # Curve's base APY is derived from trading fees and cannot go
            # negative; a negative one means something upstream is wrong.
            ("base_apy", -3.0),
        ],
    )
    def test_negative_values_are_rejected(self, make_pool, field, value):
        problems = check_pool_sanity(make_pool(**{field: value}))
        assert any(field in p and "negative" in p for p in problems)

    @pytest.mark.parametrize("field", ["stakedao_apy", "beefy_apy", "convex_apy"])
    def test_large_negative_integration_apy_still_bounded(self, make_pool, field):
        problems = check_pool_sanity(make_pool(**{field: -MAX_PLAUSIBLE_APY * 2}))
        assert any("exceeds plausible maximum" in p for p in problems)

    def test_absurd_tvl_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(tvl=MAX_PLAUSIBLE_TVL * 2))
        assert any("exceeds plausible maximum" in p for p in problems)

    def test_absurd_apy_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(base_apy=MAX_PLAUSIBLE_APY + 1))
        assert any("exceeds plausible maximum" in p for p in problems)

    def test_non_numeric_tvl_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(tvl="1000000"))
        assert any("not numeric" in p for p in problems)

    def test_bool_is_not_accepted_as_a_number(self, make_pool):
        # bool is a subclass of int in Python; True must not read as TVL 1.
        problems = check_pool_sanity(make_pool(tvl=True))
        assert any("not numeric" in p for p in problems)

    def test_reports_every_problem_not_just_the_first(self, make_pool):
        problems = check_pool_sanity(make_pool(tvl=-1.0, base_apy=float("nan")))
        assert len(problems) >= 2


class TestOutageSignature:
    """The specific failure this gate exists to catch: an upstream outage
    coalescing every field to zero, indistinguishable from real data."""

    def test_tvl_dropping_to_exactly_zero_is_rejected(self, make_pool):
        problems = check_pool_sanity(make_pool(tvl=0), {"tvl": 5_000_000})
        assert any("upstream failure" in p for p in problems)

    def test_zero_tvl_is_allowed_when_pool_has_no_history(self, make_pool):
        # A newly tracked pool legitimately has no prior snapshot.
        assert check_pool_sanity(make_pool(tvl=0), None) == []

    def test_zero_tvl_is_allowed_when_previous_was_also_zero(self, make_pool):
        # An already-empty pool staying empty is real data, not an outage.
        assert check_pool_sanity(make_pool(tvl=0), {"tvl": 0}) == []


class TestAllowsLegitimateData:
    def test_healthy_pool_passes(self, make_pool):
        assert check_pool_sanity(make_pool()) == []

    def test_large_but_real_drop_passes(self, make_pool):
        # 5M -> 1k is a 99.98% drop. Real drains happen; only an exact zero
        # is treated as the outage signature.
        assert check_pool_sanity(make_pool(tvl=1000.0), {"tvl": 5_000_000}) == []

    def test_zero_apy_passes(self, make_pool):
        # A pool with no trading fees genuinely has 0% base APY.
        assert check_pool_sanity(make_pool(base_apy=0.0)) == []

    def test_absent_integrations_pass(self, make_pool):
        # None means "not integrated", which is not a validation failure.
        pool = make_pool(stakedao_apy=None, beefy_apy=None, convex_apy=None)
        assert check_pool_sanity(pool) == []

    @pytest.mark.parametrize("field", ["stakedao_apy", "beefy_apy", "convex_apy"])
    def test_negative_integration_apy_passes(self, make_pool, field):
        # Beefy reports genuinely negative APYs for underwater strategies
        # (26 across its vaults as of writing). Dropping them would lose
        # real data, so only TVL and fee-derived base_apy must be positive.
        assert check_pool_sanity(make_pool(**{field: -12.5})) == []


class TestGateIsEnforcedOnWrite:
    """The checker is only useful if append_to_history actually calls it."""

    def _snapshot_count(self, path, pool_id):
        with open(path) as f:
            return len(json.load(f)["pools"][pool_id]["snapshots"])

    def test_outage_snapshot_is_not_written_to_history(self, exporter, make_pool):
        healthy = make_pool(tvl=5_000_000)
        path = exporter.append_to_history([healthy])
        pool_id = exporter._generate_pool_id(healthy)
        assert self._snapshot_count(path, pool_id) == 1

        exporter.append_to_history([make_pool(tvl=0)], degraded_sources=["Curve"])
        assert self._snapshot_count(path, pool_id) == 1, "outage zeros reached history"

    def test_healthy_snapshot_is_written(self, exporter, make_pool):
        pool = make_pool()
        exporter.append_to_history([pool])
        path = exporter.append_to_history([pool])
        assert self._snapshot_count(path, exporter._generate_pool_id(pool)) == 2

    def test_one_bad_pool_does_not_block_the_others(self, exporter, make_pool):
        good = make_pool(name="good_pool")
        bad = make_pool(name="bad_pool", tvl=float("nan"))
        path = exporter.append_to_history([good, bad])
        with open(path) as f:
            history = json.load(f)
        assert exporter._generate_pool_id(good) in history["pools"]
        assert history["pools"][exporter._generate_pool_id(bad)]["snapshots"] == []


class TestDegradedSourcesMetadata:
    def test_clean_run_records_empty_list(self, exporter, make_pool):
        path = exporter.export_to_json([make_pool()])
        with open(path) as f:
            assert json.load(f)["metadata"]["degraded_sources"] == []

    def test_degraded_run_records_the_failed_sources(self, exporter, make_pool):
        path = exporter.export_to_json(
            [make_pool()], degraded_sources=["StakeDAO", "Curve"]
        )
        with open(path) as f:
            assert json.load(f)["metadata"]["degraded_sources"] == ["Curve", "StakeDAO"]
