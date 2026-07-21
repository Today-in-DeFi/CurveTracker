"""Ethereum on-chain reads for Curve gauge reward streams.

Curve's HTTP API reports an extra-reward APY but never the stream's expiry, so
a pool paying 6.5% that lapses tomorrow is indistinguishable from one funded
for another year. `reward_data(token)` on the gauge carries both the expiry and
the rate; this module reads it directly.

Unlike plasma_onchain / monad_onchain, `_rpc_call` here **raises** on failure
rather than returning a zero sentinel. A silently-zeroed period_finish would
read as "this stream expired in 1970", which is exactly the plausible-looking
wrong value this repo keeps getting bitten by. Callers are expected to catch,
record the source as degraded, and omit the field -- never to substitute a
placeholder.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from onchain_rpc import JSONRPCClient, RPCError  # noqa: F401  (re-exported)

# keccak("reward_data(address)")[:4]. Hardcoded rather than derived so the
# module needs no eth_utils/web3 dependency; verified live against gauge
# 0x07a0...5e9 on 2026-07-21.
REWARD_DATA_SELECTOR = '0x48e9c65e'

# LiquidityGauge Reward struct, in return order. Word 0 is the token address,
# but some deployed gauges leave it zero (0x07a0...5e9 does), so decoding is
# positional and word 0 is never used to validate the request.
_WORD_DISTRIBUTOR = 1
_WORD_PERIOD_FINISH = 2
_WORD_RATE = 3

SECONDS_PER_YEAR = 31_536_000

DEFAULT_RPC_URLS = (
    'https://ethereum-rpc.publicnode.com',
    'https://eth.drpc.org',
    'https://eth-mainnet.public.blastapi.io',
)

REQUEST_TIMEOUT = 15


class EthereumRPC:
    """Gauge reward reads over the shared fail-loud JSON-RPC client."""

    def __init__(self, rpc_urls: Optional[List[str]] = None):
        configured = os.getenv('ETHEREUM_RPC_URL')
        if rpc_urls:
            urls = list(rpc_urls)
        elif configured:
            # An explicitly configured endpoint is tried first, but the public
            # fallbacks stay in play so one bad key doesn't lose every stream.
            urls = [configured] + list(DEFAULT_RPC_URLS)
        else:
            urls = list(DEFAULT_RPC_URLS)

        self.rpc_urls = urls
        self.client = JSONRPCClient(urls, timeout=REQUEST_TIMEOUT,
                                    label="Ethereum")

    @property
    def session(self):
        """Kept so tests and callers can patch transport in one place."""
        return self.client.session

    def _rpc_call(self, to: str, data: str) -> str:
        """eth_call, returning raw hex. Raises RPCError if no endpoint answers."""
        return self.client.call(to, data)

    def get_reward_data(self, gauge_address: str, token_address: str) -> Dict:
        """Read one reward stream's expiry and rate from the gauge.

        Returns period_finish (unix + ISO), rate per second and per year, the
        distributor, and whether the stream is live as of now. Raises RPCError
        rather than returning partial or placeholder values.
        """
        if not gauge_address or not token_address:
            raise RPCError("gauge_address and token_address are both required")

        padded = token_address[2:].lower().rjust(64, '0')
        raw = self._rpc_call(gauge_address, REWARD_DATA_SELECTOR + padded)

        words = _split_words(raw)
        if len(words) <= _WORD_RATE:
            raise RPCError(
                f"reward_data returned {len(words)} words, expected at least "
                f"{_WORD_RATE + 1} -- gauge {gauge_address} may use a "
                f"different ABI")

        period_finish = words[_WORD_PERIOD_FINISH]
        rate_raw = words[_WORD_RATE]
        distributor = '0x' + format(words[_WORD_DISTRIBUTOR], '040x')

        # Reward tokens are assumed 18-decimal, which holds for every token in
        # Curve's gaugeRewards today. rate_per_year is therefore indicative;
        # period_finish and active do not depend on it.
        rate_per_second = rate_raw / 1e18

        return {
            'period_finish': period_finish,
            'period_finish_iso': _to_iso(period_finish),
            'rate_per_second': rate_per_second,
            'rate_per_year': rate_per_second * SECONDS_PER_YEAR,
            'distributor': distributor,
            'active': is_stream_active(period_finish),
        }


def _split_words(raw: str) -> List[int]:
    """Split an ABI return blob into 32-byte words as ints."""
    body = raw[2:] if raw.startswith('0x') else raw
    return [int(body[i:i + 64], 16) for i in range(0, len(body) - 63, 64)]


def _to_iso(unix_ts: int) -> Optional[str]:
    """Format a unix timestamp as UTC ISO-8601, or None if it is unset."""
    if not unix_ts:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')


def is_stream_active(period_finish: int, now: Optional[int] = None) -> bool:
    """Is a reward stream still paying?

    Unlike the apy > 0 heuristic this replaces, a stream that is funded but
    momentarily paying zero still reads as active, and one that lapsed reads
    as expired the moment it does -- not once its APY happens to hit zero.
    """
    if not period_finish:
        return False
    if now is None:
        now = int(datetime.now(tz=timezone.utc).timestamp())
    return period_finish > now


def seconds_until_expiry(period_finish: int, now: Optional[int] = None) -> Optional[int]:
    """Seconds until a stream lapses; negative if already lapsed, None if unset."""
    if not period_finish:
        return None
    if now is None:
        now = int(datetime.now(tz=timezone.utc).timestamp())
    return period_finish - now


_rpc = None


def get_rpc() -> EthereumRPC:
    """Shared client, so one Session is reused across a run."""
    global _rpc
    if _rpc is None:
        _rpc = EthereumRPC()
    return _rpc


if __name__ == '__main__':
    rpc = get_rpc()
    gauge = '0x07a01471fa544d9c6531b631e6a96a79a9ad05e9'
    for symbol, token in [('BOLD', '0x6440f144b7e50D6a8439336510312d2F54beB01D'),
                          ('LUSD', '0x5f98805A4E8be255a32880FDeC7F6728C6568bA0')]:
        data = rpc.get_reward_data(gauge, token)
        left = seconds_until_expiry(data['period_finish'])
        print(f"{symbol}: finishes {data['period_finish_iso']} "
              f"({left / 3600:.1f}h) active={data['active']} "
              f"rate={data['rate_per_year']:,.0f}/yr")
