"""Tests for pricing on-chain pool TVL from PegTracker.

The chain fetchers read token amounts only, so TVL was summed as if every
token were $1 -- understating any pool holding a yield-bearing token like
sUSDe (~$1.24). Prices now come from PegTracker, bound by an explicit
peg_key, and a price that cannot be resolved fails loudly rather than
leaving a plausible $1.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from pegtracker_prices import PegTrackerPrices, PriceUnavailable


NOW = datetime(2026, 7, 22, 1, 0, 0, tzinfo=timezone.utc)


def write_feed(tmp_path, entries, last_updated=None):
    feed = dict(entries)
    feed['last_updated'] = last_updated or NOW.strftime('%Y-%m-%dT%H:%M:%SZ')
    path = tmp_path / "peg.json"
    path.write_text(json.dumps(feed))
    return str(path)


def entry(market=None, theoretical=None, ts=None):
    e = {}
    if market is not None:
        e['market_price'] = market
    if theoretical is not None:
        e['theoretical_price'] = theoretical
    e['timestamp'] = ts or NOW.strftime('%Y-%m-%dT%H:%M:%SZ')
    return e


class TestResolvesPrice:
    def test_market_price_is_used(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry(market=1.2397)})
        assert PegTrackerPrices(path).get_price('sUSDe', now=NOW) == 1.2397

    def test_nav_used_when_market_absent(self, tmp_path):
        """PegTracker publishes NAV for exactly the thin-market tokens."""
        path = write_feed(tmp_path, {'sUSDe': entry(theoretical=1.24)})
        assert PegTrackerPrices(path).get_price('sUSDe', now=NOW) == 1.24

    def test_market_preferred_over_nav(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry(market=1.23, theoretical=1.25)})
        assert PegTrackerPrices(path).get_price('sUSDe', now=NOW) == 1.23


class TestFailsLoud:
    def test_missing_key_raises(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry(market=1.0)})
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(path).get_price('nonexistent', now=NOW)

    def test_no_price_fields_raises(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry()})
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(path).get_price('sUSDe', now=NOW)

    def test_stale_price_raises_rather_than_trusting(self, tmp_path):
        old = (NOW - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%SZ')
        path = write_feed(tmp_path, {'sUSDe': entry(market=1.24, ts=old)})
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(path).get_price('sUSDe', now=NOW)

    def test_fresh_within_window_is_ok(self, tmp_path):
        recent = (NOW - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        path = write_feed(tmp_path, {'sUSDe': entry(market=1.24, ts=recent)})
        assert PegTrackerPrices(path).get_price('sUSDe', now=NOW) == 1.24

    def test_missing_feed_file_raises(self, tmp_path):
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(str(tmp_path / "absent.json")).get_price('sUSDe', now=NOW)

    def test_non_positive_price_raises(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry(market=0)})
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(path).get_price('sUSDe', now=NOW)

    def test_non_numeric_price_raises(self, tmp_path):
        path = write_feed(tmp_path, {'sUSDe': entry(market="oops")})
        with pytest.raises(PriceUnavailable):
            PegTrackerPrices(path).get_price('sUSDe', now=NOW)


class TestFreshnessFallback:
    def test_entry_without_timestamp_uses_feed_last_updated(self, tmp_path):
        e = {'market_price': 1.24}  # no per-entry timestamp
        path = write_feed(tmp_path, {'sUSDe': e})
        assert PegTrackerPrices(path).get_price('sUSDe', now=NOW) == 1.24
