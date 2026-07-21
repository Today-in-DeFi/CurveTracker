"""Tests for reading extra gauge incentives from Curve's own API.

Extra rewards used to come from StakeDAO only, so an incentivised pool
without StakeDAO coverage silently reported none -- the incentive vanished
from the export entirely. Curve's `gaugeRewards` is now the primary source,
with StakeDAO kept as a fallback.
"""

from curve_tracker import parse_gauge_rewards


# Real getPools payload for BOLD/USDC on 2026-07-21: one live stream and one
# that lapsed 14 months earlier, which Curve still reports at apy 0.
BOLD_USDC = {
    'gaugeRewards': [
        {
            'gaugeAddress': '0x07a01471fa544d9c6531b631e6a96a79a9ad05e9',
            'symbol': 'BOLD',
            'tokenAddress': '0x6440f144b7e50D6a8439336510312d2F54beB01D',
            'apy': 6.474156406998594,
        },
        {
            'gaugeAddress': '0x07a01471fa544d9c6531b631e6a96a79a9ad05e9',
            'symbol': 'LUSD',
            'tokenAddress': '0x5f98805A4E8be255a32880FDeC7F6728C6568bA0',
            'apy': 0,
        },
    ]
}


class TestLiveStreams:
    def test_live_stream_is_read_from_curve(self):
        rewards = parse_gauge_rewards(BOLD_USDC)
        bold = next(r for r in rewards if r['token'] == 'BOLD')
        assert bold['apy'] == 6.474156406998594
        assert bold['active'] is True
        assert bold['source'] == 'curve_gauge'

    def test_addresses_are_carried_through(self):
        bold = parse_gauge_rewards(BOLD_USDC)[0]
        assert bold['gauge_address'] == '0x07a01471fa544d9c6531b631e6a96a79a9ad05e9'
        assert bold['token_address'] == '0x6440f144b7e50D6a8439336510312d2F54beB01D'


class TestExpiredStreams:
    def test_dead_stream_is_kept_not_dropped(self):
        """"Incentive ended" must be distinguishable from "never had one"."""
        rewards = parse_gauge_rewards(BOLD_USDC)
        lusd = next(r for r in rewards if r['token'] == 'LUSD')
        assert lusd['active'] is False
        assert lusd['apy'] == 0

    def test_both_streams_are_present(self):
        assert len(parse_gauge_rewards(BOLD_USDC)) == 2


class TestMalformedInput:
    def test_missing_key_yields_nothing(self):
        assert parse_gauge_rewards({}) == []

    def test_null_gauge_rewards_yields_nothing(self):
        assert parse_gauge_rewards({'gaugeRewards': None}) == []

    def test_entries_without_a_symbol_are_skipped(self):
        assert parse_gauge_rewards({'gaugeRewards': [{'apy': 5.0}]}) == []

    def test_non_numeric_apy_is_skipped_not_zeroed(self):
        """Coercing a bad apy to 0 would read as an expired stream."""
        assert parse_gauge_rewards(
            {'gaugeRewards': [{'symbol': 'X', 'apy': 'oops'}]}
        ) == []

    def test_null_apy_is_treated_as_inactive(self):
        rewards = parse_gauge_rewards({'gaugeRewards': [{'symbol': 'X', 'apy': None}]})
        assert rewards[0]['active'] is False

    def test_non_dict_entries_are_skipped(self):
        assert parse_gauge_rewards({'gaugeRewards': ['junk', None]}) == []
