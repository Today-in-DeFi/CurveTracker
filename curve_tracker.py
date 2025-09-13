#!/usr/bin/env python3
"""
Curve Finance Pool Tracker
Fetches TVL, APY, and rewards data for Curve pools
"""

import requests
import json
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from tabulate import tabulate
import argparse
import sys


@dataclass
class PoolData:
    name: str
    chain: str
    address: str
    tvl: float
    base_apy: float
    crv_rewards_apy: float
    other_rewards: List[Dict[str, Union[str, float]]]
    total_apy: float
    coins: List[str]
    coin_ratios: List[str]


class CurveAPI:
    BASE_URL = "https://api.curve.finance/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CurveTracker/1.0'
        })
    
    def _make_request(self, endpoint: str) -> Dict:
        """Make API request with error handling"""
        try:
            response = self.session.get(f"{self.BASE_URL}/{endpoint}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}
    
    def get_all_pools(self, chain: str) -> Dict:
        """Get all pools for a specific chain"""
        return self._make_request(f"getPools/all/{chain}")
    
    def get_base_apys(self, chain: str) -> Dict:
        """Get base APY data for a chain"""
        return self._make_request(f"getBaseApys/{chain}")
    
    def get_all_gauges(self) -> Dict:
        """Get all gauge information"""
        return self._make_request("getAllGauges")
    
    def get_volumes(self, chain: str) -> Dict:
        """Get volume and TVL data"""
        return self._make_request(f"getVolumes/{chain}")


class CurveTracker:
    def __init__(self):
        self.api = CurveAPI()
        self._pools_cache = {}
        self._gauges_cache = {}
        self._apys_cache = {}
        self._volumes_cache = {}
    
    def _load_chain_data(self, chain: str):
        """Load all data for a chain into cache"""
        if chain not in self._pools_cache:
            print(f"Loading {chain} data...")
            self._pools_cache[chain] = self.api.get_all_pools(chain)
            self._apys_cache[chain] = self.api.get_base_apys(chain)
            self._volumes_cache[chain] = self.api.get_volumes(chain)
        
        if not self._gauges_cache:
            self._gauges_cache = self.api.get_all_gauges()
    
    def find_pool_by_address(self, chain: str, address: str) -> Optional[Dict]:
        """Find pool by address in the chain data"""
        self._load_chain_data(chain)
        
        pools_data = self._pools_cache.get(chain, {})
        if 'data' not in pools_data or 'poolData' not in pools_data['data']:
            return None
        
        address_lower = address.lower()
        for pool in pools_data['data']['poolData']:
            if isinstance(pool, dict) and pool.get('address', '').lower() == address_lower:
                return pool
        return None
    
    def find_pool_by_name(self, chain: str, name: str) -> Optional[Dict]:
        """Find pool by name or partial name match"""
        self._load_chain_data(chain)
        
        pools_data = self._pools_cache.get(chain, {})
        if 'data' not in pools_data or 'poolData' not in pools_data['data']:
            return None
        
        name_lower = name.lower()
        for pool in pools_data['data']['poolData']:
            if isinstance(pool, dict):
                pool_name = pool.get('name', '').lower()
                if name_lower in pool_name or pool_name in name_lower:
                    return pool
        return None
    
    def get_pool_apy_data(self, chain: str, address: str) -> Dict:
        """Get APY data for a specific pool"""
        self._load_chain_data(chain)
        
        apy_data = self._apys_cache.get(chain, {})
        if 'data' not in apy_data or 'baseApys' not in apy_data['data']:
            return {}
        
        address_lower = address.lower()
        # Search through the baseApys array for matching address
        for pool_apy in apy_data['data']['baseApys']:
            if isinstance(pool_apy, dict) and pool_apy.get('address', '').lower() == address_lower:
                return pool_apy
        
        return {}
    
    def get_pool_volume_data(self, chain: str, address: str) -> Dict:
        """Get volume/TVL data for a specific pool"""
        self._load_chain_data(chain)
        
        volume_data = self._volumes_cache.get(chain, {})
        if 'data' not in volume_data:
            return {}
        
        address_lower = address.lower()
        return volume_data['data'].get(address_lower, {})
    
    def get_gauge_rewards(self, chain: str, pool_address: str) -> Dict:
        """Get gauge reward data for a pool"""
        if not self._gauges_cache:
            self._gauges_cache = self.api.get_all_gauges()
        
        gauges_data = self._gauges_cache.get('data', {})
        pool_address_lower = pool_address.lower()
        
        for gauge_address, gauge_info in gauges_data.items():
            if isinstance(gauge_info, dict):
                gauge_pool_address = gauge_info.get('swap', '').lower()
                if gauge_pool_address == pool_address_lower:
                    return gauge_info
        
        return {}
    
    def get_pool_data(self, chain: str, pool_identifier: str) -> Optional[PoolData]:
        """Get comprehensive pool data by address or name"""
        # Try to find by address first
        pool = self.find_pool_by_address(chain, pool_identifier)
        
        # If not found, try by name
        if not pool:
            pool = self.find_pool_by_name(chain, pool_identifier)
        
        if not pool:
            print(f"Pool '{pool_identifier}' not found on {chain}")
            return None
        
        pool_address = pool['address']
        
        # Get APY data
        apy_data = self.get_pool_apy_data(chain, pool_address)
        base_apy = 0
        if apy_data:
            # Use daily APY if available, otherwise weekly
            daily_apy = apy_data.get('latestDailyApyPcent', 0)
            weekly_apy = apy_data.get('latestWeeklyApyPcent', 0)
            base_apy = daily_apy if daily_apy > 0 else weekly_apy
        
        # Get volume/TVL data
        volume_data = self.get_pool_volume_data(chain, pool_address)
        tvl = volume_data.get('usdTotal', 0)
        
        # If no TVL from volume API, calculate from pool balances
        if tvl == 0 and 'coins' in pool:
            tvl = 0
            for coin in pool['coins']:
                if isinstance(coin, dict):
                    balance = float(coin.get('poolBalance', 0))
                    price = float(coin.get('usdPrice', 0))
                    decimals = int(coin.get('decimals', 18))
                    coin_value = (balance / (10 ** decimals)) * price
                    tvl += coin_value
        
        # Get gauge rewards
        gauge_data = self.get_gauge_rewards(chain, pool_address)
        crv_apy = 0
        other_rewards = []
        
        if gauge_data:
            # Get CRV APY range from gauge data
            # Try gaugeFutureCrvApy first (might be more accurate), fallback to gaugeCrvApy
            gauge_crv_apy = gauge_data.get('gaugeFutureCrvApy', gauge_data.get('gaugeCrvApy', []))
            if gauge_crv_apy and len(gauge_crv_apy) >= 2:
                crv_apy = gauge_crv_apy  # Store as range [min, max]
            elif gauge_crv_apy and len(gauge_crv_apy) == 1:
                crv_apy = [gauge_crv_apy[0], gauge_crv_apy[0]]  # Same value for min/max
            
            # Check for other reward tokens
            side_chain_rewards_apy = gauge_data.get('sideChainRewardsApy', 0)
            if side_chain_rewards_apy > 0:
                other_rewards.append({
                    'token': 'Side Chain Rewards',
                    'apy': side_chain_rewards_apy * 100
                })
        
        # Get coin information and calculate ratios
        coins = []
        coin_ratios = []
        if 'coins' in pool:
            total_usd_value = 0
            coin_values = []
            
            # First pass: calculate USD values
            for coin in pool['coins']:
                if isinstance(coin, dict):
                    symbol = coin.get('symbol', 'Unknown')
                    balance = float(coin.get('poolBalance', 0))
                    decimals = int(coin.get('decimals', 18))
                    price = float(coin.get('usdPrice', 0))
                    
                    readable_balance = balance / (10 ** decimals)
                    usd_value = readable_balance * price
                    total_usd_value += usd_value
                    
                    coins.append(symbol)
                    coin_values.append({
                        'symbol': symbol,
                        'usd_value': usd_value
                    })
                else:
                    coins.append(str(coin))
            
            # Second pass: calculate ratios
            for coin_data in coin_values:
                if total_usd_value > 0:
                    ratio = (coin_data['usd_value'] / total_usd_value) * 100
                    coin_ratios.append(f"{coin_data['symbol']}: {ratio:.1f}%")
                else:
                    coin_ratios.append(f"{coin_data['symbol']}: 0.0%")
        
        return PoolData(
            name=pool.get('name', 'Unknown'),
            chain=chain,
            address=pool_address,
            tvl=tvl,
            base_apy=base_apy,
            crv_rewards_apy=crv_apy,
            other_rewards=other_rewards,
            total_apy=0,  # Not used anymore
            coins=coins,
            coin_ratios=coin_ratios
        )
    
    def track_pools(self, pools: List[Dict[str, str]]) -> List[PoolData]:
        """Track multiple pools"""
        results = []
        for pool_info in pools:
            chain = pool_info['chain']
            pool_id = pool_info['pool']
            
            pool_data = self.get_pool_data(chain, pool_id)
            if pool_data:
                results.append(pool_data)
        
        return results


def format_currency(amount: float) -> str:
    """Format currency with appropriate suffixes"""
    if amount >= 1_000_000_000:
        return f"${amount/1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.2f}K"
    else:
        return f"${amount:.2f}"


def print_results(pool_data_list: List[PoolData]):
    """Print results in tabular format"""
    if not pool_data_list:
        print("No pool data found.")
        return
    
    headers = [
        "Pool Name",
        "Chain",
        "Coins",
        "Coin Ratios",
        "TVL",
        "Base APY (%)",
        "CRV Rewards (%)",
        "Other Rewards (%)"
    ]
    
    rows = []
    for pool in pool_data_list:
        # Format CRV rewards as range if it's a list, otherwise as single value
        if isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) >= 2:
            crv_rewards_str = f"{pool.crv_rewards_apy[0]:.2f} - {pool.crv_rewards_apy[1]:.2f}"
        elif isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) == 1:
            crv_rewards_str = f"{pool.crv_rewards_apy[0]:.2f}"
        elif isinstance(pool.crv_rewards_apy, (int, float)) and pool.crv_rewards_apy > 0:
            crv_rewards_str = f"{pool.crv_rewards_apy:.2f}"
        else:
            crv_rewards_str = "0.00"
        
        # Format other rewards
        other_rewards_str = ""
        if pool.other_rewards:
            rewards_list = [f"{r['token']}: {r['apy']:.2f}%" for r in pool.other_rewards]
            other_rewards_str = ", ".join(rewards_list)
        else:
            other_rewards_str = "None"
        
        # Format coins
        coins_str = " / ".join(pool.coins[:3])  # Limit to first 3 coins
        if len(pool.coins) > 3:
            coins_str += "..."
        
        # Format coin ratios
        ratios_str = ", ".join(pool.coin_ratios[:2])  # Limit to first 2 ratios
        if len(pool.coin_ratios) > 2:
            ratios_str += "..."
        
        rows.append([
            pool.name[:25] + "..." if len(pool.name) > 25 else pool.name,
            pool.chain.title(),
            coins_str,
            ratios_str,
            format_currency(pool.tvl),
            f"{pool.base_apy:.2f}",
            crv_rewards_str,
            other_rewards_str
        ])
    
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def main():
    parser = argparse.ArgumentParser(description="Track Curve Finance pools")
    parser.add_argument('--chain', '-c', default='ethereum', 
                       help='Blockchain (default: ethereum)')
    parser.add_argument('--pool', '-p', 
                       help='Pool address or name')
    parser.add_argument('--pools', '-P',
                       help='JSON file with pool list')
    
    args = parser.parse_args()
    
    tracker = CurveTracker()
    
    if args.pools:
        # Load from JSON file
        try:
            with open(args.pools, 'r') as f:
                pools = json.load(f)
            results = tracker.track_pools(pools)
        except FileNotFoundError:
            print(f"File {args.pools} not found")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {args.pools}")
            sys.exit(1)
    elif args.pool:
        # Single pool
        pool_data = tracker.get_pool_data(args.chain, args.pool)
        results = [pool_data] if pool_data else []
    else:
        # Default: show popular pools
        popular_pools = [
            {'chain': 'ethereum', 'pool': '3pool'},
            {'chain': 'ethereum', 'pool': 'steth'},
            {'chain': 'ethereum', 'pool': 'frxeth'}
        ]
        results = tracker.track_pools(popular_pools)
    
    print_results(results)


if __name__ == "__main__":
    main()