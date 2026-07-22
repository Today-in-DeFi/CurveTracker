"""Tests for find_pool_by_name direction.

The match used to be bidirectional: `name_lower in pool_name OR pool_name in
name_lower`. The second half let a pool named "a" match nearly any query,
and let a 42-char address that had fallen through from a failed address
lookup resolve to that pool -- returning the wrong pool's data under the
queried name, with no error.
"""

import pytest

from curve_tracker import CurveTracker


@pytest.fixture
def tracker_with_pools(monkeypatch):
    """A tracker whose chain cache is stubbed with a few named pools."""
    t = CurveTracker()
    pools = {
        'data': {
            'poolData': [
                {'name': 'a', 'address': '0xaaa0000000000000000000000000000000000000'},
                {'name': 'Curve.fi ETH/stETH', 'address': '0xdc24316b9ae028f1497c275eb9192a3ea0f67022'},
                {'name': 'BOLD/USDC Pool', 'address': '0xefc6516323fbd28e80b85a497b65a86243a54b3e'},
            ]
        }
    }
    monkeypatch.setattr(t, '_load_chain_data', lambda chain: None)
    t._pools_cache['ethereum'] = pools
    return t


class TestForwardMatchStillWorks:
    def test_partial_name_query_matches(self, tracker_with_pools):
        pool = tracker_with_pools.find_pool_by_name('ethereum', 'steth')
        assert pool['name'] == 'Curve.fi ETH/stETH'

    def test_case_insensitive(self, tracker_with_pools):
        pool = tracker_with_pools.find_pool_by_name('ethereum', 'BOLD')
        assert pool['name'] == 'BOLD/USDC Pool'


class TestReverseMatchIsGone:
    def test_short_name_does_not_match_arbitrary_query(self, tracker_with_pools):
        """A pool named "a" must not swallow an unrelated query."""
        assert tracker_with_pools.find_pool_by_name('ethereum', 'nonexistent pool') is None

    def test_unknown_address_does_not_resolve_to_pool_a(self, tracker_with_pools):
        """The exact regression: a failed-lookup address must not name-match."""
        result = tracker_with_pools.find_pool_by_name(
            'ethereum', '0x000000000000000000000000000000000000dead')
        assert result is None

    def test_address_shaped_query_is_rejected_outright(self, tracker_with_pools):
        # Even an address that IS a real pool's address is not a name.
        result = tracker_with_pools.find_pool_by_name(
            'ethereum', '0xefc6516323fbd28e80b85a497b65a86243a54b3e')
        assert result is None


class TestNoMatch:
    def test_genuinely_absent_name_returns_none(self, tracker_with_pools):
        assert tracker_with_pools.find_pool_by_name('ethereum', 'wsteth/reth') is None

    def test_missing_chain_data_returns_none(self):
        t = CurveTracker()
        t._pools_cache['ethereum'] = {}
        assert t.find_pool_by_name('ethereum', 'steth') is None
