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


class CurveTracker:
    def __init__(self):
        self.api = CurveAPI()
        self._pools_cache = {}
        self._gauges_cache = {}
        self._apys_cache = {}
        self._volumes_cache = {}
    
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
    
    def get_pool_data(self, chain: str, pool_identifier: str) -> Optional[PoolData]:
        """Get comprehensive pool data by address or name"""
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
            
            # Check for other reward tokens
            side_chain_rewards_apy = gauge_data.get('sideChainRewardsApy', 0)
            if side_chain_rewards_apy > 0:
                other_rewards.append({
                    'token': 'Side Chain Rewards',
                    'apy': side_chain_rewards_apy * 100
                })
        
        # Get coin information and calculate ratios
        coins = []
        coin_ratios = []
        if 'coins' in pool:
            total_usd_value = 0
            coin_values = []
            
            # First pass: calculate USD values
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
                        'usd_value': usd_value
                    })
                else:
                    coins.append(str(coin))
            
            # Second pass: calculate ratios
            for coin_data in coin_values:
                if total_usd_value > 0:
                    ratio = (coin_data['usd_value'] / total_usd_value) * 100
                    coin_ratios.append(f"{coin_data['symbol']}: {ratio:.1f}%")
                else:
                    coin_ratios.append(f"{coin_data['symbol']}: 0.0%")
        
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
            coin_ratios=coin_ratios
        )
    
    def track_pools(self, pools: List[Dict[str, str]]) -> List[PoolData]:
        """Track multiple pools"""
        results = []
        for pool_info in pools:
            chain = pool_info['chain']
            pool_id = pool_info['pool']
            
            pool_data = self.get_pool_data(chain, pool_id)
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
    
    def get_or_create_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str) -> gspread.Worksheet:
        """Get existing worksheet or create new one with headers"""
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"✅ Found existing sheet: {sheet_name}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"📝 Creating new sheet: {sheet_name}")
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=12)
            
            # Add headers
            headers = [
                'Date', 'Time', 'Pool Name', 'Chain', 'Coins', 'Coin Ratios', 
                'TVL', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)', 
                'Other Rewards', 'Address'
            ]
            worksheet.update('A1:L1', [headers])
            print(f"📋 Added headers to new sheet")
            
            return worksheet
    
    def format_data_for_sheets(self, pool_data_list: List[PoolData]) -> pd.DataFrame:
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
            
            # Format coins and ratios
            coins_str = " / ".join(pool.coins)
            ratios_str = ", ".join(pool.coin_ratios)
            
            rows.append([
                date_str,
                time_str,
                pool.name,
                pool.chain.title(),
                coins_str,
                ratios_str,
                pool.tvl,
                pool.base_apy,
                crv_min,
                crv_max,
                other_rewards_str,
                pool.address
            ])
        
        columns = [
            'Date', 'Time', 'Pool Name', 'Chain', 'Coins', 'Coin Ratios',
            'TVL', 'Base APY (%)', 'CRV Rewards Min (%)', 'CRV Rewards Max (%)',
            'Other Rewards', 'Address'
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
        
        # Group pools by chain
        pools_by_chain = {}
        for pool in pool_data_list:
            chain = pool.chain.title()
            if chain not in pools_by_chain:
                pools_by_chain[chain] = []
            pools_by_chain[chain].append(pool)
        
        # Export each chain to its own worksheet
        for chain, pools in pools_by_chain.items():
            sheet_name = f"{chain} Pools"
            worksheet = self.get_or_create_worksheet(spreadsheet, sheet_name)
            
            # Convert to DataFrame
            df = self.format_data_for_sheets(pools)
            
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
                    print(f"📈 Appended {len(df)} rows to {sheet_name} (total: {len(combined_df)})")
                    
                except Exception as e:
                    print(f"⚠️  Error appending data, replacing instead: {e}")
                    set_with_dataframe(worksheet, df, include_index=False)
                    print(f"📝 Replaced data in {sheet_name} with {len(df)} rows")
            else:
                # Replace all data
                worksheet.clear()
                set_with_dataframe(worksheet, df, include_index=False)
                print(f"📝 Updated {sheet_name} with {len(df)} pools")
        
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
        
        rows.append([
            pool.name[:25] + "..." if len(pool.name) > 25 else pool.name,
            pool.chain.title(),
            coins_str,
            ratios_str,
            format_currency(pool.tvl),
            f"{pool.base_apy:.2f}",
            crv_rewards_str,
            other_rewards_str
        ])
    
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def main():
    parser = argparse.ArgumentParser(description="Track Curve Finance pools")
    parser.add_argument('--chain', '-c', default='ethereum', 
                       help='Blockchain (default: ethereum)')
    parser.add_argument('--pool', '-p', 
                       help='Pool address or name')
    parser.add_argument('--pools', '-P',
                       help='JSON file with pool list')
    
    # Google Sheets arguments
    parser.add_argument('--export-sheets', action='store_true',
                       help='Export results to Google Sheets')
    parser.add_argument('--credentials', 
                       help='Path to Google service account credentials JSON file')
    parser.add_argument('--sheet-id',
                       help='Google Sheets spreadsheet ID')
    parser.add_argument('--sheet-name',
                       help='Google Sheets spreadsheet name (default: "Curve Pool Tracker")')
    parser.add_argument('--replace-data', action='store_true',
                       help='Replace existing data instead of appending (default: append)')
    
    args = parser.parse_args()
    
    tracker = CurveTracker()
    
    if args.pools:
        # Load from JSON file
        try:
            with open(args.pools, 'r') as f:
                pools = json.load(f)
            results = tracker.track_pools(pools)
        except FileNotFoundError:
            print(f"File {args.pools} not found")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {args.pools}")
            sys.exit(1)
    elif args.pool:
        # Single pool
        pool_data = tracker.get_pool_data(args.chain, args.pool)
        results = [pool_data] if pool_data else []
    else:
        # Default: show popular pools
        popular_pools = [
            {'chain': 'ethereum', 'pool': '3pool'},
            {'chain': 'ethereum', 'pool': 'steth'},
            {'chain': 'ethereum', 'pool': 'frxeth'}
        ]
        results = tracker.track_pools(popular_pools)
    
    print_results(results)
    
    # Export to Google Sheets if requested
    if args.export_sheets:
        if not SHEETS_AVAILABLE:
            print("\n❌ Google Sheets functionality not available.")
            print("Install dependencies with: pip install gspread gspread-dataframe google-auth")
            sys.exit(1)
        
        if not results:
            print("\n❌ No data to export to Google Sheets")
            sys.exit(1)
        
        try:
            print(f"\n📊 Exporting to Google Sheets...")
            exporter = GoogleSheetsExporter(args.credentials)
            exporter.export_to_sheets(
                results,
                spreadsheet_id=args.sheet_id,
                spreadsheet_name=args.sheet_name,
                append_data=not args.replace_data
            )
        except Exception as e:
            print(f"\n❌ Failed to export to Google Sheets: {e}")
            print("Make sure you have:")
            print("  1. Valid Google credentials")
            print("  2. Shared the spreadsheet with your service account email")
            print("  3. Proper permissions to create/edit spreadsheets")
            sys.exit(1)


if __name__ == "__main__":
    main()