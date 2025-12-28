"""
JSON Data Exporter for CurveTracker
Generates comprehensive JSON exports of pool data for external consumption
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class CurveDataExporter:
    """Export Curve pool data to JSON format"""

    def __init__(self, output_dir: str = "data"):
        """
        Initialize exporter.

        Args:
            output_dir: Directory for JSON output files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_to_json(
        self,
        pool_data_list: List,  # List[PoolData]
        history_data: Optional[Dict[str, List[Dict]]] = None
    ) -> str:
        """
        Export pool data to JSON file.

        Args:
            pool_data_list: List of PoolData objects
            history_data: Optional 7-day history per pool (keyed by pool_id)

        Returns:
            Path to saved JSON file
        """
        if not pool_data_list:
            print("⚠️  No pool data to export")
            return ""

        timestamp = datetime.utcnow()

        # Build data structure
        data = {
            "version": "1.0",
            "metadata": self._build_metadata(pool_data_list, timestamp),
            "pools": self._build_pools_array(pool_data_list, history_data)
        }

        # Save to file
        filename = "curve_pools_latest.json"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)

        print(f"✅ Exported {len(pool_data_list)} pools to {filename}")
        return filepath

    def _build_metadata(
        self,
        pool_data_list: List,
        timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Build metadata section.

        Args:
            pool_data_list: List of pool data
            timestamp: Current timestamp

        Returns:
            Metadata dictionary
        """
        chains = set(p.chain for p in pool_data_list)

        # Check which integrations have data
        has_stakedao = any(p.stakedao_apy is not None for p in pool_data_list)
        has_beefy = any(p.beefy_apy is not None for p in pool_data_list)

        integrations = ["Curve"]
        if has_stakedao:
            integrations.append("StakeDAO")
        if has_beefy:
            integrations.append("Beefy")

        return {
            "generated_at": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "CurveTracker v1.0",
            "total_pools": len(pool_data_list),
            "chains": sorted(chains),
            "data_freshness_hours": 1,
            "integrations": integrations
        }

    def _build_pools_array(
        self,
        pool_data_list: List,
        history_data: Optional[Dict[str, List[Dict]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build pools array with latest + history.

        Args:
            pool_data_list: List of pool data
            history_data: Optional historical data keyed by pool_id

        Returns:
            List of pool dictionaries
        """
        result = []
        seen_ids = set()  # Track pool IDs to deduplicate

        for pool in pool_data_list:
            pool_id = self._generate_pool_id(pool)

            # Skip duplicates
            if pool_id in seen_ids:
                continue
            seen_ids.add(pool_id)

            # Parse CRV rewards range
            # Debug: print the crv_rewards_apy value
            # print(f"DEBUG: {pool.name} - crv_rewards_apy = {pool.crv_rewards_apy}")
            crv_min, crv_max = self._parse_crv_rewards(pool.crv_rewards_apy)

            pool_data = {
                "id": pool_id,
                "name": pool.name,
                "chain": pool.chain,
                "latest": {
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "coins": " / ".join(pool.coins),
                    "coin_ratios": ", ".join(pool.coin_ratios),
                    "tvl_usd": self._format_tvl(pool.tvl),
                    "tvl_raw": round(pool.tvl, 2),
                    "base_apy": round(pool.base_apy, 2),
                    "crv_rewards": {
                        "min": round(crv_min, 2),
                        "max": round(crv_max, 2),
                        "range_text": f"{crv_min:.2f} - {crv_max:.2f}"
                    },
                    "other_rewards": self._format_other_rewards(pool.other_rewards),
                    "total_apy": round(pool.total_apy, 2)
                },
                "metadata": {
                    "pool_address": pool.address
                }
            }

            # Add StakeDAO data if available
            if pool.stakedao_apy is not None:
                pool_data["latest"]["stakedao"] = {
                    "apy": round(pool.stakedao_apy, 2),
                    "tvl": round(pool.stakedao_tvl, 2) if pool.stakedao_tvl else None,
                    "boost": round(pool.stakedao_boost, 2) if pool.stakedao_boost else None,
                    "fees": pool.stakedao_fees
                }

            # Add Beefy data if available
            if pool.beefy_apy is not None:
                pool_data["latest"]["beefy"] = {
                    "apy": round(pool.beefy_apy, 2),
                    "tvl": round(pool.beefy_tvl, 2) if pool.beefy_tvl else None,
                    "vault_id": pool.beefy_vault_id
                }

            # Add coin details if available
            if pool.coin_amounts and pool.coin_prices:
                coin_details = []
                for i, coin in enumerate(pool.coins):
                    if i < len(pool.coin_amounts) and i < len(pool.coin_prices):
                        coin_details.append({
                            "name": coin,
                            "amount": round(pool.coin_amounts[i], 2),
                            "price": round(pool.coin_prices[i], 4)
                        })
                if coin_details:
                    pool_data["latest"]["coin_details"] = coin_details

            # Add historical data if available
            if history_data and pool_id in history_data:
                pool_data["history_7d"] = history_data[pool_id]

            result.append(pool_data)

        # Sort by chain, then by name
        result.sort(key=lambda p: (p["chain"], p["name"]))

        return result

    def _generate_pool_id(self, pool) -> str:
        """
        Generate unique pool identifier.

        Args:
            pool: PoolData object

        Returns:
            Unique pool ID string (e.g., "ethereum_reusd_scrvusd")
        """
        import re

        # Clean up pool name: remove special characters, convert spaces to underscores
        pool_name = pool.name.lower()
        # Remove parentheses and their contents
        pool_name = re.sub(r'\([^)]*\)', '', pool_name)
        pool_name = pool_name.replace(" ", "_").replace("-", "_").replace("/", "_")
        # Remove multiple consecutive underscores
        pool_name = re.sub(r'_+', '_', pool_name).strip('_')

        return f"{pool.chain}_{pool_name}"

    def _parse_crv_rewards(self, crv_rewards_apy) -> tuple:
        """
        Parse CRV rewards into min/max range.

        Args:
            crv_rewards_apy: CRV rewards APY (could be list [min, max], string range "6.07 - 15.18", or float)

        Returns:
            Tuple of (min_apy, max_apy)
        """
        # Check if it's a list [min, max]
        if isinstance(crv_rewards_apy, list):
            if len(crv_rewards_apy) >= 2:
                return float(crv_rewards_apy[0]), float(crv_rewards_apy[1])
            elif len(crv_rewards_apy) == 1:
                val = float(crv_rewards_apy[0])
                return val, val

        # Check if it's already a string range like "6.07 - 15.18"
        if isinstance(crv_rewards_apy, str):
            try:
                parts = crv_rewards_apy.split(' - ')
                if len(parts) == 2:
                    min_apy = float(parts[0])
                    max_apy = float(parts[1])
                    return min_apy, max_apy
            except (ValueError, AttributeError):
                pass

        # Fallback: treat as single value
        try:
            apy_value = float(crv_rewards_apy)
            return apy_value, apy_value
        except (ValueError, TypeError):
            # Default to 0 if can't parse
            return 0.0, 0.0

    def _format_other_rewards(self, other_rewards: List[Dict]) -> Optional[List[Dict]]:
        """Format other rewards for JSON export"""
        if not other_rewards:
            return None

        return [
            {
                "token": reward["token"],
                "apy": round(reward["apy"], 2)
            }
            for reward in other_rewards
        ]

    def _format_tvl(self, tvl: float) -> str:
        """Format TVL with appropriate suffixes"""
        if tvl >= 1_000_000_000:
            return f"${tvl/1_000_000_000:.2f}B"
        elif tvl >= 1_000_000:
            return f"${tvl/1_000_000:.2f}M"
        elif tvl >= 1_000:
            return f"${tvl/1_000:.2f}K"
        else:
            return f"${tvl:.2f}"

    def export_daily_archive(
        self,
        pool_data_list: List,
        history_data: Optional[Dict[str, List[Dict]]] = None
    ) -> str:
        """
        Export daily archive with timestamp in filename.

        Args:
            pool_data_list: List of pool data
            history_data: Optional historical data

        Returns:
            Path to saved archive file
        """
        if not pool_data_list:
            return ""

        timestamp = datetime.utcnow()
        date_str = timestamp.strftime("%Y%m%d")

        # Build data structure (same as main export)
        data = {
            "version": "1.0",
            "metadata": self._build_metadata(pool_data_list, timestamp),
            "pools": self._build_pools_array(pool_data_list, history_data)
        }

        # Save to dated file
        filename = f"curve_pools_{date_str}.json"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, sort_keys=False)

        print(f"✅ Exported daily archive to {filename}")
        return filepath

    def append_to_history(
        self,
        pool_data_list: List,
        max_snapshots_per_pool: Optional[int] = None
    ) -> str:
        """
        Append current pool data to cumulative history file.

        Args:
            pool_data_list: List of PoolData objects
            max_snapshots_per_pool: Optional limit on snapshots per pool (None = unlimited)

        Returns:
            Path to saved history file
        """
        if not pool_data_list:
            print("⚠️  No pool data to append to history")
            return ""

        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        # History file path
        history_filename = "curve_pools_history.json"
        history_filepath = os.path.join(self.output_dir, history_filename)

        # Load existing history or create new structure
        if os.path.exists(history_filepath):
            try:
                with open(history_filepath, "r") as f:
                    history = json.load(f)
                print(f"📖 Loaded existing history with {len(history.get('pools', {}))} pools")
            except json.JSONDecodeError:
                print("⚠️  History file corrupted, creating new one")
                history = self._create_empty_history()
        else:
            print("📝 Creating new history file")
            history = self._create_empty_history()

        # Update last_updated timestamp
        history["last_updated"] = timestamp_str

        # Append snapshot for each pool
        pools_updated = 0
        for pool in pool_data_list:
            pool_id = self._generate_pool_id(pool)

            # Create pool entry if doesn't exist
            if pool_id not in history["pools"]:
                history["pools"][pool_id] = {
                    "metadata": {
                        "name": pool.name,
                        "chain": pool.chain,
                        "address": pool.address
                    },
                    "snapshots": []
                }

            # Parse CRV rewards
            crv_min, crv_max = self._parse_crv_rewards(pool.crv_rewards_apy)

            # Build snapshot
            snapshot = {
                "timestamp": timestamp_str,
                "tvl": round(pool.tvl, 2),
                "base_apy": round(pool.base_apy, 2),
                "crv_rewards_min": round(crv_min, 2),
                "crv_rewards_max": round(crv_max, 2),
                "total_apy": round(pool.total_apy, 2)
            }

            # Add optional integration data
            if pool.stakedao_apy is not None:
                snapshot["stakedao_apy"] = round(pool.stakedao_apy, 2)
                if pool.stakedao_tvl is not None:
                    snapshot["stakedao_tvl"] = round(pool.stakedao_tvl, 2)
                if pool.stakedao_boost is not None:
                    snapshot["stakedao_boost"] = round(pool.stakedao_boost, 2)

            if pool.beefy_apy is not None:
                snapshot["beefy_apy"] = round(pool.beefy_apy, 2)
                if pool.beefy_tvl is not None:
                    snapshot["beefy_tvl"] = round(pool.beefy_tvl, 2)

            # Append snapshot
            history["pools"][pool_id]["snapshots"].append(snapshot)

            # Apply retention limit if specified
            if max_snapshots_per_pool:
                snapshots = history["pools"][pool_id]["snapshots"]
                if len(snapshots) > max_snapshots_per_pool:
                    history["pools"][pool_id]["snapshots"] = snapshots[-max_snapshots_per_pool:]

            pools_updated += 1

        # Save updated history
        with open(history_filepath, "w") as f:
            json.dump(history, f, indent=2, sort_keys=False)

        total_snapshots = sum(len(p["snapshots"]) for p in history["pools"].values())
        print(f"✅ Updated history: {pools_updated} pools, {total_snapshots} total snapshots")

        return history_filepath

    def _create_empty_history(self) -> Dict[str, Any]:
        """Create empty history file structure"""
        return {
            "version": "1.0",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pools": {}
        }
