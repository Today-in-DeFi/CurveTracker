# Curve Finance Pool Tracker

A Python script to track Curve Finance pools across multiple chains, providing comprehensive data on TVL, APY, CRV rewards, and coin ratios.

## Features

- 🔍 **Pool Discovery**: Find pools by address or name
- 💰 **TVL Tracking**: Real-time Total Value Locked calculations
- 📊 **APY Analysis**: Base APY from trading fees
- 🎯 **CRV Rewards**: Shows reward ranges (min to max boost)
- ⚖️ **Coin Ratios**: Balance distribution within pools
- 🌐 **Multi-Chain Support**: Ethereum, Polygon, Arbitrum, and more
- 📋 **Clean Output**: Tabular format for easy comparison

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
```

### Multiple Pools
```bash
# Use JSON file with pool list
python3 curve_tracker.py --pools pools_example.json
```

### Google Sheets Export
```bash
# Export to Google Sheets (creates spreadsheet if needed)
python3 curve_tracker.py --pools pools_example.json --export-sheets

# Export with custom credentials file
python3 curve_tracker.py -p "0x123..." --export-sheets --credentials "./service-account.json"

# Export to specific spreadsheet
python3 curve_tracker.py --pools pools.json --export-sheets --sheet-id "1abc123xyz"

# Replace data instead of appending
python3 curve_tracker.py --pools pools.json --export-sheets --replace-data
```

### Example JSON format (pools_example.json):
```json
[
  {
    "chain": "ethereum",
    "pool": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50"
  },
  {
    "chain": "ethereum", 
    "pool": "3pool"
  }
]
```

## Output Example

```
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+
| Pool Name     | Chain    | Coins           | Coin Ratios                  | TVL     |   Base APY (%) | CRV Rewards (%)   | Other Rewards (%)   |
+===============+==========+=================+==============================+=========+================+===================+=====================+
| reUSD/scrvUSD | Ethereum | reUSD / scrvUSD | reUSD: 76.0%, scrvUSD: 24.0% | $53.85M |           2.31 | 7.17 - 17.93      | None                |
+---------------+----------+-----------------+------------------------------+---------+----------------+-------------------+---------------------+
```

## Data Sources

The script uses official Curve Finance APIs:
- **Pool Data**: `https://api.curve.finance/v1/getPools/all/{chain}`
- **Base APY**: `https://api.curve.finance/v1/getBaseApys/{chain}`
- **Gauge Rewards**: `https://api.curve.finance/v1/getAllGauges`
- **Volume/TVL**: `https://api.curve.finance/v1/getVolumes/{chain}`

## Supported Chains

- Ethereum
- Polygon  
- Arbitrum
- Optimism
- Base
- Fantom
- And more...

## Understanding the Output

### Columns Explained

- **Pool Name**: Curve pool identifier
- **Chain**: Blockchain network
- **Coins**: Token pairs in the pool
- **Coin Ratios**: Balance distribution (e.g., 76% Token A, 24% Token B)
- **TVL**: Total Value Locked in USD
- **Base APY**: Yield from trading fees
- **CRV Rewards**: CRV token rewards range (min = no boost, max = 2.5x boost)
- **Other Rewards**: Additional incentive tokens (LDO, ARB, etc.)

### CRV Rewards Range
- **Minimum (e.g., 7.17%)**: No veCRV boost
- **Maximum (e.g., 17.93%)**: Maximum 2.5x boost with locked veCRV
- **Your actual APY** depends on how much CRV you lock for voting

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

### Google Sheets Options:
- `--export-sheets`: Enable Google Sheets export
- `--credentials`: Path to service account JSON file
- `--sheet-id`: Specific spreadsheet ID to use
- `--sheet-name`: Spreadsheet name (default: "Curve Pool Tracker")
- `--replace-data`: Replace data instead of appending

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Disclaimer

This tool is for informational purposes only. Always verify data independently before making financial decisions.