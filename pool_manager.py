"""
Pool Management Module for CurveTracker
Allows programmatic addition, removal, and management of tracked pools
"""

import json
import os
from typing import Dict, List, Optional, Union
from datetime import datetime
import requests


class PoolManager:
    """Manage pools in pools.json configuration file"""

    def __init__(self, config_file: str = "pools.json"):
        """
        Initialize pool manager.

        Args:
            config_file: Path to pools.json configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load pools configuration from JSON file"""
        if not os.path.exists(self.config_file):
            # Create default config if doesn't exist
            default_config = {
                "enable_stakedao": True,
                "enable_beefy": True,
                "pools": []
            }
            self._save_config(default_config)
            return default_config

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Ensure pools array exists
                if 'pools' not in config:
                    config['pools'] = []
                return config
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.config_file}: {e}")

    def _save_config(self, config: Dict) -> None:
        """Save configuration to JSON file"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2, sort_keys=False)

    def _backup_config(self) -> str:
        """Create backup of current config"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.config_file}.backup_{timestamp}"

        with open(self.config_file, 'r') as src:
            with open(backup_file, 'w') as dst:
                dst.write(src.read())

        return backup_file

    def add_pool(
        self,
        chain: str,
        pool: str,
        comment: Optional[str] = None,
        stakedao_enabled: Optional[bool] = None,
        beefy_enabled: Optional[bool] = None,
        gauge_address: Optional[str] = None,
        stakedao_vault: Optional[str] = None,
        validate: bool = True
    ) -> bool:
        """
        Add a new pool to track.

        Args:
            chain: Blockchain network (e.g., "ethereum", "fraxtal")
            pool: Pool address or name
            comment: Human-readable description
            stakedao_enabled: Enable StakeDAO integration for this pool
            beefy_enabled: Enable Beefy integration for this pool
            gauge_address: Optional gauge address
            stakedao_vault: Optional StakeDAO vault address
            validate: Whether to validate pool exists via API

        Returns:
            True if added successfully, False if already exists

        Example:
            manager = PoolManager()
            manager.add_pool(
                chain="ethereum",
                pool="0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
                comment="reUSD/scrvUSD",
                stakedao_enabled=True,
                beefy_enabled=True
            )
        """
        # Check if pool already exists
        if self.pool_exists(chain, pool):
            print(f"⚠️  Pool already exists: {chain}/{pool}")
            return False

        # Validate pool if requested
        if validate:
            if not self.validate_pool(chain, pool):
                print(f"❌ Pool validation failed: {chain}/{pool}")
                return False

        # Create backup before modifying
        self._backup_config()

        # Build pool entry
        pool_entry = {
            "chain": chain,
            "pool": pool
        }

        if comment:
            pool_entry["comment"] = comment
        if stakedao_enabled is not None:
            pool_entry["stakedao_enabled"] = stakedao_enabled
        if beefy_enabled is not None:
            pool_entry["beefy_enabled"] = beefy_enabled
        if gauge_address:
            pool_entry["gauge_address"] = gauge_address
        if stakedao_vault:
            pool_entry["stakedao_vault"] = stakedao_vault

        # Add to config
        self.config['pools'].append(pool_entry)
        self._save_config(self.config)

        print(f"✅ Added pool: {chain}/{pool}")
        if comment:
            print(f"   Comment: {comment}")

        return True

    def remove_pool(self, chain: str, pool: str) -> bool:
        """
        Remove a pool from tracking.

        Args:
            chain: Blockchain network
            pool: Pool address or name

        Returns:
            True if removed, False if not found

        Example:
            manager.remove_pool("ethereum", "0xc522...")
        """
        # Create backup before modifying
        self._backup_config()

        initial_count = len(self.config['pools'])

        # Filter out matching pool
        self.config['pools'] = [
            p for p in self.config['pools']
            if not (p['chain'].lower() == chain.lower() and p['pool'].lower() == pool.lower())
        ]

        if len(self.config['pools']) < initial_count:
            self._save_config(self.config)
            print(f"✅ Removed pool: {chain}/{pool}")
            return True
        else:
            print(f"⚠️  Pool not found: {chain}/{pool}")
            return False

    def update_pool(
        self,
        chain: str,
        pool: str,
        comment: Optional[str] = None,
        stakedao_enabled: Optional[bool] = None,
        beefy_enabled: Optional[bool] = None,
        gauge_address: Optional[str] = None,
        stakedao_vault: Optional[str] = None
    ) -> bool:
        """
        Update an existing pool's settings.

        Args:
            chain: Blockchain network
            pool: Pool address or name
            comment: New comment
            stakedao_enabled: Enable/disable StakeDAO
            beefy_enabled: Enable/disable Beefy
            gauge_address: Update gauge address
            stakedao_vault: Update StakeDAO vault

        Returns:
            True if updated, False if not found

        Example:
            manager.update_pool(
                chain="ethereum",
                pool="0xc522...",
                stakedao_enabled=False
            )
        """
        # Create backup before modifying
        self._backup_config()

        found = False
        for p in self.config['pools']:
            if p['chain'].lower() == chain.lower() and p['pool'].lower() == pool.lower():
                found = True

                # Update fields if provided
                if comment is not None:
                    p['comment'] = comment
                if stakedao_enabled is not None:
                    p['stakedao_enabled'] = stakedao_enabled
                if beefy_enabled is not None:
                    p['beefy_enabled'] = beefy_enabled
                if gauge_address is not None:
                    p['gauge_address'] = gauge_address
                if stakedao_vault is not None:
                    p['stakedao_vault'] = stakedao_vault

                break

        if found:
            self._save_config(self.config)
            print(f"✅ Updated pool: {chain}/{pool}")
            return True
        else:
            print(f"⚠️  Pool not found: {chain}/{pool}")
            return False

    def pool_exists(self, chain: str, pool: str) -> bool:
        """
        Check if a pool is already being tracked.

        Args:
            chain: Blockchain network
            pool: Pool address or name

        Returns:
            True if pool exists in config
        """
        for p in self.config['pools']:
            if p['chain'].lower() == chain.lower() and p['pool'].lower() == pool.lower():
                return True
        return False

    def get_pool(self, chain: str, pool: str) -> Optional[Dict]:
        """
        Get configuration for a specific pool.

        Args:
            chain: Blockchain network
            pool: Pool address or name

        Returns:
            Pool configuration dict or None if not found
        """
        for p in self.config['pools']:
            if p['chain'].lower() == chain.lower() and p['pool'].lower() == pool.lower():
                return p.copy()
        return None

    def list_pools(
        self,
        chain: Optional[str] = None,
        stakedao_only: bool = False,
        beefy_only: bool = False
    ) -> List[Dict]:
        """
        List all tracked pools with optional filters.

        Args:
            chain: Filter by specific chain
            stakedao_only: Only show pools with StakeDAO enabled
            beefy_only: Only show pools with Beefy enabled

        Returns:
            List of pool configuration dicts

        Example:
            # List all Ethereum pools
            eth_pools = manager.list_pools(chain="ethereum")

            # List all pools with StakeDAO enabled
            stakedao_pools = manager.list_pools(stakedao_only=True)
        """
        pools = self.config['pools'].copy()

        # Apply filters
        if chain:
            pools = [p for p in pools if p['chain'].lower() == chain.lower()]

        if stakedao_only:
            pools = [p for p in pools if p.get('stakedao_enabled', False)]

        if beefy_only:
            pools = [p for p in pools if p.get('beefy_enabled', False)]

        return pools

    def validate_pool(self, chain: str, pool: str) -> bool:
        """
        Validate that a pool exists on Curve Finance.

        Args:
            chain: Blockchain network
            pool: Pool address or name

        Returns:
            True if pool exists and is valid

        Note:
            Makes API call to Curve Finance
        """
        try:
            # Try Curve API
            url = f"https://api.curve.finance/v1/getPools/all/{chain}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data or 'data' not in data:
                return False

            pools_data = data['data'].get('poolData', [])

            # Check if pool exists (by address or name)
            pool_lower = pool.lower()
            for pool_info in pools_data:
                pool_address = pool_info.get('address', '').lower()
                pool_name = pool_info.get('name', '').lower()

                if pool_lower == pool_address or pool_lower == pool_name:
                    return True

            print(f"⚠️  Pool not found in Curve API: {chain}/{pool}")
            return False

        except Exception as e:
            print(f"⚠️  Could not validate pool (API error): {e}")
            # Return True to allow adding anyway
            return True

    def set_global_integrations(
        self,
        enable_stakedao: Optional[bool] = None,
        enable_beefy: Optional[bool] = None
    ) -> None:
        """
        Set global integration flags.

        Args:
            enable_stakedao: Enable StakeDAO globally
            enable_beefy: Enable Beefy globally

        Example:
            manager.set_global_integrations(enable_stakedao=True, enable_beefy=True)
        """
        # Create backup before modifying
        self._backup_config()

        if enable_stakedao is not None:
            self.config['enable_stakedao'] = enable_stakedao
            print(f"✅ Global StakeDAO: {'enabled' if enable_stakedao else 'disabled'}")

        if enable_beefy is not None:
            self.config['enable_beefy'] = enable_beefy
            print(f"✅ Global Beefy: {'enabled' if enable_beefy else 'disabled'}")

        self._save_config(self.config)

    def bulk_add_pools(self, pools: List[Dict]) -> Dict[str, int]:
        """
        Add multiple pools at once.

        Args:
            pools: List of pool dicts with 'chain' and 'pool' keys

        Returns:
            Dict with 'added', 'skipped', 'failed' counts

        Example:
            pools = [
                {"chain": "ethereum", "pool": "0xabc...", "comment": "Pool 1"},
                {"chain": "ethereum", "pool": "0xdef...", "comment": "Pool 2"}
            ]
            results = manager.bulk_add_pools(pools)
            print(f"Added: {results['added']}, Skipped: {results['skipped']}")
        """
        results = {"added": 0, "skipped": 0, "failed": 0}

        for pool_config in pools:
            chain = pool_config.get('chain')
            pool = pool_config.get('pool')

            if not chain or not pool:
                print(f"⚠️  Skipping invalid pool config: {pool_config}")
                results['failed'] += 1
                continue

            try:
                added = self.add_pool(
                    chain=chain,
                    pool=pool,
                    comment=pool_config.get('comment'),
                    stakedao_enabled=pool_config.get('stakedao_enabled'),
                    beefy_enabled=pool_config.get('beefy_enabled'),
                    gauge_address=pool_config.get('gauge_address'),
                    stakedao_vault=pool_config.get('stakedao_vault'),
                    validate=pool_config.get('validate', False)
                )

                if added:
                    results['added'] += 1
                else:
                    results['skipped'] += 1
            except Exception as e:
                print(f"❌ Error adding pool {chain}/{pool}: {e}")
                results['failed'] += 1

        print(f"\n📊 Bulk add results:")
        print(f"   Added: {results['added']}")
        print(f"   Skipped: {results['skipped']}")
        print(f"   Failed: {results['failed']}")

        return results

    def export_config(self, output_file: Optional[str] = None) -> str:
        """
        Export current configuration.

        Args:
            output_file: Optional output filename

        Returns:
            Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"pools_export_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(self.config, f, indent=2, sort_keys=False)

        print(f"✅ Exported configuration to: {output_file}")
        return output_file

    def import_config(self, input_file: str, merge: bool = False) -> bool:
        """
        Import configuration from file.

        Args:
            input_file: File to import from
            merge: If True, merge with existing pools; if False, replace

        Returns:
            True if successful
        """
        try:
            with open(input_file, 'r') as f:
                imported_config = json.load(f)

            # Create backup before importing
            self._backup_config()

            if merge:
                # Merge pools
                existing_pools = {(p['chain'], p['pool']) for p in self.config['pools']}

                for pool in imported_config.get('pools', []):
                    pool_key = (pool['chain'], pool['pool'])
                    if pool_key not in existing_pools:
                        self.config['pools'].append(pool)

                print(f"✅ Merged {len(imported_config.get('pools', []))} pools")
            else:
                # Replace entire config
                self.config = imported_config
                print(f"✅ Replaced configuration with {len(imported_config.get('pools', []))} pools")

            self._save_config(self.config)
            return True

        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """
        Get statistics about tracked pools.

        Returns:
            Dict with statistics

        Example:
            stats = manager.get_stats()
            print(f"Total pools: {stats['total_pools']}")
            print(f"Chains: {', '.join(stats['chains'])}")
        """
        pools = self.config['pools']

        chains = set(p['chain'] for p in pools)
        stakedao_enabled = sum(1 for p in pools if p.get('stakedao_enabled', False))
        beefy_enabled = sum(1 for p in pools if p.get('beefy_enabled', False))

        return {
            'total_pools': len(pools),
            'chains': sorted(chains),
            'chain_counts': {
                chain: sum(1 for p in pools if p['chain'] == chain)
                for chain in chains
            },
            'stakedao_enabled_count': stakedao_enabled,
            'beefy_enabled_count': beefy_enabled,
            'global_stakedao': self.config.get('enable_stakedao', False),
            'global_beefy': self.config.get('enable_beefy', False)
        }

    def print_stats(self) -> None:
        """Print formatted statistics"""
        stats = self.get_stats()

        print("\n📊 Pool Tracking Statistics")
        print("=" * 50)
        print(f"Total Pools: {stats['total_pools']}")
        print(f"Chains: {', '.join(stats['chains'])}")
        print(f"\nPools per chain:")
        for chain, count in stats['chain_counts'].items():
            print(f"  {chain}: {count}")
        print(f"\nIntegrations:")
        print(f"  Global StakeDAO: {'✓' if stats['global_stakedao'] else '✗'}")
        print(f"  Global Beefy: {'✓' if stats['global_beefy'] else '✗'}")
        print(f"  Pools with StakeDAO: {stats['stakedao_enabled_count']}")
        print(f"  Pools with Beefy: {stats['beefy_enabled_count']}")
        print("=" * 50)
