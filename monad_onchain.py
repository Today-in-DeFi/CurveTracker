"""
Monad Chain On-Chain Data Fetcher for Curve Pools

Fetches real-time pool data directly from Monad blockchain RPC
since Curve API doesn't index Monad pools yet.

Reads fail loudly: see onchain_rpc. A dropped eth_call used to become a
balance of zero, which silently dropped one leg out of a pool's TVL while
leaving the result non-zero and therefore unrejectable downstream.
"""

from typing import Dict, List, Optional

from onchain_rpc import JSONRPCClient, RPCError

RPC_URLS = ('https://rpc.monad.xyz',)


class MonadOnChainFetcher:
    """Fetch Curve pool data from Monad chain via RPC"""

    RPC_URL = RPC_URLS[0]

    # Curve pool ABI function signatures
    BALANCES_SIGNATURE = '0x4903b0d1'  # balances(uint256)
    COINS_SIGNATURE = '0xc6610657'     # coins(uint256)
    VIRTUAL_PRICE_SIGNATURE = '0xbb7b8b80'  # get_virtual_price()

    def __init__(self, rpc_urls: Optional[List[str]] = None):
        self.client = JSONRPCClient(rpc_urls or RPC_URLS, label="Monad")

    @property
    def session(self):
        """Kept for callers that reached into the old attribute."""
        return self.client.session

    def get_token_balance(self, pool_address: str, token_index: int) -> int:
        """Balance of the token at index. Raises RPCError if unreadable."""
        data = self.BALANCES_SIGNATURE + format(token_index, '064x')
        return self.client.call_uint(pool_address, data)

    def get_coin_address(self, pool_address: str, token_index: int) -> str:
        """Address of the coin at index. Raises RPCError if unreadable."""
        data = self.COINS_SIGNATURE + format(token_index, '064x')
        return self.client.call_address(pool_address, data)

    def get_virtual_price(self, pool_address: str) -> float:
        """Pool virtual price. Raises RPCError if unreadable."""
        return self.client.call_uint(
            pool_address, self.VIRTUAL_PRICE_SIGNATURE) / 1e18

    def get_pool_data(self, pool_address: str, tokens: List[Dict]) -> Dict:
        """
        Get pool TVL, balances, and virtual price.

        Every leg must be read successfully. A partial result is refused
        rather than returned, because a TVL missing one token still looks
        like a plausible TVL -- there is no way for a caller to tell.

        Args:
            pool_address: Pool contract address
            tokens: List of token configs with 'symbol' and 'decimals'

        Raises:
            RPCError: if any leg, or the virtual price, could not be read.
        """
        balances = []
        coin_amounts = []

        for i, token in enumerate(tokens):
            try:
                balance_raw = self.get_token_balance(pool_address, i)
            except RPCError as e:
                raise RPCError(
                    f"Monad pool {pool_address}: could not read balance for "
                    f"{token.get('symbol', f'token {i}')} -- refusing to report "
                    f"a TVL missing this leg ({e})")

            balance = balance_raw / (10 ** token['decimals'])
            balances.append(balance)
            coin_amounts.append(balance_raw)

        # NOTE: this sums token *amounts*, not USD value, so it is only
        # correct while every token trades at ~$1. Tracked separately.
        pool_tvl = sum(balances)

        return {
            'tvl': pool_tvl,
            'balances': balances,
            'coin_amounts': coin_amounts,
            'virtual_price': self.get_virtual_price(pool_address),
        }


_fetcher = None


def get_fetcher() -> MonadOnChainFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = MonadOnChainFetcher()
    return _fetcher


if __name__ == '__main__':
    fetcher = get_fetcher()

    pools = [
        {
            'name': 'AUSD/USDC/USDT0 (3pool)',
            'address': '0x942644106b073e30d72c2c5d7529d5c296ea91ab',
            'tokens': [
                {'symbol': 'AUSD', 'decimals': 6},
                {'symbol': 'USDC', 'decimals': 6},
                {'symbol': 'USDT0', 'decimals': 6},
            ],
        },
    ]

    print("Testing Monad On-Chain Fetcher")
    print("=" * 60)

    for pool in pools:
        data = fetcher.get_pool_data(pool['address'], pool['tokens'])
        print(f"\n{pool['name']}:")
        for i, token in enumerate(pool['tokens']):
            print(f"  {token['symbol']}: {data['balances'][i]:,.2f}")
        print(f"  TVL: ${data['tvl']:,.2f}")
        print(f"  Virtual price: {data['virtual_price']:.6f}")
