#!/usr/bin/env python3
"""
Curve Finance Pool Tracker
Fetches TVL, APY, and rewards data for Curve pools
"""

import requests
import json
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from tabulate import tabulate
import argparse
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Plasma on-chain data fetcher
try:
    from plasma_onchain import get_fetcher as get_plasma_fetcher
    PLASMA_ONCHAIN_AVAILABLE = True
except ImportError:
    PLASMA_ONCHAIN_AVAILABLE = False

# Google Sheets imports (optional)
try:
    import gspread
    from google.auth import default
    from google.oauth2 import service_account
    from gspread_dataframe import set_with_dataframe
    import pandas as pd
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False

# Load environment variables
load_dotenv()


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
    eth_amounts: List[str]  # ETH amounts for ETH pools
    coin_amounts: List[float] = field(default_factory=list)  # Individual coin amounts
    coin_prices: List[float] = field(default_factory=list)   # Individual coin prices
    # StakeDAO fields
    stakedao_apy: Optional[float] = None
    stakedao_tvl: Optional[float] = None
    stakedao_boost: Optional[float] = None
    stakedao_fees: Optional[str] = None
    # Beefy fields
    beefy_apy: Optional[float] = None
    beefy_boost: Optional[float] = None
    beefy_tvl: Optional[float] = None
    beefy_vault_id: Optional[str] = None


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


class StakeDAOAPI:
    BASE_URL = "https://api.stakedao.org"

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
            print(f"StakeDAO API request failed: {e}")
            return {}

    def get_curve_strategies(self, chain_id: str = "1") -> Dict:
        """Get Curve strategies for a specific chain"""
        return self._make_request(f"api/strategies/v2/curve/{chain_id}.json")

    def find_strategy_by_address(self, pool_address: str, chain_id: str = "1") -> Optional[Dict]:
        """Find StakeDAO strategy by Curve pool address"""
        strategies_data = self.get_curve_strategies(chain_id)

        # v2 API returns an array directly, not a dict with 'deployed' key
        if not strategies_data or not isinstance(strategies_data, list):
            return None

        pool_address_lower = pool_address.lower()

        # Search through strategies for matching pool address
        for strategy in strategies_data:
            if isinstance(strategy, dict):
                # Check if strategy has pool address or LP token address
                # Try different possible field names for the token address
                strategy_address = ''
                if 'lpToken' in strategy and isinstance(strategy['lpToken'], str):
                    strategy_address = strategy['lpToken'].lower()
                elif 'lpToken' in strategy and isinstance(strategy['lpToken'], dict):
                    strategy_address = strategy['lpToken'].get('address', '').lower()

                if strategy_address == pool_address_lower:
                    return strategy
        return None


class BeefyAPI:
    BASE_URL = "https://api.beefy.finance"

    # Chain name to chain ID mapping
    CHAIN_ID_MAP = {
        'ethereum': 1,
        'polygon': 137,
        'arbitrum': 42161,
        'optimism': 10,
        'bsc': 56,
        'fantom': 250,
        'avalanche': 43114,
        'fraxtal': 252
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CurveTracker/1.0'
        })

    def _make_request(self, endpoint: str) -> Union[Dict, List]:
        """Make API request with error handling"""
        try:
            response = self.session.get(f"{self.BASE_URL}/{endpoint}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Beefy API request failed: {e}")
            return {}

    def get_vaults(self) -> List[Dict]:
        """Get all Beefy vaults"""
        return self._make_request("vaults")

    def get_apy_data(self) -> Dict:
        """Get APY data for all vaults"""
        return self._make_request("apy")

    def get_tvl_data(self) -> Dict:
        """Get TVL data organized by chain and vault"""
        return self._make_request("tvl")

    def get_boosts_data(self) -> List[Dict]:
        """Get boost/incentive data"""
        return self._make_request("boosts")

    def find_curve_vault_by_address(self, pool_address: str, chain: str = "ethereum") -> Optional[Dict]:
        """Find Beefy vault by Curve pool address"""
        vaults = self.get_vaults()
        if not vaults:
            return None

        chain_id = self.CHAIN_ID_MAP.get(chain.lower(), 1)
        pool_address_lower = pool_address.lower()

        # Look for Curve vaults on the specified chain
        curve_vaults = []
        for vault in vaults:
            if (vault.get('chain') == chain and
                vault.get('tokenProviderId') == 'curve'):

                # Check if vault has the pool address (in tokenAddress or other fields)
                token_address = vault.get('tokenAddress', '').lower()
                if token_address == pool_address_lower:
                    curve_vaults.append(vault)

        # If we found exact matches, return the one with highest TVL
        if curve_vaults:
            tvl_data = self.get_tvl_data()
            chain_tvls = tvl_data.get(str(chain_id), {})

            # Add TVL to each vault and sort by TVL
            for vault in curve_vaults:
                vault_id = vault.get('id')
                vault['_tvl'] = chain_tvls.get(vault_id, 0)

            # Return vault with highest TVL
            return max(curve_vaults, key=lambda v: v.get('_tvl', 0))

        return None


class CurveTracker:
    def __init__(self, enable_stakedao: bool = False, enable_beefy: bool = False):
        self.api = CurveAPI()
        self.stakedao_api = StakeDAOAPI() if enable_stakedao else None
        self.beefy_api = BeefyAPI() if enable_beefy else None
        self._pools_cache = {}
        self._gauges_cache = {}
        self._apys_cache = {}
        self._volumes_cache = {}
        self._stakedao_cache = {}
        self._beefy_cache = {}
    
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

    def get_stakedao_data(self, chain: str, pool_address: str) -> Dict:
        """Get StakeDAO strategy data for a pool"""
        if not self.stakedao_api:
            return {}

        # Handle manual StakeDAO data for chains not supported by API
        manual_data = self._get_manual_stakedao_data(chain, pool_address)
        if manual_data:
            return manual_data

        # Map chain name to chain ID for StakeDAO
        chain_mapping = {
            'ethereum': '1',
            'polygon': '137',
            'arbitrum': '42161',
            'optimism': '10',
            'fraxtal': '252'
        }
        chain_id = chain_mapping.get(chain.lower(), '1')

        if chain_id not in self._stakedao_cache:
            self._stakedao_cache[chain_id] = {}

        if pool_address not in self._stakedao_cache[chain_id]:
            strategy = self.stakedao_api.find_strategy_by_address(pool_address, chain_id)
            self._stakedao_cache[chain_id][pool_address] = strategy or {}

        return self._stakedao_cache[chain_id][pool_address]

    def _get_manual_stakedao_data(self, chain: str, pool_address: str) -> Dict:
        """Get manually configured StakeDAO data for pools not in API"""
        # No manual StakeDAO data - only use real API data
        # Placeholder data removed to avoid confusion
        return {}

    def _get_manual_pool_data(self, chain: str, pool_identifier: str) -> Optional[Dict]:
        """Get manually configured pool data for chains not supported by Curve API"""
        # Only return manual data for truly unsupported chains
        # Plasma: Curve deployed Sept 2025, but API doesn't index pools yet
        manual_pools = {
            'plasma': {
                '0x2d84d79c852f6842abe0304b70bbaa1506add457': {
                    'address': '0x2d84d79c852f6842abe0304b70bbaa1506add457',
                    'name': 'USDT/USDe',
                    'coins': [
                        {
                            'address': '0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb',
                            'symbol': 'USDT',
                            'decimals': 6,
                            'poolBalance': 0,
                            'usdPrice': 1.0
                        },
                        {
                            'address': '0x5d3a1Ff2b6BAb83b63cd9AD0787074081a52ef34',
                            'symbol': 'USDe',
                            'decimals': 18,
                            'poolBalance': 0,
                            'usdPrice': 1.0
                        }
                    ]
                },
                '0x1e8d78e9b3f0152d54d32904b7933f1cfe439df1': {
                    'address': '0x1e8d78e9b3f0152d54d32904b7933f1cfe439df1',
                    'name': 'USDT/sUSDe',
                    'coins': [
                        {
                            'address': '0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb',
                            'symbol': 'USDT',
                            'decimals': 6,
                            'poolBalance': 0,
                            'usdPrice': 1.0
                        },
                        {
                            'address': '0x211Cc4DD073734dA055fbF44a2b4667d5E5fE5d2',
                            'symbol': 'sUSDe',
                            'decimals': 18,
                            'poolBalance': 0,
                            'usdPrice': 1.0
                        }
                    ]
                }
            }
        }

        chain_data = manual_pools.get(chain.lower(), {})
        pool_address = pool_identifier.lower()
        return chain_data.get(pool_address)

    def get_beefy_data(self, chain: str, pool_address: str) -> Dict:
        """Get Beefy vault data for a pool"""
        if not self.beefy_api:
            return {}

        if chain not in self._beefy_cache:
            self._beefy_cache[chain] = {}

        if pool_address not in self._beefy_cache[chain]:
            vault = self.beefy_api.find_curve_vault_by_address(pool_address, chain)
            self._beefy_cache[chain][pool_address] = vault or {}

        return self._beefy_cache[chain][pool_address]
    
    def get_pool_data(self, chain: str, pool_identifier: str, stakedao_enabled: bool = None, beefy_enabled: bool = None) -> Optional[PoolData]:
        """Get comprehensive pool data by address or name"""
        # Check for manual pool data first (for chains not supported by Curve API)
        manual_pool = self._get_manual_pool_data(chain, pool_identifier)
        if manual_pool:
            pool = manual_pool
        else:
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

        # Fetch on-chain data for Plasma pools
        if chain.lower() == 'plasma' and PLASMA_ONCHAIN_AVAILABLE and 'coins' in pool:
            try:
                fetcher = get_plasma_fetcher()
                tokens = [{'symbol': coin['symbol'], 'decimals': coin['decimals']} for coin in pool['coins']]
                onchain_data = fetcher.get_pool_data(pool_address, tokens)
                tvl = onchain_data['tvl']
                # Update coin balances with real on-chain data
                for i, coin in enumerate(pool['coins']):
                    if i < len(onchain_data['balances']):
                        coin['poolBalance'] = onchain_data['coin_amounts'][i]
            except Exception as e:
                print(f"Warning: Failed to fetch on-chain data for Plasma pool: {e}")

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

            # Check for other reward tokens from Curve gauge data
            side_chain_rewards_apy = gauge_data.get('sideChainRewardsApy', 0)
            if side_chain_rewards_apy > 0:
                other_rewards.append({
                    'token': 'Side Chain Rewards',
                    'apy': side_chain_rewards_apy * 100
                })
        
        # Get coin information and calculate ratios
        coins = []
        coin_ratios = []
        eth_amounts = []
        coin_amounts = []
        coin_prices = []
        if 'coins' in pool:
            total_usd_value = 0
            coin_values = []

            # First pass: calculate USD values and ETH amounts
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
                        'balance': readable_balance,
                        'usd_value': usd_value,
                        'price': price
                    })

                    # Store individual amounts and prices
                    coin_amounts.append(readable_balance)
                    coin_prices.append(price)

                    # Store ETH amounts (always store, will be filtered later if needed)
                    eth_amounts.append(f"{symbol}: {readable_balance:.4f}")
                else:
                    coins.append(str(coin))

            # Second pass: calculate ratios
            for coin_data in coin_values:
                if total_usd_value > 0:
                    ratio = (coin_data['usd_value'] / total_usd_value) * 100
                    coin_ratios.append(f"{coin_data['symbol']}: {ratio:.1f}%")
                else:
                    coin_ratios.append(f"{coin_data['symbol']}: 0.0%")

        # Get StakeDAO data if enabled
        stakedao_apy = None
        stakedao_tvl = None
        stakedao_boost = None
        stakedao_fees = None

        if self.stakedao_api and (stakedao_enabled if stakedao_enabled is not None else True):
            stakedao_data = self.get_stakedao_data(chain, pool_address)
            if stakedao_data:
                # Extract APY data (v2 API uses current.total instead of projected.total)
                apr_data = stakedao_data.get('apr', {})

                # Try v2 API structure first (current.total)
                current_apr = apr_data.get('current', {})
                if current_apr and 'total' in current_apr:
                    stakedao_apy = current_apr['total']
                else:
                    # Fallback to v1 API structure (projected.total)
                    projected_apr = apr_data.get('projected', {})
                    if projected_apr and 'total' in projected_apr:
                        stakedao_apy = projected_apr['total']

                # Extract TVL
                stakedao_tvl = stakedao_data.get('tvl')

                # Extract boost
                stakedao_boost = apr_data.get('boost')

                # Extract fees (basic implementation)
                fee_parts = []
                if 'fees' in stakedao_data:
                    fees = stakedao_data['fees']
                    if isinstance(fees, dict):
                        for fee_type, fee_value in fees.items():
                            if isinstance(fee_value, (int, float)) and fee_value > 0:
                                fee_parts.append(f"{fee_type}: {fee_value:.2f}%")
                if fee_parts:
                    stakedao_fees = ", ".join(fee_parts)

                # If Curve gauge data doesn't have other rewards, check StakeDAO rewards
                if not other_rewards and 'rewards' in stakedao_data:
                    for reward in stakedao_data['rewards']:
                        if isinstance(reward, dict):
                            token_info = reward.get('token', {})
                            if isinstance(token_info, dict):
                                token_symbol = token_info.get('symbol', 'Unknown')
                                reward_apr = reward.get('apr', 0)

                                # Skip CRV rewards as they're already shown in CRV Rewards column
                                if token_symbol.upper() != 'CRV' and reward_apr > 0:
                                    other_rewards.append({
                                        'token': token_symbol,
                                        'apy': reward_apr
                                    })

        # Get Beefy data if enabled
        beefy_apy = None
        beefy_boost = None
        beefy_tvl = None
        beefy_vault_id = None

        if self.beefy_api and (beefy_enabled if beefy_enabled is not None else True):
            beefy_data = self.get_beefy_data(chain, pool_address)
            if beefy_data:
                # Get vault ID for reference
                beefy_vault_id = beefy_data.get('id')

                # Get APY data (Beefy returns as decimal, convert to percentage)
                apy_data = self.beefy_api.get_apy_data()
                if beefy_vault_id and beefy_vault_id in apy_data:
                    raw_apy = apy_data[beefy_vault_id]
                    if isinstance(raw_apy, (int, float)) and raw_apy < 1:
                        beefy_apy = raw_apy * 100  # Convert decimal to percentage
                    else:
                        beefy_apy = raw_apy  # Keep as-is if already percentage

                # Get TVL data (already populated in _tvl from vault finding)
                beefy_tvl = beefy_data.get('_tvl')

                # Get boost data (boosts use format "moo_<vault-id>")
                boosts_data = self.beefy_api.get_boosts_data()
                if boosts_data and beefy_vault_id:
                    boost_id_to_find = f"moo_{beefy_vault_id}"
                    for boost in boosts_data:
                        if isinstance(boost, dict) and boost.get('id') == boost_id_to_find:
                            # Check if boost is active and get reward info
                            if boost.get('status') == 'active':
                                # Boost rewards are typically additional token incentives
                                earned_token = boost.get('earnedToken', 'Unknown')
                                beefy_boost = f"{earned_token} rewards"
                            break

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
            coin_ratios=coin_ratios,
            eth_amounts=eth_amounts,
            coin_amounts=coin_amounts,
            coin_prices=coin_prices,
            stakedao_apy=stakedao_apy,
            stakedao_tvl=stakedao_tvl,
            stakedao_boost=stakedao_boost,
            stakedao_fees=stakedao_fees,
            beefy_apy=beefy_apy,
            beefy_boost=beefy_boost,
            beefy_tvl=beefy_tvl,
            beefy_vault_id=beefy_vault_id
        )
    
    def track_pools(self, pools: List[Dict[str, str]]) -> List[PoolData]:
        """Track multiple pools"""
        results = []
        for pool_info in pools:
            chain = pool_info['chain']
            pool_id = pool_info['pool']
            stakedao_enabled = pool_info.get('stakedao_enabled', False)
            beefy_enabled = pool_info.get('beefy_enabled', False)

            pool_data = self.get_pool_data(chain, pool_id, stakedao_enabled, beefy_enabled)
            if pool_data:
                results.append(pool_data)

        return results


class GoogleSheetsExporter:
    """Handle Google Sheets export functionality"""
    
    def __init__(self, credentials_file: Optional[str] = None):
        if not SHEETS_AVAILABLE:
            raise ImportError("Google Sheets dependencies not available. Install with: pip install gspread gspread-dataframe google-auth")
        
        self.credentials_file = credentials_file or os.getenv('GOOGLE_CREDENTIALS_FILE')
        self.client = None
    
    def _is_eth_pool(self, pool: PoolData) -> bool:
        """Determine if a pool is ETH-based"""
        eth_tokens = {'eth', 'weth', 'weeth', 'steth', 'reth', 'cbeth', 'sweth', 'frxeth', 'sfrxeth'}
        
        # Check if any coin is an ETH variant
        for coin in pool.coins:
            if coin.lower() in eth_tokens:
                return True
        
        return False
    
    def get_client(self) -> gspread.Client:
        """Get authenticated Google Sheets client"""
        if self.client:
            return self.client
        
        try:
            if self.credentials_file and os.path.exists(self.credentials_file):
                # Use service account
                print(f"🔐 Authenticating with service account: {self.credentials_file}")
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_file,
                    scopes=['https://spreadsheets.google.com/feeds', 
                           'https://www.googleapis.com/auth/drive']
                )
                self.client = gspread.authorize(credentials)
                
                # Show service account email for sharing
                with open(self.credentials_file, 'r') as f:
                    creds_info = json.load(f)
                    email = creds_info.get('client_email', 'Unknown')
                    print(f"📧 Service account email: {email}")
                    print("   Share your Google Sheet with this email address")
            else:
                # Use default credentials
                print("🔐 Using default Google credentials")
                creds, project = default(scopes=['https://spreadsheets.google.com/feeds',
                                               'https://www.googleapis.com/auth/drive'])
                self.client = gspread.authorize(creds)
            
            return self.client
            
        except Exception as e:
            raise Exception(f"Google Sheets authentication failed: {e}")
    
    def get_or_create_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str, max_coins: int = 2) -> gspread.Worksheet:
        """Get existing worksheet or create new one with headers"""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"✅ Found existing sheet: {sheet_name}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"📝 Creating new sheet: {sheet_name}")

            # Calculate total columns needed
            base_cols = 10  # Date, Time, Pool Name, Coin Ratios, TVL, Base APY, CRV Min/Max, Other Rewards, Address
            coin_cols = max_coins * 2  # Amount and Price for each coin
            integration_cols = 5  # StakeDAO APY, TVL, Boost, Beefy APY, TVL
            total_cols = base_cols + coin_cols + integration_cols

            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=total_cols)

            headers = [
                'Date', 'Time', 'Pool Name', 'Coin Ratios (USD Value)',
                'TVL (USD)', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
                'Other Rewards', 'StakeDAO APY (%)', 'StakeDAO TVL (USD)',
                'StakeDAO Boost', 'Beefy APY (%)', 'Beefy TVL (USD)', 'Address'
            ]

            # Add coin amount and price columns at the end
            for i in range(max_coins):
                headers.extend([
                    f'Coin {i+1} Amount',
                    f'Coin {i+1} Price'
                ])

            worksheet.update(values=[headers], range_name=f'A1:{chr(65+len(headers)-1)}1')
            print(f"📋 Added headers to new sheet")

            return worksheet
    
    def format_data_for_sheets(self, pool_data_list: List[PoolData], max_coins: int = 2) -> pd.DataFrame:
        """Convert pool data to DataFrame format for Google Sheets"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        rows = []
        for pool in pool_data_list:
            # Format CRV rewards
            if isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) >= 2:
                crv_min = pool.crv_rewards_apy[0]
                crv_max = pool.crv_rewards_apy[1]
            elif isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) == 1:
                crv_min = crv_max = pool.crv_rewards_apy[0]
            elif isinstance(pool.crv_rewards_apy, (int, float)):
                crv_min = crv_max = pool.crv_rewards_apy
            else:
                crv_min = crv_max = 0

            # Format other rewards
            other_rewards_str = ""
            if pool.other_rewards:
                rewards_list = [f"{r['token']}: {r['apy']:.2f}%" for r in pool.other_rewards]
                other_rewards_str = ", ".join(rewards_list)
            else:
                other_rewards_str = "None"

            # Asset ratio column should always use percentages (coin_ratios)
            coin_data_str = ", ".join(pool.coin_ratios)

            row = [
                date_str,
                time_str,
                pool.name,
                coin_data_str,
                pool.tvl,
                pool.base_apy,
                crv_min,
                crv_max,
                other_rewards_str,
                pool.stakedao_apy if pool.stakedao_apy is not None else "",
                pool.stakedao_tvl if pool.stakedao_tvl is not None else "",
                pool.stakedao_boost if pool.stakedao_boost is not None else "",
                pool.beefy_apy if pool.beefy_apy is not None else "",
                pool.beefy_tvl if pool.beefy_tvl is not None else "",
                pool.address
            ]

            # Add coin amounts and prices at the end
            for i in range(max_coins):
                if pool.coin_amounts and i < len(pool.coin_amounts):
                    row.append(pool.coin_amounts[i])
                else:
                    row.append("")

                if pool.coin_prices and i < len(pool.coin_prices):
                    row.append(pool.coin_prices[i])
                else:
                    row.append("")

            rows.append(row)

        # Build column headers
        columns = [
            'Date', 'Time', 'Pool Name', 'Coin Ratios (USD Value)',
            'TVL (USD)', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
            'Other Rewards', 'StakeDAO APY (%)', 'StakeDAO TVL (USD)',
            'StakeDAO Boost', 'Beefy APY (%)', 'Beefy TVL (USD)', 'Address'
        ]

        # Add coin amount and price columns at the end
        for i in range(max_coins):
            columns.extend([
                f'Coin {i+1} Amount',
                f'Coin {i+1} Price'
            ])

        return pd.DataFrame(rows, columns=columns)
    
    def export_to_sheets(self, pool_data_list: List[PoolData], 
                        spreadsheet_id: Optional[str] = None, 
                        spreadsheet_name: Optional[str] = None,
                        append_data: bool = True) -> None:
        """Export pool data to Google Sheets"""
        if not pool_data_list:
            print("❌ No pool data to export")
            return
        
        client = self.get_client()
        
        # Get spreadsheet
        try:
            if spreadsheet_id:
                spreadsheet = client.open_by_key(spreadsheet_id)
            elif spreadsheet_name:
                spreadsheet = client.open(spreadsheet_name)
            else:
                spreadsheet_name = "Curve Pool Tracker"
                try:
                    spreadsheet = client.open(spreadsheet_name)
                except gspread.exceptions.SpreadsheetNotFound:
                    print(f"📝 Creating new spreadsheet: {spreadsheet_name}")
                    spreadsheet = client.create(spreadsheet_name)
                    print(f"🔗 Spreadsheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
            
            print(f"📊 Using spreadsheet: {spreadsheet.title}")
        except Exception as e:
            print(f"❌ Error accessing spreadsheet: {e}")
            return
        
        # Determine the maximum number of coins across all pools
        max_coins = max(len(p.coins) for p in pool_data_list) if pool_data_list else 2

        # Group pools by chain and asset type (USD vs ETH)
        pools_by_category = {}
        for pool in pool_data_list:
            chain = pool.chain.title()

            # Determine if this is an ETH-based pool
            is_eth_pool = self._is_eth_pool(pool)

            if is_eth_pool:
                category = f"{chain} ETH"
            else:
                category = f"{chain} USD"

            if category not in pools_by_category:
                pools_by_category[category] = []
            pools_by_category[category].append(pool)

        # Export each category to its own worksheet
        for category, pools in pools_by_category.items():
            worksheet = self.get_or_create_worksheet(spreadsheet, category, max_coins=max_coins)

            # Convert to DataFrame with coin amount/price columns
            df = self.format_data_for_sheets(pools, max_coins=max_coins)
            
            if append_data:
                # Append to existing data
                try:
                    existing_data = worksheet.get_all_records()
                    if existing_data:
                        existing_df = pd.DataFrame(existing_data)
                        combined_df = pd.concat([existing_df, df], ignore_index=True)
                    else:
                        combined_df = df
                    
                    # Clear and update with combined data
                    worksheet.clear()
                    set_with_dataframe(worksheet, combined_df, include_index=False)
                    print(f"📈 Appended {len(df)} rows to {category} (total: {len(combined_df)})")
                    
                except Exception as e:
                    print(f"⚠️  Error appending data, replacing instead: {e}")
                    set_with_dataframe(worksheet, df, include_index=False)
                    print(f"📝 Replaced data in {category} with {len(df)} rows")
            else:
                # Replace all data
                worksheet.clear()
                set_with_dataframe(worksheet, df, include_index=False)
                print(f"📝 Updated {category} with {len(df)} pools")
        
        print(f"✅ Successfully exported {len(pool_data_list)} pools to Google Sheets")

    def _cleanup_old_log_data(
        self,
        worksheet: gspread.Worksheet,
        days_to_keep: int = 30
    ) -> int:
        """
        Remove log entries older than specified days.

        Args:
            worksheet: The Log worksheet to clean
            days_to_keep: Number of days of history to retain (default: 30)

        Returns:
            Number of rows deleted
        """
        from datetime import timedelta

        try:
            # Get all values from the sheet
            all_values = worksheet.get_all_values()

            if len(all_values) <= 1:
                # Only header row or empty sheet
                return 0

            # First row is headers, keep it
            headers = all_values[0]
            data_rows = all_values[1:]

            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            # Filter rows to keep
            rows_to_keep = []
            rows_deleted = 0

            for row in data_rows:
                if not row or len(row) < 2:
                    continue

                # Date is in column 0, Time is in column 1
                date_str = row[0]
                time_str = row[1]
                try:
                    # Parse date and time (format: 'YYYY-MM-DD' and 'HH:MM:SS')
                    timestamp_str = f"{date_str} {time_str}"
                    row_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if row_timestamp >= cutoff_date:
                        rows_to_keep.append(row)
                    else:
                        rows_deleted += 1
                except (ValueError, IndexError):
                    # Keep rows with malformed timestamps to be safe
                    rows_to_keep.append(row)

            # Only rewrite if we're deleting rows
            if rows_deleted > 0:
                # Clear the sheet
                worksheet.clear()

                # Rewrite with headers + filtered data
                new_data = [headers] + rows_to_keep
                worksheet.update(values=new_data, range_name='A1')

                print(f"🗑️  Cleaned up {rows_deleted} old rows (keeping last {days_to_keep} days)")

            return rows_deleted

        except Exception as e:
            print(f"⚠️  Warning: Could not cleanup old log data: {e}")
            return 0

    def export_to_log_sheet(
        self,
        pool_data_list: List[PoolData],
        spreadsheet_id: Optional[str] = None,
        spreadsheet_name: Optional[str] = None,
        days_to_keep: int = 30
    ) -> None:
        """
        Export pool data to 'Log' sheet for time-series tracking.

        Creates multiple rows per timestamp (one row per pool) with consistent columns.
        Format: Date | Time | Pool Name | Coin Ratios | TVL | Base APY | CRV Min | CRV Max | ...

        Automatically cleans up rows older than specified days to keep sheet performant.

        Args:
            pool_data_list: List of pool data to log
            spreadsheet_id: Optional spreadsheet ID
            spreadsheet_name: Optional spreadsheet name (defaults to "Curve Pool Tracker")
            days_to_keep: Number of days of history to retain (default: 30)
        """
        if not pool_data_list:
            print("⚠️  No pool data to log")
            return

        client = self.get_client()

        # Get spreadsheet
        try:
            if spreadsheet_id:
                spreadsheet = client.open_by_key(spreadsheet_id)
            elif spreadsheet_name:
                spreadsheet = client.open(spreadsheet_name)
            else:
                spreadsheet_name = "Curve Pool Tracker"
                spreadsheet = client.open(spreadsheet_name)

            print(f"📊 Logging to spreadsheet: {spreadsheet.title}")
        except Exception as e:
            print(f"❌ Error accessing spreadsheet for log: {e}")
            return

        # Sort pools consistently (by chain, then name)
        sorted_pools = sorted(pool_data_list, key=lambda p: (p.chain, p.name))

        # Get or create Log sheet
        sheet_name = "Log"
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"✅ Found existing Log sheet")
        except gspread.exceptions.WorksheetNotFound:
            print(f"📝 Creating new Log sheet")

            worksheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=10000,  # More rows since we'll have multiple per timestamp
                cols=20
            )

            # Build headers (same format as individual category sheets)
            headers = [
                'Date', 'Time', 'Pool Name', 'Chain', 'Coin Ratios (USD Value)',
                'TVL (USD)', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
                'Other Rewards', 'StakeDAO APY (%)', 'StakeDAO TVL (USD)',
                'StakeDAO Boost', 'Beefy APY (%)', 'Beefy TVL (USD)', 'Address'
            ]

            # Write headers
            worksheet.update(values=[headers], range_name=f'A1')
            print(f"📋 Created Log sheet with headers")

        # Cleanup old data (keep only last N days)
        self._cleanup_old_log_data(worksheet, days_to_keep=days_to_keep)

        # Build data rows (one per pool)
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        rows_to_append = []
        for pool in sorted_pools:
            # Parse CRV rewards
            if isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) >= 2:
                crv_min = pool.crv_rewards_apy[0]
                crv_max = pool.crv_rewards_apy[1]
            elif isinstance(pool.crv_rewards_apy, list) and len(pool.crv_rewards_apy) == 1:
                crv_min = crv_max = pool.crv_rewards_apy[0]
            elif isinstance(pool.crv_rewards_apy, (int, float)):
                crv_min = crv_max = pool.crv_rewards_apy
            else:
                crv_min = crv_max = 0

            # Format other rewards
            other_rewards_str = ""
            if pool.other_rewards:
                rewards_list = [f"{r['token']}: {r['apy']:.2f}%" for r in pool.other_rewards]
                other_rewards_str = ", ".join(rewards_list)
            else:
                other_rewards_str = "None"

            # Format coin ratios
            coin_ratios_str = ", ".join(pool.coin_ratios)

            row = [
                date_str,
                time_str,
                pool.name,
                pool.chain.title(),
                coin_ratios_str,
                pool.tvl,
                pool.base_apy,
                crv_min,
                crv_max,
                other_rewards_str,
                pool.stakedao_apy if pool.stakedao_apy is not None else "",
                pool.stakedao_tvl if pool.stakedao_tvl is not None else "",
                pool.stakedao_boost if pool.stakedao_boost is not None else "",
                pool.beefy_apy if pool.beefy_apy is not None else "",
                pool.beefy_tvl if pool.beefy_tvl is not None else "",
                pool.address
            ]
            rows_to_append.append(row)

        # Insert rows at top (after headers) - newest data first
        try:
            if rows_to_append:
                worksheet.insert_rows(rows_to_append, row=2, value_input_option='USER_ENTERED')
                print(f"✅ Logged {len(rows_to_append)} pool snapshots at {date_str} {time_str}")
        except Exception as e:
            print(f"❌ Error appending to Log sheet: {e}")


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

    # Check if any pools have StakeDAO or Beefy data to determine if we need extra columns
    has_stakedao = any(p.stakedao_apy is not None or p.stakedao_tvl is not None for p in pool_data_list)
    has_beefy = any(p.beefy_apy is not None or p.beefy_tvl is not None for p in pool_data_list)

    # Determine the maximum number of coins across all pools
    max_coins = max(len(p.coins) for p in pool_data_list) if pool_data_list else 0

    headers = [
        "Pool Name",
        "Chain",
        "Coins",
        "Coin Ratios (USD Value)",
        "TVL",
        "Base APY (%)",
        "CRV Rewards (%)",
        "Other Rewards (%)"
    ]

    # Add StakeDAO columns if any pool has StakeDAO data
    if has_stakedao:
        headers.extend([
            "StakeDAO APY (%)",
            "StakeDAO TVL",
            "StakeDAO Boost"
        ])

    # Add Beefy columns if any pool has Beefy data
    if has_beefy:
        headers.extend([
            "Beefy APY (%)",
            "Beefy TVL"
        ])

    # Add address column
    headers.append("Address")

    # Add dynamic coin amount and price columns at the end
    for i in range(max_coins):
        headers.extend([
            f"Coin {i+1} Amount",
            f"Coin {i+1} Price"
        ])
    
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
        
        row = [
            pool.name[:25] + "..." if len(pool.name) > 25 else pool.name,
            pool.chain.title(),
            coins_str,
            ratios_str,
            format_currency(pool.tvl),
            f"{pool.base_apy:.2f}",
            crv_rewards_str,
            other_rewards_str
        ]

        # Add StakeDAO columns if needed
        if has_stakedao:
            stakedao_apy_str = f"{pool.stakedao_apy:.2f}" if pool.stakedao_apy is not None else "N/A"
            stakedao_tvl_str = format_currency(pool.stakedao_tvl) if pool.stakedao_tvl is not None else "N/A"
            stakedao_boost_str = f"{pool.stakedao_boost:.1f}x" if pool.stakedao_boost is not None else "N/A"

            row.extend([
                stakedao_apy_str,
                stakedao_tvl_str,
                stakedao_boost_str
            ])

        # Add Beefy columns if needed
        if has_beefy:
            beefy_apy_str = f"{pool.beefy_apy:.2f}" if pool.beefy_apy is not None else "N/A"
            beefy_tvl_str = format_currency(pool.beefy_tvl) if pool.beefy_tvl is not None else "N/A"

            row.extend([
                beefy_apy_str,
                beefy_tvl_str
            ])

        # Add address column
        row.append(pool.address)

        # Add coin amount and price columns at the end
        for i in range(max_coins):
            if pool.coin_amounts and i < len(pool.coin_amounts):
                row.append(f"{pool.coin_amounts[i]:,.2f}")
            else:
                row.append("N/A")

            if pool.coin_prices and i < len(pool.coin_prices):
                row.append(f"${pool.coin_prices[i]:,.4f}")
            else:
                row.append("N/A")

        rows.append(row)
    
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def main():
    parser = argparse.ArgumentParser(description="Track Curve Finance pools")
    parser.add_argument('--chain', '-c', default='ethereum',
                       help='Blockchain (default: ethereum)')
    parser.add_argument('--pool', '-p',
                       help='Pool address or name')
    parser.add_argument('--pools', '-P',
                       help='JSON file with pool list')

    # StakeDAO integration
    parser.add_argument('--stakedao', action='store_true',
                       help='Enable StakeDAO data fetching')

    # Beefy integration
    parser.add_argument('--beefy', action='store_true',
                       help='Enable Beefy data fetching')

    # Google Sheets arguments
    parser.add_argument('--export-sheets', action='store_true',
                       help='Export results to Google Sheets')
    parser.add_argument('--credentials',
                       help='Path to Google service account credentials JSON file')
    parser.add_argument('--sheet-id',
                       help='Google Sheets spreadsheet ID')
    parser.add_argument('--sheet-name',
                       help='Google Sheets spreadsheet name (default: "Curve Pool Tracker")')
    parser.add_argument('--append-data', action='store_true',
                       help='Append to existing data instead of replacing (default: replace)')
    parser.add_argument('--replace-data', action='store_true',
                       help='Replace existing data (same as default behavior)')

    # JSON export arguments
    parser.add_argument('--export-json', action='store_true',
                       help='Export data to JSON and upload to Google Drive')
    parser.add_argument('--json-only', action='store_true', default=True,
                       help='Export to JSON file only (no Drive upload) - enabled by default')
    parser.add_argument('--no-json', action='store_true',
                       help='Disable JSON export')
    parser.add_argument('--drive-folder-id',
                       help='Google Drive folder ID for uploads')
    parser.add_argument('--archive', action='store_true',
                       help='Also create dated archive file')

    # Pool management arguments
    parser.add_argument('--add-pool', nargs=2, metavar=('CHAIN', 'POOL'),
                       help='Add a new pool to track (e.g., --add-pool ethereum 0xabc...)')
    parser.add_argument('--remove-pool', nargs=2, metavar=('CHAIN', 'POOL'),
                       help='Remove a pool from tracking')
    parser.add_argument('--list-pools', action='store_true',
                       help='List all tracked pools')
    parser.add_argument('--pool-stats', action='store_true',
                       help='Show pool tracking statistics')
    parser.add_argument('--comment',
                       help='Comment/description for --add-pool')
    parser.add_argument('--no-validate', action='store_true',
                       help='Skip validation when adding pool')

    args = parser.parse_args()

    # Handle pool management commands first (these exit after executing)
    if args.add_pool or args.remove_pool or args.list_pools or args.pool_stats:
        try:
            from pool_manager import PoolManager
            manager = PoolManager()

            if args.add_pool:
                chain, pool = args.add_pool
                manager.add_pool(
                    chain=chain,
                    pool=pool,
                    comment=args.comment,
                    stakedao_enabled=args.stakedao if args.stakedao else None,
                    beefy_enabled=args.beefy if args.beefy else None,
                    validate=not args.no_validate
                )
                sys.exit(0)

            if args.remove_pool:
                chain, pool = args.remove_pool
                manager.remove_pool(chain, pool)
                sys.exit(0)

            if args.list_pools:
                pools = manager.list_pools()
                if not pools:
                    print("No pools configured")
                else:
                    print(f"\n📋 Tracked Pools ({len(pools)}):")
                    print("=" * 80)
                    for p in pools:
                        comment = f" - {p['comment']}" if 'comment' in p else ""
                        print(f"  {p['chain']}/{p['pool']}{comment}")
                        if p.get('stakedao_enabled'):
                            print(f"    ✓ StakeDAO enabled")
                        if p.get('beefy_enabled'):
                            print(f"    ✓ Beefy enabled")
                    print("=" * 80)
                sys.exit(0)

            if args.pool_stats:
                manager.print_stats()
                sys.exit(0)

        except ImportError:
            print("❌ Error: pool_manager.py not found")
            print("Make sure pool_manager.py is in the same directory")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Pool management error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Check for StakeDAO and Beefy flags in JSON config or CLI
    enable_stakedao = args.stakedao
    enable_beefy = args.beefy

    # Load JSON file early to check for StakeDAO config
    pools_config = None
    if args.pools:
        try:
            with open(args.pools, 'r') as f:
                pools_config = json.load(f)
                # Check if JSON has StakeDAO or Beefy config
                if isinstance(pools_config, dict):
                    if pools_config.get('enable_stakedao'):
                        enable_stakedao = True
                    if pools_config.get('enable_beefy'):
                        enable_beefy = True
                    pools_config = pools_config.get('pools', [])
        except FileNotFoundError:
            print(f"File {args.pools} not found")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {args.pools}")
            sys.exit(1)
    elif os.path.exists('pools.json'):
        try:
            with open('pools.json', 'r') as f:
                pools_config = json.load(f)
                # Check if JSON has StakeDAO or Beefy config
                if isinstance(pools_config, dict):
                    if pools_config.get('enable_stakedao'):
                        enable_stakedao = True
                    if pools_config.get('enable_beefy'):
                        enable_beefy = True
                    pools_config = pools_config.get('pools', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pools_config = None

    tracker = CurveTracker(enable_stakedao=enable_stakedao, enable_beefy=enable_beefy)

    if enable_stakedao:
        print("🚀 StakeDAO integration enabled")
    if enable_beefy:
        print("🥩 Beefy integration enabled")
    
    if args.pools and pools_config is not None:
        # Use loaded JSON file
        results = tracker.track_pools(pools_config)
    elif args.pool:
        # Single pool
        pool_data = tracker.get_pool_data(args.chain, args.pool)
        results = [pool_data] if pool_data else []
    else:
        # Default: use pools.json if it exists, otherwise show popular pools
        if pools_config is not None:
            results = tracker.track_pools(pools_config)
            print("📄 Using default pools.json file")
        else:
            popular_pools = [
                {'chain': 'ethereum', 'pool': '3pool'},
                {'chain': 'ethereum', 'pool': 'steth'},
                {'chain': 'ethereum', 'pool': 'frxeth'}
            ]
            results = tracker.track_pools(popular_pools)
            print("📄 Using default popular pools (pools.json not found)")
    
    print_results(results)
    
    # Export to Google Sheets (auto-export if credentials available, or if explicitly requested)
    auto_export = False
    
    # Check if we should auto-export (credentials file exists and no explicit --export-sheets flag)
    if not args.export_sheets:
        credentials_file = args.credentials or os.getenv('GOOGLE_CREDENTIALS_FILE') or 'Google Credentials.json'
        if os.path.exists(credentials_file) and SHEETS_AVAILABLE:
            auto_export = True
            args.credentials = credentials_file  # Ensure we use the found credentials file
    
    if args.export_sheets or auto_export:
        if not SHEETS_AVAILABLE:
            print("\n❌ Google Sheets functionality not available.")
            print("Install dependencies with: pip install gspread gspread-dataframe google-auth")
            if args.export_sheets:  # Only exit if explicitly requested
                sys.exit(1)
        elif not results:
            print("\n❌ No data to export to Google Sheets")
            if args.export_sheets:  # Only exit if explicitly requested
                sys.exit(1)
        else:
            try:
                if auto_export:
                    print(f"\n📊 Auto-exporting to Google Sheets (credentials found)...")
                else:
                    print(f"\n📊 Exporting to Google Sheets...")
                
                exporter = GoogleSheetsExporter(args.credentials)
                # Default behavior: replace data (clear previous)
                # Only append if explicitly requested with --append-data
                append_data = args.append_data
                
                exporter.export_to_sheets(
                    results,
                    spreadsheet_id=args.sheet_id,
                    spreadsheet_name=args.sheet_name,
                    append_data=append_data
                )

                # Also export to Log sheet for time-series tracking
                exporter.export_to_log_sheet(
                    results,
                    spreadsheet_id=args.sheet_id,
                    spreadsheet_name=args.sheet_name
                )
            except Exception as e:
                print(f"\n❌ Failed to export to Google Sheets: {e}")
                print("Make sure you have:")
                print("  1. Valid Google credentials")
                print("  2. Shared the spreadsheet with your service account email")
                print("  3. Proper permissions to create/edit spreadsheets")
                if args.export_sheets:  # Only exit if explicitly requested
                    sys.exit(1)
                else:
                    print("💡 Auto-export failed, but continuing with terminal output...")

    # Export to JSON (and optionally upload to Google Drive)
    # JSON export is enabled by default unless --no-json is specified
    if (args.export_json or args.json_only) and not args.no_json:
        if not results:
            print("\n❌ No data to export to JSON")
        else:
            try:
                print(f"\n📦 Exporting to JSON...")

                # Import exporter
                from json_exporter import CurveDataExporter

                exporter = CurveDataExporter(output_dir="data")

                # Export main file
                filepath = exporter.export_to_json(results)

                # Append to cumulative history
                exporter.append_to_history(results)

                # Export archive if requested
                if args.archive:
                    archive_path = exporter.export_daily_archive(results)
                    print(f"📁 Created archive: {archive_path}")

                # Upload to Drive if --export-json (not --json-only)
                if args.export_json and not args.json_only:
                    try:
                        from drive_uploader import DriveUploader

                        print("📤 Uploading to Google Drive...")

                        credentials_file = args.credentials or os.getenv('GOOGLE_CREDENTIALS_FILE') or 'Google Credentials.json'
                        uploader = DriveUploader(
                            creds_file=credentials_file,
                            folder_id=args.drive_folder_id
                        )

                        # Upload main file
                        result = uploader.upload_json(filepath, "curve_pools_latest.json")

                        if result['success']:
                            print(f"✅ JSON data uploaded successfully!")
                            print(f"🔗 Public URL: {result['url']}")
                            print(f"📋 File ID: {result['file_id']}")

                            # Upload archive if created
                            if args.archive:
                                archive_filename = os.path.basename(archive_path)
                                archive_result = uploader.upload_json(archive_path, archive_filename)
                                if archive_result['success']:
                                    print(f"📁 Archive uploaded: {archive_filename}")

                            # Upload history file (cumulative time-series data)
                            history_filepath = os.path.join("data", "curve_pools_history.json")
                            if os.path.exists(history_filepath):
                                history_result = uploader.upload_json(history_filepath, "curve_pools_history.json")
                                if history_result['success']:
                                    print(f"📊 History file uploaded")
                                else:
                                    print(f"⚠️  Warning: History upload failed: {history_result.get('error', 'Unknown error')}")

                            # Cleanup old archives (keep 30 days)
                            deleted = uploader.cleanup_old_archives(days_to_keep=30)
                            if deleted > 0:
                                print(f"🗑️  Cleaned up {deleted} old archive(s)")
                        else:
                            print(f"❌ Upload failed: {result['error']}")
                            sys.exit(1)

                    except ImportError as e:
                        print(f"❌ Error: Missing required libraries for Drive upload")
                        print("Install with: pip install google-api-python-client google-auth")
                        sys.exit(1)
                    except Exception as e:
                        print(f"❌ Failed to upload to Google Drive: {e}")
                        sys.exit(1)
                else:
                    print(f"💾 JSON saved locally: {filepath}")

            except ImportError:
                print("❌ Error: json_exporter.py not found")
                print("Make sure json_exporter.py is in the same directory")
                sys.exit(1)
            except Exception as e:
                print(f"❌ Failed to export JSON: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)


if __name__ == "__main__":
    main()