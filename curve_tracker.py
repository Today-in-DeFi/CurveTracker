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
import os
from datetime import datetime
from dotenv import load_dotenv

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
        # Fraxtal is now supported by Curve API, so no manual overrides needed
        manual_pools = {}

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
                        'usd_value': usd_value
                    })

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
    
    def get_or_create_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str, use_eth_units: bool = False) -> gspread.Worksheet:
        """Get existing worksheet or create new one with headers"""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"✅ Found existing sheet: {sheet_name}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"📝 Creating new sheet: {sheet_name}")
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=12)

            # Asset ratio column should always be "Coin Ratios" with percentages
            coin_column = 'Coin Ratios'

            headers = [
                'Date', 'Time', 'Pool Name', coin_column,
                'TVL (USD)', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
                'Other Rewards', 'Address', 'StakeDAO APY (%)', 'StakeDAO TVL (USD)',
                'StakeDAO Boost', 'Beefy APY (%)', 'Beefy TVL (USD)'
            ]
            worksheet.update(values=[headers], range_name='A1:O1')
            print(f"📋 Added headers to new sheet")

            return worksheet
    
    def format_data_for_sheets(self, pool_data_list: List[PoolData], use_eth_units: bool = False) -> pd.DataFrame:
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

            rows.append([
                date_str,
                time_str,
                pool.name,
                coin_data_str,
                pool.tvl,
                pool.base_apy,
                crv_min,
                crv_max,
                other_rewards_str,
                pool.address,
                pool.stakedao_apy if pool.stakedao_apy is not None else "",
                pool.stakedao_tvl if pool.stakedao_tvl is not None else "",
                pool.stakedao_boost if pool.stakedao_boost is not None else "",
                pool.beefy_apy if pool.beefy_apy is not None else "",
                pool.beefy_tvl if pool.beefy_tvl is not None else ""
            ])

        # Asset ratio column should always be called "Coin Ratios"
        coin_column = 'Coin Ratios'

        columns = [
            'Date', 'Time', 'Pool Name', coin_column,
            'TVL (USD)', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
            'Other Rewards', 'Address', 'StakeDAO APY (%)', 'StakeDAO TVL (USD)',
            'StakeDAO Boost', 'Beefy APY (%)', 'Beefy TVL (USD)'
        ]

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
            # Check if this is an ETH category
            is_eth_category = "ETH" in category
            worksheet = self.get_or_create_worksheet(spreadsheet, category, use_eth_units=is_eth_category)

            # Convert to DataFrame - asset ratios always use percentages regardless of pool type
            df = self.format_data_for_sheets(pools, use_eth_units=False)
            
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

    args = parser.parse_args()

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


if __name__ == "__main__":
    main()