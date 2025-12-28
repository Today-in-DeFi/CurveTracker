#!/usr/bin/env python3
"""
Example: Bulk Add Multiple Pools

Shows how to add multiple pools at once from a list.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pool_manager import PoolManager


def main():
    manager = PoolManager()

    # Define pools to add
    pools_to_add = [
        {
            "chain": "ethereum",
            "pool": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
            "comment": "reUSD/scrvUSD",
            "stakedao_enabled": True,
            "beefy_enabled": True
        },
        {
            "chain": "ethereum",
            "pool": "0x72310DAAed61321b02B08A547150c07522c6a976",
            "comment": "USDC/USDf",
            "stakedao_enabled": True,
            "beefy_enabled": True
        },
        {
            "chain": "fraxtal",
            "pool": "0x15d1ed4418dA1F268bCAd5BA7c8d06BB3c3081eD",
            "comment": "frxUSD/FXB 2027",
            "gauge_address": "0x7506A3e213C362b9e21895c2Bd930DF454d46573",
            "stakedao_enabled": True,
            "beefy_enabled": False
        }
    ]

    # Bulk add
    results = manager.bulk_add_pools(pools_to_add)

    print(f"\n✅ Successfully added {results['added']} pools")
    print(f"⚠️  Skipped {results['skipped']} pools (already exist)")
    print(f"❌ Failed {results['failed']} pools")

    # Show final stats
    manager.print_stats()


if __name__ == "__main__":
    main()
