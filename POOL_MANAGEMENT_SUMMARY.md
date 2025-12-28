# Pool Management System - Quick Start

Complete system for programmatic pool management in CurveTracker.

## 🎯 What You Can Do

1. **CLI Commands** - Quick pool management from terminal
2. **Python Module** - Import and use in your scripts
3. **Webhook Server** - HTTP API for remote integrations
4. **Auto-Discovery** - Automatically find and add pools
5. **Monitoring** - Continuous monitoring and auto-addition

---

## 🚀 Quick Examples

### CLI: Add a Pool

```bash
# Basic
python3 curve_tracker.py --add-pool ethereum 0xabc123...

# With all options
python3 curve_tracker.py --add-pool ethereum 0xabc123... \
  --comment "High APY pool" \
  --stakedao \
  --beefy
```

### CLI: List Pools

```bash
python3 curve_tracker.py --list-pools
python3 curve_tracker.py --pool-stats
```

### Python: Add Pools

```python
from pool_manager import PoolManager

manager = PoolManager()

# Add single pool
manager.add_pool(
    chain="ethereum",
    pool="0xabc...",
    comment="My pool",
    stakedao_enabled=True
)

# Bulk add
pools = [
    {"chain": "ethereum", "pool": "0xabc...", "comment": "Pool 1"},
    {"chain": "ethereum", "pool": "0xdef...", "comment": "Pool 2"}
]
results = manager.bulk_add_pools(pools)
```

### Python: Auto-Discovery

```bash
# Run the auto-discovery script
python3 examples/auto_discover_pools.py

# Or customize it:
from pool_manager import PoolManager
import requests

def discover_high_tvl_pools(min_tvl=10_000_000):
    # Fetch from Curve API
    url = "https://api.curve.finance/v1/getPools/all/ethereum"
    data = requests.get(url).json()

    # Filter and add
    manager = PoolManager()
    for pool in data['data']['poolData']:
        if pool['usdTotal'] > min_tvl:
            manager.add_pool(
                chain="ethereum",
                pool=pool['address'],
                comment=f"{pool['name']} - ${pool['usdTotal']:,.0f}"
            )
```

### Webhook Server

```bash
# Start server
python3 examples/webhook_listener.py

# In another terminal, add pool via HTTP
curl -X POST http://localhost:8080/add-pool \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum",
    "pool": "0xabc...",
    "comment": "Remote pool",
    "stakedao_enabled": true
  }'
```

---

## 📁 Files Created

### Core Module
- **`pool_manager.py`** - Main pool management class with all functions

### Example Scripts
- **`examples/add_single_pool.py`** - Add one pool
- **`examples/bulk_add_pools.py`** - Add multiple pools
- **`examples/auto_discover_pools.py`** - Find high-TVL pools
- **`examples/webhook_listener.py`** - HTTP server for remote management
- **`examples/monitor_and_auto_add.py`** - Continuous monitoring daemon

### Documentation
- **`POOL_MANAGEMENT.md`** - Complete guide with all API details

---

## 🔥 Common Use Cases

### 1. Discord/Telegram Bot

```python
# When user sends: !add-pool ethereum 0xabc...
from pool_manager import PoolManager

manager = PoolManager()
success = manager.add_pool("ethereum", "0xabc...")

if success:
    await message.reply("✅ Pool added!")
```

### 2. Automated Monitoring (Cron)

```bash
# Add to crontab - check every 6 hours
0 */6 * * * /home/danger/CurveTracker/examples/auto_discover_pools.py

# Or continuous monitoring
nohup python3 examples/monitor_and_auto_add.py &
```

### 3. Alert-Based Addition

```python
# When APY alert triggers
from pool_manager import PoolManager

def on_high_apy_alert(pool_address, chain, apy):
    if apy > 50:  # High APY detected
        manager = PoolManager()
        manager.add_pool(
            chain=chain,
            pool=pool_address,
            comment=f"High APY alert: {apy}%",
            stakedao_enabled=True,
            beefy_enabled=True
        )
```

### 4. External API Sync

```python
# Sync from external data source
import requests
from pool_manager import PoolManager

response = requests.get("https://api.example.com/top-pools")
external_pools = response.json()

manager = PoolManager()
for pool in external_pools:
    manager.add_pool(
        chain=pool['chain'],
        pool=pool['address'],
        comment=f"External: {pool['name']}"
    )
```

---

## 🛠️ Python API Reference

### Most Used Methods

```python
from pool_manager import PoolManager

manager = PoolManager()

# Add pool
manager.add_pool(chain, pool, comment="...", stakedao_enabled=True)

# Remove pool
manager.remove_pool(chain, pool)

# Check if exists
if manager.pool_exists(chain, pool):
    print("Already tracked")

# List pools
all_pools = manager.list_pools()
eth_pools = manager.list_pools(chain="ethereum")
stakedao_pools = manager.list_pools(stakedao_only=True)

# Get pool config
config = manager.get_pool(chain, pool)

# Update pool
manager.update_pool(chain, pool, comment="New comment")

# Bulk operations
manager.bulk_add_pools([{...}, {...}])

# Stats
stats = manager.get_stats()
manager.print_stats()

# Import/Export
manager.export_config("backup.json")
manager.import_config("backup.json", merge=True)
```

---

## 🎨 Customization Examples

### Custom Discovery Criteria

Edit `examples/auto_discover_pools.py`:

```python
def meets_criteria(pool_data: dict) -> bool:
    """Customize your auto-add criteria here"""
    tvl = pool_data.get('usdTotal', 0)
    volume = pool_data.get('totalDailyFeesUSD', 0)
    apy = pool_data.get('apy', 0)

    # Your custom logic
    return (
        tvl > 10_000_000 and      # TVL > $10M
        apy > 10 and              # APY > 10%
        volume > 100_000          # Volume > $100k/day
    )
```

### Conditional Integration

```python
# Enable StakeDAO only for pools > $50M TVL
if pool_tvl > 50_000_000:
    manager.add_pool(chain, pool, stakedao_enabled=True, beefy_enabled=True)
else:
    manager.add_pool(chain, pool, stakedao_enabled=False, beefy_enabled=True)
```

---

## 💡 Pro Tips

### 1. Always Use Comments

```python
# Good - you'll remember what this is
manager.add_pool(
    chain="ethereum",
    pool="0xabc...",
    comment="High APY stable pool from Discord alert"
)

# Bad - you'll forget
manager.add_pool("ethereum", "0xabc...")
```

### 2. Check Before Adding

```python
if not manager.pool_exists(chain, pool):
    manager.add_pool(chain, pool)
```

### 3. Use Validation Wisely

```python
# From Curve API? Skip validation (faster)
manager.add_pool(chain, pool, validate=False)

# Manual entry? Validate it
manager.add_pool(chain, pool, validate=True)
```

### 4. Bulk > Loop

```python
# Better - single transaction
results = manager.bulk_add_pools(pools)

# Slower - multiple transactions
for pool in pools:
    manager.add_pool(**pool)
```

### 5. Monitor Stats

```python
stats = manager.get_stats()
if stats['total_pools'] > 100:
    print("⚠️ Tracking many pools - consider cleanup")
```

---

## 🔒 Safety Features

### Automatic Backups

Every change creates a backup:
```
pools.json.backup_20251120_143022
```

Backups created before:
- Adding pools
- Removing pools
- Updating pools
- Importing configs

### Validation

Optional validation via Curve API:
```python
# Validates pool exists before adding
manager.add_pool(chain, pool, validate=True)

# Skips validation (faster, for trusted sources)
manager.add_pool(chain, pool, validate=False)
```

### Duplicate Prevention

```python
# Won't add if already exists
manager.add_pool(chain, pool)  # Returns False if exists
```

---

## 📊 Statistics

```python
stats = manager.get_stats()

# Returns:
{
    'total_pools': 7,
    'chains': ['ethereum', 'fraxtal'],
    'chain_counts': {'ethereum': 6, 'fraxtal': 1},
    'stakedao_enabled_count': 6,
    'beefy_enabled_count': 4,
    'global_stakedao': True,
    'global_beefy': True
}
```

---

## 🚦 Testing

```bash
# Test CLI
python3 curve_tracker.py --list-pools
python3 curve_tracker.py --pool-stats

# Test adding (won't duplicate if exists)
python3 curve_tracker.py --add-pool ethereum 0xtest123 \
  --comment "Test pool" \
  --no-validate

# Test removing
python3 curve_tracker.py --remove-pool ethereum 0xtest123

# Test examples
python3 examples/add_single_pool.py
python3 examples/bulk_add_pools.py
python3 examples/auto_discover_pools.py
```

---

## 📚 Full Documentation

See **`POOL_MANAGEMENT.md`** for complete API reference, all examples, and advanced usage.

---

## 🆘 Troubleshooting

### Pool Already Exists

```python
if manager.pool_exists(chain, pool):
    manager.update_pool(chain, pool, comment="Updated")
else:
    manager.add_pool(chain, pool)
```

### Import Error

```python
# Add parent directory to path
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pool_manager import PoolManager
```

### Restore from Backup

```bash
# List backups
ls -lh pools.json.backup_*

# Restore
cp pools.json.backup_20251120_143022 pools.json
```

---

## ⚡ Quick Reference

| Task | CLI Command | Python Code |
|------|-------------|-------------|
| Add pool | `--add-pool ethereum 0xabc...` | `manager.add_pool("ethereum", "0xabc...")` |
| Remove pool | `--remove-pool ethereum 0xabc...` | `manager.remove_pool("ethereum", "0xabc...")` |
| List pools | `--list-pools` | `manager.list_pools()` |
| Show stats | `--pool-stats` | `manager.print_stats()` |
| Check exists | - | `manager.pool_exists("ethereum", "0xabc...")` |
| Bulk add | - | `manager.bulk_add_pools([...])` |

---

Ready to use! Check `POOL_MANAGEMENT.md` for full details.
