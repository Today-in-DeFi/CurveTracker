"""
Plasma Chain On-Chain Data Fetcher for Curve Pools

Fetches real-time pool data directly from Plasma blockchain RPC
since Curve API doesn't index Plasma pools yet.
"""

import requests
from typing import Dict, Optional, List


class PlasmaOnChainFetcher:
    """Fetch Curve pool data from Plasma chain via RPC"""
    
    RPC_URL = 'https://rpc.plasma.to'
    
    # Curve pool ABI function signatures
    BALANCES_SIGNATURE = '0x4903b0d1'  # balances(uint256)
    COINS_SIGNATURE = '0xc6610657'     # coins(uint256)
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def _rpc_call(self, to: str, data: str) -> str:
        """Make JSON-RPC call to Plasma"""
        payload = {
            'jsonrpc': '2.0',
            'method': 'eth_call',
            'params': [{'to': to, 'data': data}, 'latest'],
            'id': 1
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
        """Get balance of token at index in pool"""
        data = self.BALANCES_SIGNATURE + format(token_index, '064x')
        result = self._rpc_call(pool_address, data)
        return int(result, 16)
    
    def get_coin_address(self, pool_address: str, token_index: int) -> str:
        """Get address of coin at index in pool"""
        data = self.COINS_SIGNATURE + format(token_index, '064x')
        result = self._rpc_call(pool_address, data)
        # Extract address from padded result
        return '0x' + result[-40:]
    
    def get_pool_data(self, pool_address: str, tokens: List[Dict]) -> Dict:
        """
        Get pool TVL and balances
        
        Args:
            pool_address: Pool contract address
            tokens: List of token configs with 'symbol' and 'decimals'
        
        Returns:
            Dict with tvl, balances, and coin_amounts
        """
        pool_tvl = 0
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
            'coin_amounts': coin_amounts
        }


# Singleton instance
_fetcher = None

def get_fetcher() -> PlasmaOnChainFetcher:
    """Get or create fetcher instance"""
    global _fetcher
    if _fetcher is None:
        _fetcher = PlasmaOnChainFetcher()
    return _fetcher


if __name__ == '__main__':
    # Test the fetcher
    fetcher = get_fetcher()
    
    pools = [
        {
            'name': 'USDT/USDe',
            'address': '0x2d84d79c852f6842abe0304b70bbaa1506add457',
            'tokens': [
                {'symbol': 'USDT', 'decimals': 6},
                {'symbol': 'USDe', 'decimals': 18}
            ]
        },
        {
            'name': 'USDT/sUSDe',
            'address': '0x1e8d78e9b3f0152d54d32904b7933f1cfe439df1',
            'tokens': [
                {'symbol': 'USDT', 'decimals': 6},
                {'symbol': 'sUSDe', 'decimals': 18}
            ]
        }
    ]
    
    print("Testing Plasma On-Chain Fetcher")
    print("=" * 60)
    
    for pool in pools:
        data = fetcher.get_pool_data(pool['address'], pool['tokens'])
        print(f"\n{pool['name']}:")
        for i, token in enumerate(pool['tokens']):
            print(f"  {token['symbol']}: {data['balances'][i]:,.2f}")
        print(f"  TVL: ${data['tvl']:,.2f}")
