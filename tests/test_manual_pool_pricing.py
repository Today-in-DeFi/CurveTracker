"""Tests for the manual-pool pricing integration in get_pool_data.

The regression these guard: a non-$1 coin priced at $1, producing a
plausible-but-understated TVL with no signal. And the fail-loud contract:
if a declared price cannot be resolved, the pool must not fall back to the
naive amount-sum.
"""

import pytest

import curve_tracker
from curve_tracker import CurveTracker


class StubPrices:
    def __init__(self, table, fail=False):
        self.table = table
        self.fail = fail

    def get_price(self, peg_key, now=None):
        if self.fail or peg_key not in self.table:
            from pegtracker_prices import PriceUnavailable
            raise PriceUnavailable(f"stub: {peg_key}")
        return self.table[peg_key]


@pytest.fixture
def tracker(monkeypatch):
    t = CurveTracker()

    # Stub the chain fetcher so no network is touched: 1.0 USDT (6dp) and
    # 1.0 sUSDe (18dp).
    class FakeFetcher:
        def get_pool_data(self, address, tokens):
            return {
                'tvl': 2.0,  # the naive amount-sum; must NOT be used
                'balances': [1.0, 1.0],
                'coin_amounts': [10 ** 6, 10 ** 18],
            }

    monkeypatch.setattr(curve_tracker, 'get_plasma_fetcher', lambda: FakeFetcher())
    monkeypatch.setattr(curve_tracker, 'PLASMA_ONCHAIN_AVAILABLE', True)
    # Skip all the API-backed enrichment; we only care about TVL/pricing.
    monkeypatch.setattr(t, 'get_pool_apy_data', lambda *a, **k: {})
    monkeypatch.setattr(t, 'get_pool_volume_data', lambda *a, **k: {})
    monkeypatch.setattr(t, 'get_gauge_rewards', lambda *a, **k: {})
    monkeypatch.setattr(t, '_enrich_rewards_with_expiry', lambda chain, r: r)
    return t


SUSDE_POOL = '0x1e8d78e9b3f0152d54d32904b7933f1cfe439df1'


class TestPricedCorrectly:
    def test_susde_valued_above_one_dollar(self, tracker, monkeypatch):
        monkeypatch.setattr('pegtracker_prices.get_prices',
                            lambda: StubPrices({'sUSDe': 1.24}))
        pool = tracker.get_pool_data('plasma', SUSDE_POOL)

        # 1 USDT @ $1 + 1 sUSDe @ $1.24
        assert pool.tvl == pytest.approx(2.24)
        assert pool.coin_prices == pytest.approx([1.0, 1.24])
        assert 'PegTrackerPrices' not in tracker.degraded_sources()

    def test_naive_amount_sum_is_not_used(self, tracker, monkeypatch):
        """The fetcher offered tvl=2.0; the priced value must win."""
        monkeypatch.setattr('pegtracker_prices.get_prices',
                            lambda: StubPrices({'sUSDe': 1.24}))
        pool = tracker.get_pool_data('plasma', SUSDE_POOL)
        assert pool.tvl != 2.0


class TestFailsLoud:
    def test_unpriceable_coin_refuses_tvl_and_degrades(self, tracker, monkeypatch):
        monkeypatch.setattr('pegtracker_prices.get_prices',
                            lambda: StubPrices({}, fail=True))
        pool = tracker.get_pool_data('plasma', SUSDE_POOL)

        # Must NOT be the plausible ~$2 amount-sum, must be 0 and degraded.
        assert pool.tvl == 0
        assert 'PegTrackerPrices' in tracker.degraded_sources()
