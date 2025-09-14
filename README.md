# Curve Finance Pool Tracker

A comprehensive Python tool for tracking Curve Finance pool performance with integrated yield optimization data from StakeDAO and Beefy Finance across multiple chains.

## 🚀 Features

- 🔍 **Pool Discovery**: Find pools by address or name across multiple chains
- 💰 **TVL Tracking**: Real-time Total Value Locked calculations
- 📊 **Multi-Platform APY**: Compare yields across Curve, StakeDAO, and Beefy Finance
- 🎯 **CRV Rewards**: Shows reward ranges (min to max boost) with veCRV multipliers
- ⚖️ **Coin Analysis**: Balance distribution and ETH-specific tracking
- 🌐 **Multi-Chain Support**: Ethereum, Fraxtal, Polygon, Arbitrum, Optimism, Base, Fantom and more
- 📈 **Yield Optimization**: Integrated StakeDAO liquid lockers and Beefy vault strategies
- 📋 **Smart Export**: Automated Google Sheets integration with organized data and timestamp tracking
- ⚙️ **Flexible Config**: CLI flags and JSON configuration with modular integration control
- 🔗 **Address Matching**: Intelligent pool matching across platforms using LP token addresses
- 📊 **Dynamic Columns**: Shows integration data only when available (StakeDAO/Beefy)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Today-in-DeFi/CurveTracker.git
cd CurveTracker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Single Pool Query
```bash
# Query by pool address
python3 curve_tracker.py -c ethereum -p "0xc522A6606BBA746d7960404F22a3DB936B6F4F50"

# Query by pool name
python3 curve_tracker.py -c ethereum -p "3pool"

# Query with StakeDAO integration
python3 curve_tracker.py -c ethereum -p "3pool" --stakedao

# Query with Beefy integration
python3 curve_tracker.py -c ethereum -p "3pool" --beefy

# Query with both integrations
python3 curve_tracker.py -c ethereum -p "3pool" --stakedao --beefy
```

### Multiple Pools with JSON Configuration
```bash
# Use JSON file with pool list and integration settings
python3 curve_tracker.py --pools pools.json

# Override JSON settings with CLI flags
python3 curve_tracker.py --pools pools.json --stakedao --beefy
```

### Google Sheets Export
```bash
# Export to Google Sheets (creates spreadsheet if needed)
python3 curve_tracker.py --pools pools.json --export-sheets

# Export with custom credentials file
python3 curve_tracker.py -p "0x123..." --export-sheets --credentials "./service-account.json"

# Export to specific spreadsheet
python3 curve_tracker.py --pools pools.json --export-sheets --sheet-id "1abc123xyz"

# Replace data instead of appending
python3 curve_tracker.py --pools pools.json --export-sheets --replace-data
```

### Enhanced JSON Configuration Format:
```json
{
  "enable_stakedao": false,
  "enable_beefy": false,
  "pools": [
    {
      "chain": "ethereum",
      "pool": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
      "comment": "reUSD/scrvUSD",
      "beefy_available": true,
      "beefy_vault_id": "curve-reusd-scrvusd"
    },
    {
      "chain": "fraxtal",
      "pool": "0x15d1ed4418dA1F268bCAd5BA7c8d06BB3c3081eD",
      "comment": "frxUSD/FXB 2027",
      "gauge_address": "0x7506A3e213C362b9e21895c2Bd930DF454d46573",
      "stakedao_vault": "0xE7B60D6ABBa4E0a801ad29c9b824602aB9a0c439"
    }
  ]
}
```

## Output Examples

### Basic Output
```
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+
| Pool Name     | Chain    | Coins           | Coin Ratios                  | TVL     |   Base APY (%) | CRV Rewards (%)   | Other Rewards (%)   |
+===============+==========+=================+==============================+=========+================+===================+=====================+
| reUSD/scrvUSD | Ethereum | reUSD / scrvUSD | reUSD: 76.0%, scrvUSD: 24.0% | $53.85M |           2.31 | 7.17 - 17.93      | None                |
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+
```

### With StakeDAO and Beefy Integration
```
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+-------------------+-----------------+----------------+
| Pool Name     | Chain    | Coins           | Coin Ratios                  | TVL     |   Base APY (%) | CRV Rewards (%)   | Other Rewards (%)   | StakeDAO APY (%)  | StakeDAO TVL    | Beefy APY (%)  |
+===============+==========+=================+==============================+=========+================+===================+=====================+===================+=================+================+
| reUSD/scrvUSD | Ethereum | reUSD / scrvUSD | reUSD: 76.0%, scrvUSD: 24.0% | $53.85M |           2.31 | 7.17 - 17.93      | None                | 16.75             | $2.85M          | 13.45          |
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+-------------------+-----------------+----------------+
```

## Data Sources

### Curve Finance APIs
- **Pool Data**: `https://api.curve.finance/v1/getPools/all/{chain}`
- **Base APY**: `https://api.curve.finance/v1/getBaseApys/{chain}`
- **Gauge Rewards**: `https://api.curve.finance/v1/getAllGauges`
- **Volume/TVL**: `https://api.curve.finance/v1/getVolumes/{chain}`

### StakeDAO Integration
- **Strategy Data**: `https://api.stakedao.org/api/strategies/curve/{chainId}.json`
- **Chain Support**: Ethereum (chainId: 1), Polygon, Arbitrum, Optimism
- **Data Points**: Projected APR (includes CRV boost), Current TVL, Boost multiplier
- **Matching**: LP token address-based matching with highest TVL selection

### Beefy Finance Integration
- **Vault Data**: `https://api.beefy.finance/vaults`
- **APY Data**: `https://api.beefy.finance/apy`
- **Chain Support**: 20+ chains including Ethereum, Fraxtal, Polygon, Arbitrum
- **Data Points**: Composite APY, Total TVL
- **Matching**: LP token address-based with vault ID fallback

## Supported Chains

### Curve Finance
- **Ethereum** - Full support (Curve + StakeDAO + Beefy)
- **Fraxtal** - Curve support, StakeDAO not available
- **Polygon** - Full Curve + StakeDAO + Beefy support
- **Arbitrum** - Full Curve + StakeDAO + Beefy support
- **Optimism** - Full Curve + StakeDAO + Beefy support
- **Base** - Curve + Beefy support
- **Fantom** - Curve + Beefy support
- **And more...** - 15+ additional chains via Curve and Beefy APIs

### Integration Availability
- **StakeDAO**: Ethereum, Polygon, Arbitrum, Optimism (chainId mapping required)
- **Beefy**: 20+ chains including all major L1s and L2s
- **Manual Pool Data**: Supported for pools not available via APIs

## Understanding the Output

### Core Columns
- **Pool Name**: Curve pool identifier
- **Chain**: Blockchain network
- **Coins**: Token pairs in the pool
- **Coin Ratios**: Balance distribution (e.g., 76% Token A, 24% Token B)
- **TVL**: Total Value Locked in USD
- **Base APY**: Yield from trading fees
- **CRV Rewards**: CRV token rewards range (min = no boost, max = 2.5x boost)
- **Other Rewards**: Additional incentive tokens (LDO, ARB, etc.)

### StakeDAO Columns (when enabled)
- **StakeDAO APY**: Projected APY including CRV boost from liquid locking
- **StakeDAO TVL**: Total Value Locked in StakeDAO strategy
- **StakeDAO Boost**: Boost multiplier from sdCRV (liquid veCRV)

### Beefy Columns (when enabled)
- **Beefy APY**: Auto-compound yield optimization APY
- **Beefy TVL**: Total Value Locked in Beefy vault

### Understanding Yields
- **Base APY**: Trading fees only, always available
- **CRV Rewards Range**:
  - Minimum (e.g., 7.17%): No veCRV boost
  - Maximum (e.g., 17.93%): Maximum 2.5x boost with locked veCRV
- **StakeDAO APY**: Liquid CRV locking, no lock-up period required
- **Beefy APY**: Auto-compounding strategy, optimal for passive investors

## Google Sheets Setup

### 1. Get Google Service Account Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a Service Account and download the JSON credentials file
5. Save it as `Google Credentials.json` in your project folder

### 2. Configure Environment (Optional)

Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
# Edit .env with your credentials path
```

### 3. Share Spreadsheet

Share your Google Spreadsheet with the service account email (found in the credentials JSON file)

## Command Line Options

```bash
python3 curve_tracker.py --help
```

### Basic Options:
- `-c, --chain`: Blockchain (default: ethereum)
- `-p, --pool`: Pool address or name
- `-P, --pools`: JSON file with pool list

### Integration Options:
- `--stakedao`: Enable StakeDAO liquid locking data
- `--beefy`: Enable Beefy Finance yield optimization data

### Google Sheets Options:
- `--export-sheets`: Enable Google Sheets export
- `--credentials`: Path to service account JSON file
- `--sheet-id`: Specific spreadsheet ID to use
- `--sheet-name`: Spreadsheet name (default: "Curve Pool Tracker")
- `--replace-data`: Replace data instead of appending

### Configuration Priority:
1. CLI flags (highest priority)
2. JSON configuration file settings
3. Default values (lowest priority)

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Disclaimer

This tool is for informational purposes only. Always verify data independently before making financial decisions.