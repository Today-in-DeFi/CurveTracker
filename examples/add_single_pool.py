#!/usr/bin/env python3
"""
Example: Add a Single Pool to CurveTracker

This script shows how to programmatically add a pool to tracking.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pool_manager import PoolManager


def main():
    # Initialize pool manager
    manager = PoolManager()

    # Add a pool with all options
    success = manager.add_pool(
        chain="ethereum",
        pool="0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
        comment="reUSD/scrvUSD - High yield stablecoin pool",
        stakedao_enabled=True,
        beefy_enabled=True,
        validate=True  # Validates pool exists via Curve API
    )

    if success:
        print("\n🎉 Pool added successfully!")

        # Show updated stats
        print("\nUpdated stats:")
        manager.print_stats()
    else:
        print("\n❌ Failed to add pool (may already exist)")


if __name__ == "__main__":
    main()
