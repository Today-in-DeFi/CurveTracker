# CurveTracker Data Access

Comprehensive Curve Finance pool data with integrated yield optimization data from StakeDAO and Beefy Finance is automatically exported to Google Drive every hour.

## Quick Links

**Latest Data (Always Current):**
```
https://drive.google.com/uc?export=download&id=YOUR_FILE_ID_HERE
```

**Drive Folder (All Files):**
```
https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE
```

**Local Path:**
```
/home/danger/CurveTracker/data/curve_pools_latest.json
```

---

## Data Structure

The JSON file contains:
- **Metadata**: Generation timestamp, source, total pools tracked, supported chains
- **Pools Array**: Latest data + optional 7-day history for each pool
  - **Latest data**: TVL, APYs (Base + CRV + Other rewards), coin ratios, StakeDAO/Beefy yields
  - **7-day history**: Daily snapshots with APY trends (optional)
  - **Metadata**: Pool addresses, chain info, integration availability

---

## JSON Schema

### Root Structure
```json
{
  "version": "1.0",
  "metadata": {
    "generated_at": "2025-11-20T16:30:00Z",
    "source": "CurveTracker v1.0",
    "total_pools": 5,
    "chains": ["ethereum", "fraxtal"],
    "data_freshness_hours": 1,
    "integrations": ["Curve", "StakeDAO", "Beefy"]
  },
  "pools": [ /* pool array */ ]
}
```

### Pool Object
```json
{
  "id": "ethereum_reusd_scrvusd",
  "name": "reUSD/scrvUSD",
  "chain": "ethereum",
  "latest": {
    "timestamp": "2025-11-20T16:30:00Z",
    "coins": "reUSD / scrvUSD",
    "coin_ratios": "reUSD: 76.0%, scrvUSD: 24.0%",
    "tvl_usd": "$53.85M",
    "tvl_raw": 53850000.0,
    "base_apy": 2.31,
    "crv_rewards": {
      "min": 7.17,
      "max": 17.93,
      "range_text": "7.17 - 17.93"
    },
    "other_rewards": [
      {
        "token": "LDO",
        "apy": 1.25
      }
    ],
    "total_apy": 11.73,
    "stakedao": {
      "apy": 16.75,
      "tvl": 2850000.0,
      "boost": 1.32,
      "fees": "15% performance fee"
    },
    "beefy": {
      "apy": 13.45,
      "tvl": 1250000.0,
      "vault_id": "curve-eth-reusd-scrvusd"
    },
    "coin_details": [
      {
        "name": "reUSD",
        "amount": 40850000.0,
        "price": 1.0012
      },
      {
        "name": "scrvUSD",
        "amount": 12920000.0,
        "price": 1.0005
      }
    ]
  },
  "metadata": {
    "pool_address": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50"
  }
}
```

---

## Field Descriptions

### Metadata Object

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 timestamp of data generation |
| `source` | string | Data source identifier |
| `total_pools` | integer | Number of pools in export |
| `chains` | array | List of blockchain networks |
| `data_freshness_hours` | integer | Update frequency (1 = hourly) |
| `integrations` | array | Active data integrations |

### Pool Object

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique pool identifier (chain_poolname) |
| `name` | string | Pool display name |
| `chain` | string | Blockchain network |
| `latest.timestamp` | string | Last update timestamp |
| `latest.coins` | string | Token pairs in pool |
| `latest.coin_ratios` | string | Balance distribution |
| `latest.tvl_usd` | string | Formatted TVL with suffix |
| `latest.tvl_raw` | float | Raw TVL value in USD |
| `latest.base_apy` | float | Trading fee APY |
| `latest.total_apy` | float | Combined APY (base + CRV + other) |
| `metadata.pool_address` | string | Pool contract address |

#### CRV Rewards Object

| Field | Type | Description |
|-------|------|-------------|
| `crv_rewards.min` | float | CRV APY with no veCRV boost |
| `crv_rewards.max` | float | CRV APY with maximum 2.5x boost |
| `crv_rewards.range_text` | string | Formatted range string |

#### Other Rewards Array

```json
[
  {
    "token": "LDO",
    "apy": 1.25
  }
]
```

#### StakeDAO Object (optional)

| Field | Type | Description |
|-------|------|-------------|
| `stakedao.apy` | float | Projected APY with sdCRV boost |
| `stakedao.tvl` | float | TVL in StakeDAO strategy |
| `stakedao.boost` | float | Current boost multiplier |
| `stakedao.fees` | string | Fee structure description |

#### Beefy Object (optional)

| Field | Type | Description |
|-------|------|-------------|
| `beefy.apy` | float | Auto-compound APY |
| `beefy.tvl` | float | TVL in Beefy vault |
| `beefy.vault_id` | string | Beefy vault identifier |

#### Coin Details Array (optional)

```json
[
  {
    "name": "reUSD",
    "amount": 40850000.0,
    "price": 1.0012
  }
]
```

---

## Usage Examples

### Python

#### Basic Fetch
```python
import requests

url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
data = requests.get(url).json()

print(f"Total pools: {data['metadata']['total_pools']}")
print(f"Last updated: {data['metadata']['generated_at']}")

# Get specific pool
for pool in data['pools']:
    if pool['name'] == 'reUSD/scrvUSD':
        print(f"Base APY: {pool['latest']['base_apy']}%")
        print(f"CRV Rewards: {pool['latest']['crv_rewards']['range_text']}%")
        if 'stakedao' in pool['latest']:
            print(f"StakeDAO APY: {pool['latest']['stakedao']['apy']}%")
        break
```

#### Find Pools with Highest Base APY
```python
import requests

url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
data = requests.get(url).json()

# Sort by base APY
sorted_pools = sorted(
    data['pools'],
    key=lambda p: p['latest']['base_apy'],
    reverse=True
)

print("Top 5 Pools by Base APY:")
for pool in sorted_pools[:5]:
    print(f"{pool['name']} ({pool['chain']}): {pool['latest']['base_apy']}%")
```

#### Filter by Chain
```python
import requests

url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
data = requests.get(url).json()

# Get all Ethereum pools
eth_pools = [p for p in data['pools'] if p['chain'] == 'ethereum']

print(f"Ethereum pools: {len(eth_pools)}")
for pool in eth_pools:
    print(f"  {pool['name']}: TVL {pool['latest']['tvl_usd']}")
```

#### Find Pools with StakeDAO Integration
```python
import requests

url = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"
data = requests.get(url).json()

stakedao_pools = [
    p for p in data['pools']
    if 'stakedao' in p['latest']
]

print(f"Pools with StakeDAO: {len(stakedao_pools)}")
for pool in stakedao_pools:
    stakedao = pool['latest']['stakedao']
    print(f"{pool['name']}: {stakedao['apy']}% APY (boost: {stakedao['boost']}x)")
```

---

### JavaScript / Node.js

#### Basic Fetch
```javascript
const url = 'https://drive.google.com/uc?export=download&id=YOUR_FILE_ID';

fetch(url)
  .then(r => r.json())
  .then(data => {
    console.log(`Total pools: ${data.metadata.total_pools}`);
    console.log(`Last updated: ${data.metadata.generated_at}`);

    // Find specific pool
    const pool = data.pools.find(p => p.name === 'reUSD/scrvUSD');
    if (pool) {
      console.log(`Base APY: ${pool.latest.base_apy}%`);
      console.log(`TVL: ${pool.latest.tvl_usd}`);
    }
  });
```

#### Compare Yields Across Platforms
```javascript
const url = 'https://drive.google.com/uc?export=download&id=YOUR_FILE_ID';

fetch(url)
  .then(r => r.json())
  .then(data => {
    data.pools.forEach(pool => {
      const latest = pool.latest;
      console.log(`\n${pool.name} (${pool.chain}):`);
      console.log(`  Base APY: ${latest.base_apy}%`);
      console.log(`  CRV Rewards: ${latest.crv_rewards.range_text}%`);

      if (latest.stakedao) {
        console.log(`  StakeDAO: ${latest.stakedao.apy}%`);
      }

      if (latest.beefy) {
        console.log(`  Beefy: ${latest.beefy.apy}%`);
      }
    });
  });
```

---

### Bash / curl

#### Download Latest Data
```bash
curl -L "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" > curve_pools.json
```

#### Quick Stats with jq
```bash
# Total pools
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq '.metadata.total_pools'

# Last update time
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq -r '.metadata.generated_at'

# List all pool names
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq -r '.pools[].name'

# Get pool with highest base APY
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq -r '.pools | sort_by(-.latest.base_apy) | .[0] | "\(.name): \(.latest.base_apy)%"'

# Find pools with >$10M TVL
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq -r '.pools[] | select(.latest.tvl_raw > 10000000) | "\(.name): \(.latest.tvl_usd)"'

# Get all Ethereum pools
curl -sL "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" | \
  jq -r '.pools[] | select(.chain == "ethereum") | .name'
```

---

### Excel / Google Sheets

#### Power Query (Excel)
1. Data → Get Data → From Web
2. Enter URL: `https://drive.google.com/uc?export=download&id=YOUR_FILE_ID`
3. Click "Into Table" → Expand columns

#### Google Sheets (Apps Script)
```javascript
function importCurveData() {
  const url = 'https://drive.google.com/uc?export=download&id=YOUR_FILE_ID';
  const response = UrlFetchApp.fetch(url);
  const data = JSON.parse(response.getContentText());

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.clear();

  // Headers
  sheet.appendRow([
    'Pool Name', 'Chain', 'TVL', 'Base APY',
    'CRV Min', 'CRV Max', 'Total APY', 'StakeDAO APY', 'Beefy APY'
  ]);

  // Data
  data.pools.forEach(pool => {
    sheet.appendRow([
      pool.name,
      pool.chain,
      pool.latest.tvl_usd,
      pool.latest.base_apy,
      pool.latest.crv_rewards.min,
      pool.latest.crv_rewards.max,
      pool.latest.total_apy,
      pool.latest.stakedao ? pool.latest.stakedao.apy : 'N/A',
      pool.latest.beefy ? pool.latest.beefy.apy : 'N/A'
    ]);
  });
}
```

---

## Understanding the Data

### APY Types

1. **Base APY**: Trading fees earned by liquidity providers
2. **CRV Rewards**:
   - **Min**: Rewards with no veCRV boost (1x)
   - **Max**: Rewards with maximum veCRV boost (2.5x)
3. **Other Rewards**: Additional token incentives (LDO, ARB, etc.)
4. **Total APY**: Base + CRV (average) + Other rewards
5. **StakeDAO APY**: Liquid CRV locking via sdCRV (no lock-up)
6. **Beefy APY**: Auto-compounding vault strategy

### Yield Optimization Strategies

**Best for passive investors:**
- Use **Beefy APY** for set-and-forget auto-compounding
- No need to manually claim and compound rewards

**Best for active investors:**
- Use **StakeDAO APY** for liquid CRV exposure
- Combines trading fees + boosted CRV without locking

**Best for maximum returns:**
- Lock CRV for veCRV to achieve **CRV Max** rewards
- Requires 4-year lock for maximum boost

---

## Data Update Frequency

- **Hourly updates**: New data generated every hour via cron job
- **Historical data**: 7-day rolling window (optional)
- **Archive retention**: Daily archives kept for 30 days

---

## Rate Limits

Google Drive public links have generous rate limits:
- **Free tier**: ~1000 requests per 100 seconds per user
- **Sufficient for**: Most personal/small-team use cases
- **Tip**: Cache responses locally if querying frequently

---

## Supported Chains

- **Ethereum** - Full support (Curve + StakeDAO + Beefy)
- **Fraxtal** - Curve + Beefy support
- **Polygon** - Full Curve + Beefy support
- **Arbitrum** - Full Curve + StakeDAO + Beefy support
- **Optimism** - Full Curve + StakeDAO + Beefy support
- **Base** - Curve + Beefy support
- **And more...** - 15+ chains via Curve and Beefy APIs

---

## Integration Availability

Not all pools have StakeDAO or Beefy integrations. Check for presence of fields:

```python
pool = data['pools'][0]

# Check if StakeDAO data available
if 'stakedao' in pool['latest']:
    print(f"StakeDAO APY: {pool['latest']['stakedao']['apy']}%")
else:
    print("No StakeDAO integration for this pool")

# Check if Beefy data available
if 'beefy' in pool['latest']:
    print(f"Beefy APY: {pool['latest']['beefy']['apy']}%")
else:
    print("No Beefy integration for this pool")
```

---

## Support

For issues or questions:
- **GitHub**: https://github.com/Today-in-DeFi/CurveTracker/issues
- **Local Logs**: `/home/danger/CurveTracker/logs/`
- **Cron Logs**: Check `logs/export_YYYYMMDD.log`

---

## License

Data provided as-is. Use at your own risk. Not financial advice.

---

## Changelog

### Version 1.0 (2025-11-20)
- Initial release
- Support for Curve Finance core data
- StakeDAO integration (Ethereum, Arbitrum, Optimism)
- Beefy Finance integration (20+ chains)
- Hourly updates via cron
- 30-day archive retention
