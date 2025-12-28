# Pool Management Guide

Complete guide for programmatically managing pools in CurveTracker.

## Overview

CurveTracker provides multiple ways to add, remove, and manage tracked pools:

1. **CLI Commands** - Quick management via command line
2. **Python Module** - Programmatic access for scripts
3. **Webhook Server** - HTTP API for external integrations
4. **Auto-Discovery** - Automatically find and add high-value pools

---

## Quick Start

### CLI Commands

```bash
# Add a single pool
python3 curve_tracker.py --add-pool ethereum 0xabc... --comment "My Pool"

# Remove a pool
python3 curve_tracker.py --remove-pool ethereum 0xabc...

# List all tracked pools
python3 curve_tracker.py --list-pools

# Show tracking statistics
python3 curve_tracker.py --pool-stats
```

### Python Module

```python
from pool_manager import PoolManager

manager = PoolManager()

# Add a pool
manager.add_pool(
    chain="ethereum",
    pool="0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
    comment="reUSD/scrvUSD",
    stakedao_enabled=True,
    beefy_enabled=True
)

# List pools
pools = manager.list_pools()
for pool in pools:
    print(f"{pool['chain']}/{pool['pool']}")
```

---

## CLI Reference

### Add Pool

```bash
python3 curve_tracker.py --add-pool CHAIN POOL [OPTIONS]

Options:
  --comment TEXT          Human-readable description
  --stakedao              Enable StakeDAO for this pool
  --beefy                 Enable Beefy for this pool
  --no-validate           Skip pool validation

Examples:
  # Basic add
  python3 curve_tracker.py --add-pool ethereum 0xabc123...

  # With comment and integrations
  python3 curve_tracker.py --add-pool ethereum 0xabc123... \
    --comment "High APY stablecoin pool" \
    --stakedao --beefy

  # Skip validation (faster, but pool may not exist)
  python3 curve_tracker.py --add-pool ethereum 0xabc123... \
    --no-validate
```

### Remove Pool

```bash
python3 curve_tracker.py --remove-pool CHAIN POOL

Example:
  python3 curve_tracker.py --remove-pool ethereum 0xabc123...
```

### List Pools

```bash
python3 curve_tracker.py --list-pools

Output example:
  📋 Tracked Pools (7):
  ================================================================================
    ethereum/0xc522A6606BBA746d7960404F22a3DB936B6F4F50 - reUSD/scrvUSD
      ✓ StakeDAO enabled
      ✓ Beefy enabled
    ethereum/0x72310DAAed61321b02B08A547150c07522c6a976 - USDC/USDf
      ✓ StakeDAO enabled
      ✓ Beefy enabled
  ================================================================================
```

### Pool Statistics

```bash
python3 curve_tracker.py --pool-stats

Output example:
  📊 Pool Tracking Statistics
  ==================================================
  Total Pools: 7
  Chains: ethereum, fraxtal

  Pools per chain:
    ethereum: 6
    fraxtal: 1

  Integrations:
    Global StakeDAO: ✓
    Global Beefy: ✓
    Pools with StakeDAO: 7
    Pools with Beefy: 6
  ==================================================
```

---

## Python Module API

### PoolManager Class

#### Initialization

```python
from pool_manager import PoolManager

# Use default config file (pools.json)
manager = PoolManager()

# Use custom config file
manager = PoolManager(config_file="my_pools.json")
```

#### Add Pool

```python
manager.add_pool(
    chain: str,                          # Required
    pool: str,                           # Required (address or name)
    comment: Optional[str] = None,       # Description
    stakedao_enabled: Optional[bool] = None,
    beefy_enabled: Optional[bool] = None,
    gauge_address: Optional[str] = None,
    stakedao_vault: Optional[str] = None,
    validate: bool = True                # Validate via Curve API
) -> bool

# Returns True if added, False if already exists

# Example
success = manager.add_pool(
    chain="ethereum",
    pool="0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
    comment="reUSD/scrvUSD - High yield",
    stakedao_enabled=True,
    beefy_enabled=True
)
```

#### Remove Pool

```python
manager.remove_pool(
    chain: str,
    pool: str
) -> bool

# Returns True if removed, False if not found

# Example
manager.remove_pool("ethereum", "0xc522...")
```

#### Update Pool

```python
manager.update_pool(
    chain: str,
    pool: str,
    comment: Optional[str] = None,
    stakedao_enabled: Optional[bool] = None,
    beefy_enabled: Optional[bool] = None,
    gauge_address: Optional[str] = None,
    stakedao_vault: Optional[str] = None
) -> bool

# Example - disable StakeDAO for a pool
manager.update_pool(
    chain="ethereum",
    pool="0xc522...",
    stakedao_enabled=False
)
```

#### List Pools

```python
manager.list_pools(
    chain: Optional[str] = None,
    stakedao_only: bool = False,
    beefy_only: bool = False
) -> List[Dict]

# Examples
all_pools = manager.list_pools()
eth_pools = manager.list_pools(chain="ethereum")
stakedao_pools = manager.list_pools(stakedao_only=True)
```

#### Check Pool Exists

```python
exists = manager.pool_exists(
    chain: str,
    pool: str
) -> bool

# Example
if manager.pool_exists("ethereum", "0xabc..."):
    print("Pool already tracked")
```

#### Get Pool Config

```python
pool_config = manager.get_pool(
    chain: str,
    pool: str
) -> Optional[Dict]

# Example
config = manager.get_pool("ethereum", "0xc522...")
if config:
    print(f"Comment: {config.get('comment')}")
    print(f"StakeDAO: {config.get('stakedao_enabled')}")
```

#### Bulk Operations

```python
# Bulk add pools
pools = [
    {
        "chain": "ethereum",
        "pool": "0xabc...",
        "comment": "Pool 1",
        "stakedao_enabled": True
    },
    {
        "chain": "ethereum",
        "pool": "0xdef...",
        "comment": "Pool 2",
        "beefy_enabled": True
    }
]

results = manager.bulk_add_pools(pools)
# Returns: {'added': 2, 'skipped': 0, 'failed': 0}

print(f"Added: {results['added']}")
print(f"Skipped: {results['skipped']}")
print(f"Failed: {results['failed']}")
```

#### Global Settings

```python
# Set global integration flags
manager.set_global_integrations(
    enable_stakedao=True,
    enable_beefy=True
)
```

#### Import/Export

```python
# Export config
export_path = manager.export_config("backup.json")

# Import config (merge with existing)
manager.import_config("backup.json", merge=True)

# Import config (replace existing)
manager.import_config("new_config.json", merge=False)
```

#### Statistics

```python
# Get stats dict
stats = manager.get_stats()
print(f"Total pools: {stats['total_pools']}")
print(f"Chains: {stats['chains']}")

# Print formatted stats
manager.print_stats()
```

---

## Example Scripts

All examples are in the `examples/` directory.

### 1. Add Single Pool

```bash
python3 examples/add_single_pool.py
```

Demonstrates basic pool addition with all options.

### 2. Bulk Add Pools

```bash
python3 examples/bulk_add_pools.py
```

Add multiple pools at once from a predefined list.

### 3. Auto-Discover Pools

```bash
python3 examples/auto_discover_pools.py
```

Automatically discovers high-TVL pools from Curve and prompts to add them.

**Features:**
- Fetches all pools from Curve API
- Filters by TVL threshold
- Shows top pools
- Allows batch addition

### 4. Webhook Listener

```bash
python3 examples/webhook_listener.py
```

Starts an HTTP server for remote pool management.

**Endpoints:**
- `POST /add-pool` - Add a pool
- `POST /remove-pool` - Remove a pool
- `POST /list-pools` - List all pools

**Example request:**
```bash
curl -X POST http://localhost:8080/add-pool \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum",
    "pool": "0xabc...",
    "comment": "My Pool",
    "stakedao_enabled": true,
    "beefy_enabled": true
  }'
```

### 5. Monitor and Auto-Add

```bash
python3 examples/monitor_and_auto_add.py
```

Continuously monitors for new pools and auto-adds if they meet criteria.

**Features:**
- Runs as daemon
- Checks Curve API every hour
- Auto-adds pools meeting criteria (customizable)
- Default criteria: TVL > $5M OR 24h volume > $100k

**Customization:**
Edit the `meets_criteria()` function to change auto-add rules.

---

## Integration Patterns

### Pattern 1: Discord/Telegram Bot

```python
# bot.py
from pool_manager import PoolManager

async def on_message(message):
    if message.content.startswith("!add-pool"):
        parts = message.content.split()
        chain = parts[1]
        pool = parts[2]

        manager = PoolManager()
        success = manager.add_pool(chain, pool)

        if success:
            await message.reply(f"✅ Added pool {pool}")
        else:
            await message.reply(f"❌ Failed to add pool")
```

### Pattern 2: Cron Job Auto-Discovery

```bash
# Add to crontab
0 */6 * * * /home/danger/CurveTracker/examples/auto_discover_pools.py >> /home/danger/CurveTracker/logs/discovery.log 2>&1
```

### Pattern 3: API Integration

```python
# integration.py
import requests
from pool_manager import PoolManager

def sync_pools_from_external_api():
    """Sync pools from external tracking service"""
    response = requests.get("https://api.example.com/top-pools")
    top_pools = response.json()

    manager = PoolManager()

    for pool_data in top_pools:
        manager.add_pool(
            chain=pool_data['chain'],
            pool=pool_data['address'],
            comment=f"External: {pool_data['name']}",
            validate=True
        )

# Run daily
sync_pools_from_external_api()
```

### Pattern 4: Alert-Based Addition

```python
# alert_handler.py
from pool_manager import PoolManager

def handle_high_apy_alert(pool_address, chain, apy):
    """Called when APY monitoring system detects high APY"""
    if apy > 50:  # If APY > 50%
        manager = PoolManager()
        manager.add_pool(
            chain=chain,
            pool=pool_address,
            comment=f"High APY alert: {apy}%",
            stakedao_enabled=True,
            beefy_enabled=True
        )
        print(f"🚨 Auto-added high APY pool: {apy}%")
```

---

## Configuration File Structure

### pools.json

```json
{
  "enable_stakedao": true,
  "enable_beefy": true,
  "pools": [
    {
      "chain": "ethereum",
      "pool": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50",
      "comment": "reUSD/scrvUSD",
      "stakedao_enabled": true,
      "beefy_enabled": true
    },
    {
      "chain": "fraxtal",
      "pool": "0x15d1ed4418dA1F268bCAd5BA7c8d06BB3c3081eD",
      "comment": "frxUSD/FXB 2027",
      "gauge_address": "0x7506A3e213C362b9e21895c2Bd930DF454d46573",
      "stakedao_vault": "0xE7B60D6ABBa4E0a801ad29c9b824602aB9a0c439",
      "stakedao_enabled": true,
      "beefy_enabled": false
    }
  ]
}
```

### Backup Files

Every modification creates an automatic backup:
```
pools.json.backup_20251120_143022
```

Backups are created before:
- Adding pools
- Removing pools
- Updating pools
- Importing configs

---

## Validation

### Pool Validation

When `validate=True` (default):
- Queries Curve API to verify pool exists
- Checks pool address or name
- Prevents adding non-existent pools

Skip validation with `--no-validate` or `validate=False` when:
- Adding pools from trusted sources
- Batch adding known-good pools
- Pool is very new (not yet in API)

### Address Formats

Accepts both formats:
- Full address: `0xc522A6606BBA746d7960404F22a3DB936B6F4F50`
- Pool name: `reUSD/scrvUSD` (case-insensitive)

---

## Best Practices

### 1. Use Comments

Always add meaningful comments:
```python
manager.add_pool(
    chain="ethereum",
    pool="0xabc...",
    comment="High yield stablecoin pool - Added from alert"
)
```

### 2. Validate New Pools

Use validation for manual additions:
```python
manager.add_pool(chain, pool, validate=True)
```

Skip for bulk imports from Curve API:
```python
manager.add_pool(chain, pool, validate=False)
```

### 3. Check Before Adding

```python
if not manager.pool_exists(chain, pool):
    manager.add_pool(chain, pool)
else:
    print("Pool already tracked")
```

### 4. Use Bulk Operations

For multiple pools, use bulk_add_pools():
```python
# Better
results = manager.bulk_add_pools(pools)

# Slower
for pool in pools:
    manager.add_pool(**pool)
```

### 5. Monitor Stats

Periodically check tracking stats:
```python
stats = manager.get_stats()
if stats['total_pools'] > 100:
    print("Warning: Tracking many pools, consider cleanup")
```

---

## Troubleshooting

### Pool Already Exists

```python
# Check if exists first
if manager.pool_exists("ethereum", "0xabc..."):
    print("Pool already tracked")
    # Update instead
    manager.update_pool("ethereum", "0xabc...", comment="Updated")
else:
    manager.add_pool("ethereum", "0xabc...")
```

### Validation Fails

```python
# Try without validation
manager.add_pool(
    chain="ethereum",
    pool="0xabc...",
    validate=False  # Skip API check
)
```

### Config File Corruption

```python
# Restore from backup
import shutil
shutil.copy("pools.json.backup_20251120_143022", "pools.json")

# Or create fresh config
manager = PoolManager()
manager.export_config("pools_new.json")
```

### Import Errors

```python
# Make sure pool_manager.py is in the same directory
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pool_manager import PoolManager
```

---

## Advanced Usage

### Custom Criteria Function

```python
def should_add_pool(pool_data):
    """Custom logic for auto-adding pools"""
    tvl = pool_data.get('usdTotal', 0)
    volume = pool_data.get('totalDailyFeesUSD', 0)
    apy = pool_data.get('apy', 0)

    # Only add if:
    # - TVL > $10M
    # - APY > 5%
    # - Volume > $50k/day
    return tvl > 10_000_000 and apy > 5 and volume > 50_000
```

### Multi-Chain Monitoring

```python
chains = ["ethereum", "arbitrum", "optimism", "base"]

for chain in chains:
    pools = discover_high_tvl_pools(chain, min_tvl=5_000_000)
    manager.bulk_add_pools(pools)
```

### Conditional Integration Enablement

```python
# Enable StakeDAO only for high-TVL pools
if tvl > 50_000_000:
    manager.add_pool(
        chain=chain,
        pool=pool,
        stakedao_enabled=True,
        beefy_enabled=True
    )
else:
    manager.add_pool(
        chain=chain,
        pool=pool,
        stakedao_enabled=False,
        beefy_enabled=True
    )
```

---

## API Reference Summary

| Method | Description |
|--------|-------------|
| `add_pool()` | Add a single pool |
| `remove_pool()` | Remove a pool |
| `update_pool()` | Update pool settings |
| `pool_exists()` | Check if pool is tracked |
| `get_pool()` | Get pool configuration |
| `list_pools()` | List pools with filters |
| `bulk_add_pools()` | Add multiple pools |
| `set_global_integrations()` | Set global flags |
| `export_config()` | Export configuration |
| `import_config()` | Import configuration |
| `get_stats()` | Get statistics |
| `print_stats()` | Print formatted stats |
| `validate_pool()` | Check if pool exists via API |

---

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/Today-in-DeFi/CurveTracker/issues
- **Examples**: Check `/examples` directory
- **Logs**: Automatic backups in same directory

---

## License

Same as CurveTracker - MIT License
