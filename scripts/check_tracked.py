#!/usr/bin/env python3
"""Check if a Curve pool is already tracked in pools.json."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Check if a Curve pool is tracked")
    parser.add_argument("--pool", required=True, help="Pool contract address")
    parser.add_argument("--chain", default=None, help="Chain name (optional, searches all if omitted)")
    args = parser.parse_args()

    pools_path = Path(__file__).resolve().parent.parent / "pools.json"
    if not pools_path.exists():
        print(json.dumps({"error": "pools.json not found", "path": str(pools_path)}), file=sys.stdout)
        sys.exit(1)

    try:
        data = json.loads(pools_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(json.dumps({"error": f"Failed to read pools.json: {e}"}), file=sys.stdout)
        sys.exit(1)

    pool_lower = args.pool.lower()
    chain_filter = args.chain.lower() if args.chain else None

    match = None
    for entry in data.get("pools", []):
        entry_pool = entry.get("pool", "").lower()
        entry_chain = entry.get("chain", "").lower()
        if entry_pool == pool_lower:
            if chain_filter is None or entry_chain == chain_filter:
                match = entry
                break

    if match:
        result = {
            "tracked": True,
            "pool": pool_lower,
            "chain": match.get("chain"),
            "comment": match.get("comment"),
            "stakedao_enabled": match.get("stakedao_enabled", False),
            "beefy_enabled": match.get("beefy_enabled", False),
            "details": f"Found in pools.json: {match.get('comment', '')}",
            "add_entry": None,
            "add_command": None,
        }
    else:
        add_entry = {
            "pool": args.pool,
            "comment": "FILL_IN (e.g., tokenA/tokenB)",
            "stakedao_enabled": False,
            "beefy_enabled": False,
        }
        if args.chain:
            add_entry["chain"] = args.chain
            add_entry = {"chain": args.chain, **{k: v for k, v in add_entry.items() if k != "chain"}}

        result = {
            "tracked": False,
            "pool": pool_lower,
            "chain": args.chain if args.chain else None,
            "details": "Pool not found in pools.json",
            "add_entry": add_entry if args.chain else {k: v for k, v in add_entry.items() if k != "chain"},
            "add_command": None,
        }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
