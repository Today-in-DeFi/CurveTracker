# CurveTracker API Implementation Plan

> **Status as of 2026-07-21:** `curve_tracker_api.py` exists and implements a
> subset of this plan, under different method names. This document is the
> original design, not a description of the shipped module — check the source
> before relying on any signature here. The **Implementation Status** table
> below records what is actually built.
>
> Two design decisions in this plan have since been reversed. Both are marked
> inline: the `total_apy` field (removed from the export entirely) and the
> return-`None`-never-raise error policy.

## Overview

Create `curve_tracker_api.py` - a clean, importable Python API for external scripts to access CurveTracker data without needing to understand the internal architecture.

## Goals

1. Provide consistent, normalized data formats (always numeric values)
2. Support both cached (fast) and live (fresh) data access
3. Enable programmatic export control and configuration management
4. Make integration simple: one import, one class, intuitive methods

---

## API Design

### Class: `CurveDataAPI`

```python
from curve_tracker_api import CurveDataAPI

api = CurveDataAPI(
    data_dir="data/",           # Default: "data/"
    config_file="pools.json"    # Default: "pools.json"
)
```

---

## Methods Reference

### 1. Cached Data Access

Read from pre-generated JSON files. Fast, no API calls.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `get_pools` | `(chain: str = None)` | `List[PoolMetrics]` | All pools, optionally filtered by chain |
| `get_pool` | `(identifier: str, chain: str = None)` | `PoolMetrics \| None` | Single pool by address, name, or ID |
| `get_metadata` | `()` | `dict` | Export metadata (timestamp, version, chains) |
| `get_history` | `(pool_id: str = None)` | `dict` | Time-series data from history file |
| `get_data_age_minutes` | `()` | `float` | Minutes since last export |

### 2. Live Data Access

Fetch fresh data from Curve/StakeDAO/Convex/Beefy APIs.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `fetch_pool` | `(chain: str, identifier: str)` | `PoolMetrics \| None` | Fresh data for single pool |
| `fetch_all` | `()` | `List[PoolMetrics]` | Fresh data for all tracked pools |
| `fetch_pools` | `(pools: List[dict])` | `List[PoolMetrics]` | Fresh data for specific pool list |

### 3. Export Control

Trigger JSON exports programmatically.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `export_latest` | `()` | `str` | Write `curve_pools_latest.json`, return filepath |
| `export_archive` | `()` | `str` | Create `curve_pools_YYYYMMDD.json` archive |
| `append_history` | `()` | `bool` | Append snapshot to `curve_pools_history.json` |

### 4. Configuration Management

Manage tracked pools programmatically.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `list_tracked` | `()` | `List[dict]` | Current pool configurations from pools.json |
| `add_pool` | `(chain, address, **opts)` | `bool` | Add pool to tracking |
| `remove_pool` | `(chain, address)` | `bool` | Remove pool from tracking |
| `set_integration` | `(name: str, enabled: bool)` | `bool` | Toggle StakeDAO/Convex/Beefy globally. All default **on**; setting `False` suppresses a protocol we know exists |

### 5. Search & Utility

Convenience methods for common operations.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `search_pools` | `(query: str, chain: str = None)` | `List[PoolMetrics]` | Find all matching pools |
| `get_chains` | `()` | `List[str]` | List chains with tracked pools |
| `get_top_pools` | `(n: int = 5, sort_by: str = "tvl")` | `List[PoolMetrics]` | Top N pools by metric |

---

## Data Structures

### PoolMetrics (Normalized Output)

All methods return this consistent structure with raw numeric values:

```python
{
    # Identity
    "id": "ethereum_reusd_scrvusd",
    "name": "reUSD/scrvUSD",
    "chain": "ethereum",
    "address": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50",

    # Core Metrics (always present)
    "tvl": 53850000.0,
    "base_apy": 2.31,
    "crv_apy_min": 7.17,      # unboosted floor - NOT a fallback rate
    "crv_apy_max": 17.93,

    # Coin Details
    "coins": ["reUSD", "scrvUSD"],
    "coin_ratios": [0.76, 0.24],
    "coin_amounts": [40850000.0, 13000000.0],
    "coin_prices": [1.0012, 1.0045],

    # Optional Integrations (None only if the protocol has no market here)
    "stakedao_apy": 16.75,      # net of StakeDAO's 16.5% fee
    "stakedao_tvl": 2850000.0,
    "stakedao_boost": 1.32,
    "stakedao_fees": 16.5,
    "convex_apy": 18.20,        # net of Convex's 17% fee
    "convex_tvl": 3100000.0,
    "convex_pool_id": 440,
    "beefy_apy": 13.45,
    "beefy_tvl": 1250000.0,

    # Metadata
    "timestamp": "2025-12-28T10:30:00Z",
    "other_rewards": [{"token": "LDO", "apy": 1.25}]
}
```

> **There is deliberately no `total_apy`.** It existed in the export until
> 2026-07-21, hardcoded to `0` on every pool while documented as a combined
> rate, and was removed rather than populated. A pool pays a different rate
> depending on which protocol you stake through, so a single combined number is
> right for at most one of them and carries no signal about which. Read the
> per-protocol field matching where the position is actually held.
>
> For the same reason, do not substitute `crv_apy_min` when a protocol field is
> `None` — it is the unboosted Curve gauge floor, often near-half the real rate.

### Key Design Decision: Normalization

The existing JSON exports contain formatted strings like `"$53.85M"`. The API will:

1. Parse these back to raw numbers when reading cached data
2. Return consistent `PoolMetrics` format from both cached and live methods
3. Store a `_normalize_pool()` internal method for this conversion

---

## Implementation Plan

### Step 1: Core Structure

Create `curve_tracker_api.py` with:
- `CurveDataAPI` class
- Constructor with lazy-loading of CurveTracker/PoolManager
- Internal `_normalize_pool()` method

### Step 2: Cached Data Methods

Implement in order:
1. `get_metadata()` - simplest, read JSON metadata
2. `get_pools()` - read and normalize all pools
3. `get_pool()` - single pool lookup with smart matching
4. `get_data_age_minutes()` - parse timestamp, calculate age
5. `get_history()` - read history JSON file

### Step 3: Live Data Methods

Implement in order:
1. `fetch_pool()` - single pool via CurveTracker
2. `fetch_all()` - iterate tracked pools
3. `fetch_pools()` - custom pool list

### Step 4: Export Control

Implement in order:
1. `export_latest()` - wrap CurveDataExporter
2. `export_archive()` - wrap archive method
3. `append_history()` - wrap history method

### Step 5: Configuration Management

Implement in order:
1. `list_tracked()` - wrap PoolManager.list_pools()
2. `add_pool()` - wrap PoolManager.add_pool()
3. `remove_pool()` - wrap PoolManager.remove_pool()
4. `set_integration()` - modify global config flags

### Step 6: Search & Utility

Implement in order:
1. `search_pools()` - filter with partial matching
2. `get_chains()` - extract unique chains
3. `get_top_pools()` - sort and slice

### Step 7: Example Script

Create `examples/use_api.py` demonstrating:
- Basic data retrieval
- Freshness checking
- Live data fetch
- Finding best yields
- Configuration management

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `curve_tracker_api.py` | CREATE | New API module (~250-300 lines) |
| `examples/use_api.py` | CREATE | Usage examples (~80 lines) |

No changes to existing files required.

---

## Usage Examples

### Basic: Read Cached Data

```python
from curve_tracker_api import CurveDataAPI

api = CurveDataAPI()

# Get all pools
pools = api.get_pools()

# Filter by chain
eth_pools = api.get_pools(chain="ethereum")

# Get specific pool
pool = api.get_pool("0xc522A6606BBA746d7960404F22a3DB936B6F4F50")
print(f"TVL: ${pool['tvl']:,.0f}")
print(f"Convex APY: {pool['convex_apy']}%")
```

### Check Freshness & Refresh

```python
api = CurveDataAPI()

if api.get_data_age_minutes() > 60:
    print("Data stale, refreshing...")
    api.export_latest()

pools = api.get_pools()
```

### Compare Protocols on the Same Pool

Both StakeDAO and Convex APYs are net of their platform fees (16.5% and 17%
respectively), so they are directly comparable — a spread between them is real
rather than an artefact of fee treatment.

```python
api = CurveDataAPI()

for p in api.get_pools(chain="ethereum"):
    rates = {
        name: p[f"{name}_apy"]
        for name in ("convex", "stakedao", "beefy")
        if p.get(f"{name}_apy") is not None
    }
    if len(rates) < 2:
        continue  # nothing to compare against

    best, worst = max(rates, key=rates.get), min(rates, key=rates.get)
    spread = rates[best] - rates[worst]

    # Hourly snapshots drift on both sides; treat sub-1pp gaps as noise.
    if spread >= 1.0:
        print(f"{p['name']}: {best} {rates[best]}% vs {worst} {rates[worst]}%"
              f"  (+{spread:.2f}pp)")
```

A spread is a prompt to check, not a trade signal on its own — it ignores gas,
exit costs, and how much of the pool each protocol already holds.

### Live Data Fetch

```python
api = CurveDataAPI()

# Single pool, fresh data
live = api.fetch_pool("ethereum", "reUSD/scrvUSD")
print(f"Current TVL: ${live['tvl']:,.0f}")

# All pools, fresh data
all_live = api.fetch_all()
```

### Manage Configuration

```python
api = CurveDataAPI()

# Add a pool
api.add_pool(
    chain="ethereum",
    address="0x...",
    comment="Added by trading bot",
    stakedao_enabled=True
)

# Disable Beefy globally
api.set_integration("beefy", enabled=False)

# List what's tracked
for p in api.list_tracked():
    print(f"{p['chain']}: {p['pool']}")
```

---

## Implementation Status (2026-07-21)

`curve_tracker_api.py` ships a subset of this plan, under different names.

| Planned | Shipped as | Status |
|---------|-----------|--------|
| `get_pools(chain)` | `get_pools(chain)` | ✅ |
| `get_pool(identifier, chain)` | `find_pool(identifier, chain)` | ✅ renamed |
| — | `get_pool_by_id(pool_id)` | ✅ added |
| `fetch_pool(chain, identifier)` | `fetch_live_pool_data(chain, ...)` | ✅ renamed |
| `add_pool(chain, address, **opts)` | `add_pool_to_tracking(chain, pool, ...)` | ✅ renamed |
| `remove_pool(chain, address)` | `remove_pool_from_tracking(chain, pool)` | ✅ renamed |
| `list_tracked()` | `list_tracked_pools()` | ✅ renamed |
| `get_metadata()` | — | ❌ not built |
| `get_history(pool_id)` | — | ❌ not built |
| `get_data_age_minutes()` | — | ❌ not built |
| `fetch_all()` / `fetch_pools(list)` | — | ❌ not built |
| `export_latest()` / `export_archive()` / `append_history()` | — | ❌ not built |
| `set_integration(name, enabled)` | — | ❌ not built |
| `search_pools(query, chain)` | — | ❌ not built |
| `get_chains()` | — | ❌ not built |
| `get_top_pools(n, sort_by)` | — | ❌ not built |

**The normalization design was not implemented.** Shipped methods return the raw
export shape — nested `pool["latest"]["convex"]["apy"]`, with formatted strings
like `"$1.29M"` still present as `tvl_usd`. The flat `PoolMetrics` structure
above describes the intended output, not what you get today. Either build
`_normalize_pool()` or rewrite that section to match reality before treating it
as a contract.

---

## Testing Checklist

After implementation, verify:

- [ ] `get_pools()` returns normalized numeric values
- [ ] `get_pool()` finds by address, name, and ID
- [ ] `search_pools("USD")` returns multiple matches
- [ ] `get_data_age_minutes()` correctly calculates staleness
- [ ] `fetch_pool()` returns same structure as cached methods
- [ ] `export_latest()` creates valid JSON file
- [ ] `add_pool()` persists to pools.json
- [ ] External script can import and use API

---

## Notes

- **No breaking changes** to existing files
- **Lazy loading** - CurveTracker only initialized when live methods called
- **Error handling** - `None` for genuinely absent data (a protocol with no
  market for the pool). ~~Don't raise exceptions.~~ **Revised 2026-07-21:** a
  blanket no-raise policy is what let a missing protocol block read as a
  plausible rate for months. Distinguish *absent* from *failed*: return `None`
  when the data does not exist, but let a fetch failure or a malformed export
  surface rather than collapsing to `None` and looking like absence.
- **Thread safety** - Not guaranteed; intended for single-threaded use
