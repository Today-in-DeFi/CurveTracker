# StakeDAO API Integration Notes

## API Versioning and Chain Compatibility

### Overview
StakeDAO provides two API versions for Curve strategy data, with different chains supporting different versions. This document outlines the critical findings for proper integration.

### API Endpoints
- **v1**: `https://api.stakedao.org/api/strategies/curve/{chainId}.json`
- **v2**: `https://api.stakedao.org/api/strategies/v2/curve/{chainId}.json`

### Chain Support Matrix

| Chain | Chain ID | v1 API | v2 API | Notes |
|-------|----------|---------|---------|--------|
| Ethereum | 1 | ✅ Works | ✅ Works | Both versions available, v2 recommended |
| Arbitrum | 42161 | ✅ Works | ✅ Works | Both versions available, v2 recommended |
| Optimism | 10 | ⚠️ Unknown | ⚠️ Unknown | Needs testing |
| Polygon | 137 | ❌ 404 | ❌ 404 | No StakeDAO support |
| Fraxtal | 252 | ❌ 404 | ✅ Works | **Only v2 API available** |

### Critical Findings

#### 1. Fraxtal Requires v2 API
- **Issue**: Fraxtal (chain ID 252) only supports v2 API
- **Impact**: v1 API returns 404 for Fraxtal
- **Solution**: Always use v2 API for newer chains

#### 2. API Response Structure Differences

**v1 API Structure:**
```json
{
  "global": { /* global data */ },
  "deployed": [
    {
      "name": "pool-name",
      "lpToken": {
        "address": "0x..."
      },
      "apr": {
        "projected": {
          "total": 15.5
        },
        "boost": 1.25
      }
    }
  ]
}
```

**v2 API Structure:**
```json
[
  {
    "name": "pool-name",
    "lpToken": {
      "address": "0x...",
      "symbol": "token-symbol"
    },
    "apr": {
      "current": {
        "total": 21.3
      },
      "boost": 1.32
    },
    "rewards": [
      {
        "token": {
          "symbol": "WFRAX",
          "address": "0x..."
        },
        "apr": 13.11
      }
    ]
  }
]
```

#### 3. Key Structural Differences

| Aspect | v1 API | v2 API |
|--------|---------|---------|
| **Root Structure** | Object with `deployed` array | Direct array |
| **APR Field** | `apr.projected.total` | `apr.current.total` |
| **Rewards Data** | Limited | Comprehensive `rewards` array |
| **Token Info** | Basic | Enhanced with symbols |
| **Data Richness** | Basic | More comprehensive |

### Implementation Strategy

#### Current Implementation
The code uses a hybrid approach:

```python
def get_curve_strategies(self, chain_id: str = "1") -> Dict:
    """Always use v2 API for better data and newer chain support"""
    return self._make_request(f"api/strategies/v2/curve/{chain_id}.json")

def extract_apr(self, stakedao_data: dict):
    """Handle both v1 and v2 API response formats"""
    apr_data = stakedao_data.get('apr', {})

    # Try v2 structure first
    current_apr = apr_data.get('current', {})
    if current_apr and 'total' in current_apr:
        return current_apr['total']

    # Fallback to v1 structure
    projected_apr = apr_data.get('projected', {})
    if projected_apr and 'total' in projected_apr:
        return projected_apr['total']

    return None
```

#### Chain ID Mapping
```python
STAKEDAO_CHAIN_MAPPING = {
    'ethereum': '1',    # Both v1/v2 supported
    'arbitrum': '42161', # Both v1/v2 supported
    'optimism': '10',   # Needs verification
    'fraxtal': '252'    # Only v2 supported
    # 'polygon': '137'  # Not supported by StakeDAO
}
```

### Rewards Integration Nuances

#### Problem: Missing Rewards in Curve API
For newer chains like Fraxtal, Curve's gauge system doesn't capture all reward tokens (e.g., WFRAX rewards).

#### Solution: StakeDAO Fallback
```python
# If Curve gauge data doesn't have other rewards, check StakeDAO rewards
if not other_rewards and 'rewards' in stakedao_data:
    for reward in stakedao_data['rewards']:
        token_symbol = reward['token']['symbol']
        reward_apr = reward['apr']

        # Skip CRV (already shown in CRV Rewards column)
        if token_symbol.upper() != 'CRV' and reward_apr > 0:
            other_rewards.append({
                'token': token_symbol,
                'apy': reward_apr
            })
```

### Best Practices

#### 1. API Version Strategy
- **Default to v2**: Always use v2 API as primary choice
- **Maintain v1 compatibility**: Parse both response formats for backward compatibility
- **Graceful degradation**: Handle 404 responses for unsupported chains

#### 2. Error Handling
```python
try:
    response = requests.get(f"{BASE_URL}/api/strategies/v2/curve/{chain_id}.json")
    response.raise_for_status()
    return response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        # Chain not supported by StakeDAO
        return None
    raise
```

#### 3. Data Validation
- Always check if strategy data exists before parsing
- Validate APR fields exist before accessing
- Handle missing reward token information gracefully

### Testing Checklist

When adding new chain support:

1. ✅ Test v2 API endpoint: `/api/strategies/v2/curve/{chainId}.json`
2. ✅ Test v1 API endpoint: `/api/strategies/curve/{chainId}.json`
3. ✅ Verify response structure (array vs object)
4. ✅ Check APR field location (`current.total` vs `projected.total`)
5. ✅ Validate rewards array format
6. ✅ Test address matching logic
7. ✅ Confirm boost calculation accuracy

### Known Issues & Workarounds

#### Issue 1: Polygon Support
- **Problem**: StakeDAO doesn't support Polygon (both APIs return 404)
- **Workaround**: Gracefully degrade to show only Curve data

#### Issue 2: Address Matching Inconsistencies
- **Problem**: Different chains may use different field names for LP token addresses
- **Solution**: Check multiple possible field paths:
  ```python
  if 'lpToken' in strategy and isinstance(strategy['lpToken'], str):
      strategy_address = strategy['lpToken'].lower()
  elif 'lpToken' in strategy and isinstance(strategy['lpToken'], dict):
      strategy_address = strategy['lpToken'].get('address', '').lower()
  ```

#### Issue 3: Reward Token Symbols
- **Problem**: Some reward tokens may have inconsistent symbol formats
- **Solution**: Normalize symbols and handle edge cases

### Migration Notes

If migrating from v1 to v2 API:

1. **Update endpoint URLs** from `/strategies/curve/` to `/strategies/v2/curve/`
2. **Change response parsing** from `data['deployed']` to direct array access
3. **Update APR extraction** from `apr.projected.total` to `apr.current.total`
4. **Add rewards parsing** to leverage enhanced rewards data in v2
5. **Test all supported chains** to ensure compatibility

### Future Considerations

1. **New Chain Support**: When StakeDAO adds new chains, they'll likely use v2 API only
2. **v1 API Deprecation**: Consider v1 API may be deprecated in the future
3. **Enhanced Data**: v2 API provides richer data for better user experience
4. **Performance**: v2 API may have different rate limits or response times

---

*Last Updated: 2024-09-14*
*Documented during FXB 2027 pool integration and StakeDAO v2 API migration*