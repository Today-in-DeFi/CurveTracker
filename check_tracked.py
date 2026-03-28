#!/usr/bin/env python3
"""Check if a Curve pool is tracked in pools.json."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Check if a Curve pool is tracked")
    parser.add_argument("--pool", required=True, help="Pool contract address (0x...)")
    parser.add_argument("--chain", required=True, help="Chain name (e.g. ethereum, fraxtal, plasma)")
    args = parser.parse_args()

    pools_path = Path(__file__).parent / "pools.json"
    with open(pools_path) as f:
        config = json.load(f)

    pool_addr = args.pool.lower()
    chain = args.chain.lower()

    for entry in config.get("pools", []):
        if entry["pool"].lower() == pool_addr and entry.get("chain", "").lower() == chain:
            result = {
                "tracked": True,
                "pool": entry["pool"],
                "chain": entry.get("chain"),
                "comment": entry.get("comment"),
                "stakedao_enabled": entry.get("stakedao_enabled", False),
                "beefy_enabled": entry.get("beefy_enabled", False),
                "convex_enabled": entry.get("convex_enabled", False),
            }
            # Include optional fields if present
            if "gauge_address" in entry:
                result["gauge_address"] = entry["gauge_address"]
            if "stakedao_vault" in entry:
                result["stakedao_vault"] = entry["stakedao_vault"]
            if "enabled" in entry:
                result["enabled"] = entry["enabled"]

            json.dump(result, sys.stdout, indent=2)
            print()
            sys.exit(0)

    json.dump({"tracked": False, "pool": args.pool, "chain": args.chain}, sys.stdout, indent=2)
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
