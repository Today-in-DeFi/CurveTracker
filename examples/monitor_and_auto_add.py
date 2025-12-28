#!/usr/bin/env python3
"""
Example: Monitor New Pools and Auto-Add

Periodically checks for new pools and automatically adds them if they meet criteria.
Run this as a daemon or via cron.
"""

import sys
import os
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pool_manager import PoolManager


def get_all_curve_pools(chain: str = "ethereum"):
    """Fetch all pools from Curve API"""
    try:
        url = f"https://api.curve.finance/v1/getPools/all/{chain}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data or 'data' not in data:
            return []

        return data['data'].get('poolData', [])

    except Exception as e:
        print(f"❌ Error fetching pools: {e}")
        return []


def meets_criteria(pool_data: dict) -> bool:
    """
    Check if pool meets auto-add criteria.

    Customize this function for your needs!
    """
    tvl = pool_data.get('usdTotal', 0)
    volume_24h = pool_data.get('totalDailyFeesUSD', 0)

    # Criteria: TVL > $5M or 24h volume > $100k
    return tvl > 5_000_000 or volume_24h > 100_000


def monitor_and_add(chain: str = "ethereum", check_interval: int = 3600):
    """
    Monitor for new pools and auto-add if they meet criteria.

    Args:
        chain: Blockchain to monitor
        check_interval: Seconds between checks (default: 1 hour)
    """
    manager = PoolManager()

    print(f"🔍 Starting pool monitor for {chain}")
    print(f"⏰ Check interval: {check_interval} seconds")
    print(f"Criteria: TVL > $5M or 24h volume > $100k\n")

    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new pools...")

            # Get all pools from Curve
            all_pools = get_all_curve_pools(chain)

            # Get currently tracked pools
            tracked_pools = {p['pool'].lower() for p in manager.list_pools(chain=chain)}

            # Find new pools
            new_pools = []
            for pool in all_pools:
                pool_address = pool.get('address', '').lower()

                # Skip if already tracked
                if pool_address in tracked_pools:
                    continue

                # Check if meets criteria
                if meets_criteria(pool):
                    new_pools.append(pool)

            if new_pools:
                print(f"✨ Found {len(new_pools)} new pools meeting criteria:")

                for pool in new_pools:
                    name = pool.get('name', 'Unknown')
                    tvl = pool.get('usdTotal', 0)
                    address = pool.get('address')

                    print(f"\n  Adding: {name}")
                    print(f"  TVL: ${tvl:,.0f}")
                    print(f"  Address: {address}")

                    # Add pool
                    manager.add_pool(
                        chain=chain,
                        pool=address,
                        comment=f"{name} - Auto-added (TVL: ${tvl:,.0f})",
                        stakedao_enabled=True,
                        beefy_enabled=True,
                        validate=False  # We just got it from Curve
                    )

                print(f"\n✅ Added {len(new_pools)} new pools")
                manager.print_stats()

            else:
                print("  No new pools found")

            # Wait for next check
            print(f"\n💤 Sleeping for {check_interval} seconds...\n")
            time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Stopping pool monitor")
            break
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            time.sleep(60)  # Wait 1 minute before retrying


def main():
    # Monitor Ethereum every hour
    monitor_and_add(chain="ethereum", check_interval=3600)


if __name__ == "__main__":
    main()
