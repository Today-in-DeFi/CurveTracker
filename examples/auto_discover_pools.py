#!/usr/bin/env python3
"""
Example: Auto-Discover High TVL Pools

Automatically finds and adds high-TVL pools from Curve Finance.
"""

import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pool_manager import PoolManager


def discover_high_tvl_pools(chain: str = "ethereum", min_tvl: float = 10_000_000):
    """
    Discover pools with TVL above threshold.

    Args:
        chain: Blockchain to search
        min_tvl: Minimum TVL in USD

    Returns:
        List of high-TVL pools
    """
    print(f"🔍 Discovering pools on {chain} with TVL > ${min_tvl:,.0f}...")

    try:
        # Fetch pool data from Curve
        url = f"https://api.curve.finance/v1/getPools/all/{chain}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data or 'data' not in data:
            print("❌ No data returned from Curve API")
            return []

        pools_data = data['data'].get('poolData', [])

        # Filter by TVL
        high_tvl_pools = []
        for pool in pools_data:
            tvl = pool.get('usdTotal', 0)
            if tvl >= min_tvl:
                high_tvl_pools.append({
                    'chain': chain,
                    'pool': pool.get('address'),
                    'comment': f"{pool.get('name')} - TVL: ${tvl:,.0f}",
                    'tvl': tvl,
                    'name': pool.get('name')
                })

        # Sort by TVL
        high_tvl_pools.sort(key=lambda x: x['tvl'], reverse=True)

        print(f"✅ Found {len(high_tvl_pools)} pools with TVL > ${min_tvl:,.0f}")
        return high_tvl_pools

    except Exception as e:
        print(f"❌ Error discovering pools: {e}")
        return []


def main():
    manager = PoolManager()

    # Discover high-TVL pools on Ethereum
    pools = discover_high_tvl_pools(chain="ethereum", min_tvl=10_000_000)

    if not pools:
        print("No pools found")
        return

    # Show discovered pools
    print("\n📊 Discovered Pools:")
    print("=" * 80)
    for i, pool in enumerate(pools[:10], 1):  # Show top 10
        print(f"{i}. {pool['name']}")
        print(f"   TVL: ${pool['tvl']:,.0f}")
        print(f"   Address: {pool['pool']}")

    print("=" * 80)

    # Ask user if they want to add
    response = input("\nAdd top 5 pools to tracking? (y/n): ")

    if response.lower() == 'y':
        # Add top 5 pools
        top_pools = pools[:5]

        # Enable integrations for high-TVL pools
        for pool in top_pools:
            pool['stakedao_enabled'] = True
            pool['beefy_enabled'] = True
            pool['validate'] = False  # Skip validation, we just got this from Curve

        results = manager.bulk_add_pools(top_pools)

        print(f"\n✅ Added {results['added']} pools")
        manager.print_stats()
    else:
        print("Cancelled")


if __name__ == "__main__":
    main()
