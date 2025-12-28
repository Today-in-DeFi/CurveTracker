# CurveTracker JSON API Setup Guide

Complete setup guide for the CurveTracker JSON API with Google Drive integration.

## What Was Created

### 1. **json_exporter.py** - JSON Data Exporter
- Exports pool data to structured JSON format
- Handles all integration data (Curve, StakeDAO, Beefy)
- Creates daily archives with timestamps
- Formats TVL, APYs, and coin ratios

### 2. **drive_uploader.py** - Google Drive Integration
- Uploads JSON files to Google Drive
- Sets public read permissions automatically
- Updates existing files (no duplicates)
- Cleans up archives older than 30 days
- Returns public download URLs

### 3. **curve_tracker.py** - Updated with Export Flags
New command-line arguments:
- `--export-json` - Export and upload to Drive
- `--json-only` - Export locally (no Drive upload)
- `--archive` - Create dated archive file
- `--drive-folder-id` - Specify Drive folder

### 4. **cronjob_export.sh** - Automated Hourly Updates
- Bash script for cron automation
- Logs to dated files
- Cleans up old logs (7 days)
- Error handling and exit codes

### 5. **DATA_ACCESS.md** - Complete Documentation
- JSON schema documentation
- Usage examples (Python, JavaScript, Bash, Excel)
- Field descriptions
- API integration guide

---

## Quick Start

### 1. Test JSON Export Locally
```bash
# Export to local JSON file (no Drive upload)
python3 curve_tracker.py --pools pools.json --json-only

# Check the output
cat data/curve_pools_latest.json | jq '.metadata'
```

### 2. Upload to Google Drive
```bash
# Export and upload to Drive
python3 curve_tracker.py --pools pools.json --export-json

# With archive
python3 curve_tracker.py --pools pools.json --export-json --archive
```

### 3. Set Up Cron Job (Hourly Updates)
```bash
# Make script executable
chmod +x cronjob_export.sh

# Edit crontab
crontab -e

# Add this line for hourly updates (at the top of each hour)
0 * * * * /home/danger/CurveTracker/cronjob_export.sh
```

---

## Google Drive Setup

### Step 1: Get Your File ID

After first upload, you'll see:
```
✅ JSON data uploaded successfully!
🔗 Public URL: https://drive.google.com/uc?export=download&id=FILE_ID_HERE
📋 File ID: FILE_ID_HERE
```

### Step 2: Update DATA_ACCESS.md

Replace `YOUR_FILE_ID_HERE` with your actual file ID:

```bash
# Edit DATA_ACCESS.md
nano DATA_ACCESS.md

# Replace all instances of YOUR_FILE_ID_HERE with your actual file ID
```

### Step 3: Create a Drive Folder (Optional)

1. Go to drive.google.com
2. Create a folder named "CurveTracker API"
3. Get the folder ID from the URL
4. Use it with `--drive-folder-id` flag

```bash
python3 curve_tracker.py --pools pools.json --export-json --drive-folder-id "YOUR_FOLDER_ID"
```

---

## Command Reference

### Export Commands

```bash
# Local export only (testing)
python3 curve_tracker.py --pools pools.json --json-only

# Export and upload to Drive
python3 curve_tracker.py --pools pools.json --export-json

# Include daily archive
python3 curve_tracker.py --pools pools.json --export-json --archive

# Use custom credentials
python3 curve_tracker.py --pools pools.json --export-json --credentials "path/to/creds.json"

# Specify Drive folder
python3 curve_tracker.py --pools pools.json --export-json --drive-folder-id "1abc123xyz"
```

### Single Pool Export
```bash
# Query and export single pool
python3 curve_tracker.py -c ethereum -p "reUSD/scrvUSD" --export-json
```

### With Integrations
```bash
# Export with all integrations
python3 curve_tracker.py --pools pools.json --stakedao --beefy --export-json
```

---

## JSON Output Structure

### Metadata
```json
{
  "version": "1.0",
  "metadata": {
    "generated_at": "2025-11-20T16:30:00Z",
    "source": "CurveTracker v1.0",
    "total_pools": 7,
    "chains": ["ethereum", "fraxtal"],
    "data_freshness_hours": 1,
    "integrations": ["Curve", "StakeDAO", "Beefy"]
  },
  "pools": [ /* array of pool objects */ ]
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
    "tvl_usd": "$22.91M",
    "tvl_raw": 22913765.98,
    "base_apy": 1.68,
    "crv_rewards": {
      "min": 6.07,
      "max": 15.18,
      "range_text": "6.07 - 15.18"
    },
    "other_rewards": null,
    "stakedao": {
      "apy": 14.06,
      "tvl": 6642047.16,
      "boost": 2.37,
      "fees": null
    },
    "beefy": {
      "apy": 13.56,
      "tvl": 2153577.23,
      "vault_id": "curve-eth-reusd-scrvusd"
    },
    "coin_details": [
      {
        "name": "reUSD",
        "amount": 17520886.10,
        "price": 0.9899
      },
      {
        "name": "scrvUSD",
        "amount": 5166534.07,
        "price": 1.078
      }
    ]
  },
  "metadata": {
    "pool_address": "0xc522A6606BBA746d7960404F22a3DB936B6F4F50"
  }
}
```

---

## Cron Job Details

### What It Does
1. Changes to CurveTracker directory
2. Runs curve_tracker.py with JSON export
3. Uploads to Google Drive
4. Creates daily archive
5. Cleans up old archives (30 days)
6. Logs everything to dated log files
7. Cleans up old logs (7 days)

### Log Location
```bash
# View today's log
cat logs/export_$(date +%Y%m%d).log

# View recent logs
ls -lh logs/

# Tail live updates
tail -f logs/export_$(date +%Y%m%d).log
```

### Cron Schedule Options
```bash
# Every hour (at :00)
0 * * * * /home/danger/CurveTracker/cronjob_export.sh

# Every 30 minutes
*/30 * * * * /home/danger/CurveTracker/cronjob_export.sh

# Every 6 hours
0 */6 * * * /home/danger/CurveTracker/cronjob_export.sh

# Daily at 2 AM
0 2 * * * /home/danger/CurveTracker/cronjob_export.sh
```

---

## Troubleshooting

### Issue: Upload Fails with 403 Error
**Solution**: Check credentials file permissions
```bash
ls -l "Google Credentials.json"
# Should be readable: -rw-r--r--
```

### Issue: File Not Public
**Solution**: Check Drive permissions
```python
python3 -c "
from drive_uploader import DriveUploader
uploader = DriveUploader()
result = uploader.upload_json('data/curve_pools_latest.json', 'curve_pools_latest.json')
print(result)
"
```

### Issue: Cron Job Not Running
**Solution**: Check cron logs
```bash
# Check if cron is running
systemctl status cron

# View cron logs
grep CRON /var/log/syslog | tail -20

# Check your crontab
crontab -l
```

### Issue: JSON Export Fails
**Solution**: Check for data issues
```bash
# Test with debug output
python3 curve_tracker.py --pools pools.json --json-only 2>&1 | tee test.log

# Check the log
less test.log
```

---

## Next Steps

1. **Test the Export**
   ```bash
   python3 curve_tracker.py --pools pools.json --export-json
   ```

2. **Save Your File ID**
   - Copy the file ID from the output
   - Update DATA_ACCESS.md with your file ID

3. **Set Up Cron Job**
   ```bash
   crontab -e
   # Add: 0 * * * * /home/danger/CurveTracker/cronjob_export.sh
   ```

4. **Test Cron Manually**
   ```bash
   ./cronjob_export.sh
   # Check logs/export_*.log
   ```

5. **Share the API**
   - Update README.md with public URL
   - Share DATA_ACCESS.md with users
   - Announce on Twitter/Discord/etc.

---

## Advanced Usage

### Custom Drive Folder Structure
```bash
# Create folders in Drive:
# - CurveTracker/
#   - latest/
#   - archives/

# Upload to specific folder
python3 curve_tracker.py --pools pools.json --export-json --drive-folder-id "LATEST_FOLDER_ID"
```

### Multiple Output Files
```bash
# Export different configs to different files
python3 curve_tracker.py --pools ethereum_pools.json --json-only
mv data/curve_pools_latest.json data/curve_ethereum.json

python3 curve_tracker.py --pools fraxtal_pools.json --json-only
mv data/curve_pools_latest.json data/curve_fraxtal.json

# Upload both
python3 -c "
from drive_uploader import DriveUploader
uploader = DriveUploader()
uploader.upload_json('data/curve_ethereum.json', 'curve_ethereum.json')
uploader.upload_json('data/curve_fraxtal.json', 'curve_fraxtal.json')
"
```

### Historical Data Tracking
```bash
# Keep all daily archives
python3 curve_tracker.py --pools pools.json --export-json --archive

# Archives are automatically cleaned up after 30 days
# To change retention period, edit drive_uploader.py:
# uploader.cleanup_old_archives(days_to_keep=60)  # Keep 60 days
```

---

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/Today-in-DeFi/CurveTracker/issues
- **Logs**: Check `logs/export_*.log`
- **Test Locally**: Use `--json-only` flag

---

## License

Same as CurveTracker - MIT License

---

## Changelog

### 2025-11-20 - Initial Release
- JSON export functionality
- Google Drive integration
- Hourly cron automation
- Comprehensive documentation
- Support for Curve, StakeDAO, and Beefy data
