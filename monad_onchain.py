"""
Monad Chain On-Chain Data Fetcher for Curve Pools

Fetches real-time pool data directly from Monad blockchain RPC
since Curve API doesn't index Monad pools yet.
"""

import requests
from typing import Dict, List


class MonadOnChainFetcher:
    """Fetch Curve pool data from Monad chain via RPC"""

    RPC_URL = 'https://rpc.monad.xyz'

    # Curve pool ABI function signatures
    BALANCES_SIGNATURE = '0x4903b0d1'  # balances(uint256)
    COINS_SIGNATURE = '0xc6610657'     # coins(uint256)
    VIRTUAL_PRICE_SIGNATURE = '0xbb7b8b80'  # get_virtual_price()

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def _rpc_call(self, to: str, data: str) -> str:
        payload = {
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{'to': to, 'data': data}, 'latest'],
            'id': 1,
        }
        try:
            response = self.session.post(self.RPC_URL, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('result', '0x0')
        except Exception as e:
            print(f"RPC call failed: {e}")
            return '0x0'

    def get_token_balance(self, pool_address: str, token_index: int) -> int:
        data = self.BALANCES_SIGNATURE + format(token_index, '064x')
        result = self._rpc_call(pool_address, data)
        return int(result, 16)

    def get_coin_address(self, pool_address: str, token_index: int) -> str:
        data = self.COINS_SIGNATURE + format(token_index, '064x')
        result = self._rpc_call(pool_address, data)
        return '0x' + result[-40:]

    def get_virtual_price(self, pool_address: str) -> float:
        result = self._rpc_call(pool_address, self.VIRTUAL_PRICE_SIGNATURE)
        return int(result, 16) / 1e18

    def get_pool_data(self, pool_address: str, tokens: List[Dict]) -> Dict:
        """
        Get pool TVL, balances, and virtual price.

        Args:
            pool_address: Pool contract address
            tokens: List of token configs with 'symbol' and 'decimals'
        """
        pool_tvl = 0.0
        balances = []
        coin_amounts = []

        for i, token in enumerate(tokens):
            balance_raw = self.get_token_balance(pool_address, i)
            balance = balance_raw / (10 ** token['decimals'])
            balances.append(balance)
            coin_amounts.append(balance_raw)
            pool_tvl += balance

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
