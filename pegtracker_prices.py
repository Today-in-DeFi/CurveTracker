"""Read token USD prices from the sibling PegTracker feed.

The chain fetchers (plasma_onchain / monad_onchain) can only read token
*amounts*, not USD value, so TVL was summed as if every token traded at $1.
That understated any pool holding a yield-bearing token -- Plasma USDT/sUSDe
by tens of thousands of dollars, since sUSDe is ~$1.24, not $1.

PegTracker already tracks these prices (and NAV), so CurveTracker reads them
rather than guessing or re-deriving them on-chain.

Binding is by an explicit `peg_key` declared per coin in the pool config, NOT
by symbol or address:
  - Symbol collides (two tokens both ticker AUSD), the classic
    two-tokens-one-ticker trap.
  - Address does not match across chains: the pool holds bridged sUSDe on
    Plasma, whose contract differs from the Ethereum sUSDe PegTracker tracks,
    though the economic value is the same.
An explicit key is auditable and cannot silently mis-bind.

Fails loud. A declared key that is missing, priceless, or stale raises
PriceUnavailable rather than falling back to $1 -- a silent $1 is exactly the
bug this module exists to remove. The caller marks the run degraded and does
not persist an untrustworthy TVL.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

# Prices go stale when PegTracker stops updating. The export runs hourly and
# PegTracker refreshes on a similar cadence, so anything older than this is
# treated as unavailable rather than trusted.
DEFAULT_MAX_AGE_HOURS = 6.0

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_FEED = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'PegTracker', 'data', 'peg_tracker_latest_usd.json'))


class PriceUnavailable(RuntimeError):
    """A requested price could not be resolved. Never carries a substitute."""


class PegTrackerPrices:
    """Lazy reader over PegTracker's latest USD feed."""

    def __init__(self, feed_path: Optional[str] = None,
                 max_age_hours: float = DEFAULT_MAX_AGE_HOURS):
        self.feed_path = feed_path or os.getenv('PEGTRACKER_USD_FEED') or _DEFAULT_FEED
        self.max_age_hours = max_age_hours
        self._feed = None

    def _load(self) -> dict:
        if self._feed is None:
            try:
                with open(self.feed_path) as f:
                    self._feed = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                raise PriceUnavailable(
                    f"could not read PegTracker feed at {self.feed_path}: {e}")
        return self._feed

    def get_price(self, peg_key: str, now: Optional[datetime] = None) -> float:
        """USD price for a PegTracker entry, or raise PriceUnavailable.

        Prefers market_price; falls back to theoretical_price (NAV) when the
        market price is absent, since PegTracker publishes NAV for exactly the
        yield-bearing tokens whose market quote can be thin. Both absent, or a
        stale entry, is a hard failure.
        """
        feed = self._load()
        entry = feed.get(peg_key)
        if not isinstance(entry, dict):
            raise PriceUnavailable(f"PegTracker has no entry '{peg_key}'")

        self._check_fresh(peg_key, entry, feed, now)

        price = entry.get('market_price')
        if price is None:
            price = entry.get('theoretical_price')  # NAV fallback
        if price is None:
            raise PriceUnavailable(
                f"PegTracker entry '{peg_key}' has neither market_price nor "
                f"theoretical_price")

        try:
            price = float(price)
        except (TypeError, ValueError):
            raise PriceUnavailable(
                f"PegTracker price for '{peg_key}' is not numeric ({price!r})")
        if price <= 0:
            raise PriceUnavailable(
                f"PegTracker price for '{peg_key}' is not positive ({price})")
        return price

    def _check_fresh(self, peg_key: str, entry: dict, feed: dict,
                     now: Optional[datetime]) -> None:
        stamp = entry.get('timestamp') or feed.get('last_updated')
        if not stamp:
            raise PriceUnavailable(
                f"PegTracker entry '{peg_key}' has no timestamp to age-check")

        ts = _parse_iso(stamp)
        if ts is None:
            raise PriceUnavailable(
                f"PegTracker entry '{peg_key}' has an unparseable timestamp "
                f"({stamp!r})")

        if now is None:
            now = datetime.now(tz=timezone.utc)
        age_hours = (now - ts).total_seconds() / 3600.0
        if age_hours > self.max_age_hours:
            raise PriceUnavailable(
                f"PegTracker price for '{peg_key}' is stale: {age_hours:.1f}h "
                f"old (max {self.max_age_hours}h)")


def _parse_iso(stamp: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp to an aware UTC datetime, or None."""
    text = stamp.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


_prices = None


def get_prices() -> PegTrackerPrices:
    """Shared reader, so the feed is read once per run."""
    global _prices
    if _prices is None:
        _prices = PegTrackerPrices()
    return _prices
