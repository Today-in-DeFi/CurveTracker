# Curve Tracker Architecture

## Overview

The Curve Tracker is a modular Python application that aggregates yield farming data from multiple DeFi protocols. It follows a plugin-based architecture where external data sources (StakeDAO, Beefy Finance) can be integrated independently without affecting the core Curve functionality.

## High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  JSON Config     │    │ Google Sheets   │
│                 │    │  Parser          │    │ Export          │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    CurveTracker          │
                    │    (Main Controller)     │
                    └────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼────────┐    ┌─────────▼──────────┐    ┌────────▼────────┐
│  Curve API     │    │  StakeDAO API      │    │  Beefy API      │
│  Integration   │    │  Integration       │    │  Integration    │
└────────────────┘    └────────────────────┘    └─────────────────┘
```

## Core Components

### 1. Data Models (`PoolData` Dataclass)

```python
@dataclass
class PoolData:
    # Core Curve data (always present)
    name: str
    chain: str
    coins: str
    coin_ratios: str
    tvl: str
    base_apy: float
    crv_rewards: str
    other_rewards: str

    # Optional StakeDAO integration
    stakedao_apy: Optional[float] = None
    stakedao_tvl: Optional[float] = None
    stakedao_boost: Optional[float] = None

    # Optional Beefy integration
    beefy_apy: Optional[float] = None
    beefy_tvl: Optional[float] = None
    beefy_vault_id: Optional[str] = None
```

**Design Principles:**
- **Optional Fields**: Integration data is optional, allowing graceful degradation
- **Type Safety**: All fields are properly typed with Optional for integrations
- **Extensibility**: New integrations can be added without breaking existing code

### 2. API Integration Classes

#### CurveAPI (Core)
- **Purpose**: Primary data source for pool information, APYs, and gauge rewards
- **Endpoints**:
  - `/v1/getPools/all/{chain}` - Pool metadata and TVL
  - `/v1/getBaseApys/{chain}` - Trading fee APYs
  - `/v1/getAllGauges` - CRV reward information
- **Chain Support**: 15+ chains including Ethereum, Fraxtal, Polygon, Arbitrum

#### StakeDAOAPI (Optional Plugin)
```python
class StakeDAOAPI:
    def __init__(self):
        self.base_url = "https://api.stakedao.org"
        self.chain_mapping = {
            'ethereum': 1,
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10
        }

    def get_strategy_data(self, chain: str) -> Dict:
        # Fetch all strategies for a chain

    def find_pool_strategy(self, pool_address: str, chain: str) -> Optional[Dict]:
        # Match by LP token address, select highest TVL if multiple matches
```

**Key Features:**
- **Address Matching**: Uses LP token addresses for precise pool matching
- **Multi-Strategy Handling**: Selects highest TVL strategy when multiple matches exist
- **Chain ID Mapping**: Converts chain names to StakeDAO's numeric chain IDs
- **Projected APR**: Uses `apr.projected.total` which includes CRV boost calculations

#### BeefyAPI (Optional Plugin)
```python
class BeefyAPI:
    def __init__(self):
        self.vaults_url = "https://api.beefy.finance/vaults"
        self.apy_url = "https://api.beefy.finance/apy"

    def get_vault_data(self, pool_address: str, chain: str) -> Optional[Dict]:
        # Match by want token (LP token address) or vault ID

    def normalize_apy(self, apy_value: float) -> float:
        # Handle both percentage and decimal formats
```

**Key Features:**
- **Multi-Chain Support**: 20+ chains including Fraxtal, Ethereum, Polygon
- **Dual Matching**: Matches by LP token address or vault ID
- **APY Normalization**: Handles both decimal (0.169) and percentage (16.9) formats
- **Vault Metadata**: Includes vault strategy and risk information

### 3. Main Controller (`CurveTracker`)

```python
class CurveTracker:
    def __init__(self, enable_stakedao: bool = False, enable_beefy: bool = False):
        self.enable_stakedao = enable_stakedao
        self.enable_beefy = enable_beefy

        # Initialize APIs based on flags
        self.stakedao_api = StakeDAOAPI() if enable_stakedao else None
        self.beefy_api = BeefyAPI() if enable_beefy else None
```

**Responsibilities:**
- **Configuration Management**: Handles CLI flags and JSON config parsing
- **Data Orchestration**: Coordinates data fetching from multiple APIs
- **Integration Logic**: Merges data from different sources into unified PoolData objects
- **Output Generation**: Formats data for display and export

## Data Flow

### 1. Configuration Loading
```
CLI Args → JSON Config → Default Values
     ↓
Configuration merged with priority: CLI > JSON > Defaults
```

### 2. Pool Data Fetching
```
Input: Pool address/name + Chain
     ↓
1. Fetch core Curve data (required)
     ↓
2. If StakeDAO enabled: Fetch strategy data (optional)
     ↓
3. If Beefy enabled: Fetch vault data (optional)
     ↓
4. Merge all data into PoolData object
     ↓
Output: Complete PoolData with all available integrations
```

### 3. Address Matching Algorithm

```python
def match_pool_by_address(api_data: List[Dict], target_address: str) -> Optional[Dict]:
    """
    1. Normalize addresses (lowercase, remove 0x prefix inconsistencies)
    2. Look for exact matches in relevant address fields:
       - StakeDAO: token.address, underlying_assets
       - Beefy: tokenAddress (want token)
    3. If multiple matches, select by highest TVL
    4. Return best match or None
    """
```

## Integration Patterns

### Plugin Architecture
Each external integration follows the same pattern:

1. **Optional Initialization**: Only created if enabled via config
2. **Graceful Fallback**: Returns None/empty data if API unavailable
3. **Address-Based Matching**: Uses LP token addresses for precision
4. **Data Normalization**: Converts API responses to standard format

### Configuration System
```json
{
  "enable_stakedao": false,  // Global toggle
  "enable_beefy": false,     // Global toggle
  "pools": [
    {
      "chain": "ethereum",
      "pool": "0x...",
      "beefy_vault_id": "curve-pool-name",  // Pool-specific override
      "stakedao_vault": "0x...",            // Manual vault specification
    }
  ]
}
```

**Configuration Priority:**
1. CLI flags (highest)
2. JSON file settings
3. Default values (lowest)

## Display System

### Dynamic Column Detection
```python
def get_columns_to_display(pool_data_list: List[PoolData]) -> List[str]:
    """
    Scan all pool data to determine which integration columns have data.
    Only show StakeDAO columns if any pool has StakeDAO data.
    Only show Beefy columns if any pool has Beefy data.
    """
```

### Output Formats
- **CLI Table**: Dynamic tabulate-based table with only relevant columns
- **Google Sheets**: Separate sheets for ETH-denominated and USD-denominated pools
- **CSV Export**: All columns with N/A for missing data

## Chain Support Strategy

### Curve Finance (Core)
- **Full Support**: All chains supported by Curve API
- **Fallback**: Manual pool data for unsupported pools

### StakeDAO Integration
- **Supported Chains**: Ethereum (1), Polygon (137), Arbitrum (42161), Optimism (10)
- **Chain ID Mapping**: Required for API compatibility
- **Unsupported Chains**: Integration disabled, shows N/A

### Beefy Finance Integration
- **Multi-Chain**: 20+ chains with automatic detection
- **Chain Name Matching**: Uses Beefy's chain naming convention
- **Broad Coverage**: Covers most major L1s and L2s

## Error Handling Strategy

### API Failures
```python
try:
    api_data = fetch_external_api()
except Exception as e:
    logger.warning(f"External API failed: {e}")
    return None  # Graceful degradation
```

### Data Validation
- **Required Fields**: Core Curve data must be present
- **Optional Fields**: Integration data can be missing
- **Type Checking**: All fields validated before creating PoolData

### User Communication
- **Verbose Logging**: Debug information for troubleshooting
- **Clear Error Messages**: User-friendly error descriptions
- **Fallback Display**: "N/A" for missing integration data

## Extensibility Design

### Adding New Integrations
1. Create new API class following the pattern:
   ```python
   class NewProtocolAPI:
       def get_pool_data(self, address: str, chain: str) -> Optional[Dict]:
           # Implementation
   ```

2. Add optional fields to PoolData:
   ```python
   @dataclass
   class PoolData:
       # existing fields...
       newprotocol_apy: Optional[float] = None
   ```

3. Update CurveTracker initialization and data fetching

4. Add CLI flag and JSON configuration support

### Chain Support Expansion
- Add chain ID mappings for new protocols
- Update chain validation logic
- Test API compatibility for new chains

## Performance Considerations

### API Rate Limiting
- **Batched Requests**: Group multiple pools per API call when possible
- **Caching**: In-memory caching during single execution (no persistent cache)
- **Error Recovery**: Retry logic for transient failures

### Data Processing
- **Lazy Loading**: Integration APIs only called when enabled
- **Parallel Processing**: Could be added for multiple pool queries
- **Memory Efficiency**: Stream processing for large pool lists

## Security Considerations

### API Security
- **HTTPS Only**: All external API calls use HTTPS
- **No API Keys**: All APIs are public, no authentication required
- **Input Validation**: Pool addresses validated before API calls

### Google Sheets Integration
- **Service Account**: Uses service account credentials, not user OAuth
- **Credential Management**: Supports custom credential file paths
- **Permission Control**: User manages spreadsheet permissions

## Testing Strategy

### API Testing
- **Live API Tests**: Validate against real API endpoints
- **Mock Testing**: Unit tests with mocked API responses
- **Chain Compatibility**: Test each integration against supported chains

### Integration Testing
- **End-to-End**: Full pipeline from CLI to output
- **Configuration Testing**: All configuration combinations
- **Error Scenarios**: Network failures, invalid addresses, API downtime

## Monitoring and Debugging

### Logging Strategy
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API calls
logger.info(f"Fetching data for {pool_address} on {chain}")

# Integration failures
logger.warning(f"StakeDAO API unavailable for {chain}")

# Data processing
logger.debug(f"Matched {len(matches)} strategies for pool")
```

### Debug Information
- **API Response Logging**: Optional verbose mode for API debugging
- **Address Matching Details**: Show which addresses matched/failed
- **Configuration Validation**: Display effective configuration after merging

This architecture ensures the system is modular, extensible, and maintainable while providing reliable data aggregation across multiple DeFi protocols.