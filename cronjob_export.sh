#!/bin/bash
#
# CurveTracker Automated Export Cron Job
# Runs hourly to update Google Sheets, JSON files, and Google Drive
#
# What this does:
# - Fetches pool data from Curve, StakeDAO, and Beefy APIs
# - Updates Google Sheets (category sheets + Log sheet with 30-day history)
# - Exports JSON files (latest + cumulative history)
# - Creates daily archive (once per day)
# - Uploads all files to Google Drive
# - Cleans up old data (>30 days from Sheets and Drive)
#
# Setup:
# 1. Make executable: chmod +x cronjob_export.sh
# 2. Add to crontab: crontab -e
# 3. Add line: 0 * * * * /home/danger/CurveTracker/cronjob_export.sh
#

# Configuration
SCRIPT_DIR="/home/danger/CurveTracker"
PYTHON_BIN="python3"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/export_$(date +\%Y\%m\%d).log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Start execution
log "========================================="
log "Starting CurveTracker JSON export"
log "========================================="

# Change to script directory
cd "$SCRIPT_DIR" || {
    log "ERROR: Could not change to directory: $SCRIPT_DIR"
    exit 1
}

# Run the tracker with JSON export
log "Running curve_tracker.py with JSON export..."

$PYTHON_BIN curve_tracker.py \
    --pools pools.json \
    --export-json \
    --archive \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Export completed successfully"
else
    log "❌ Export failed with exit code: $EXIT_CODE"
fi

# Keep only last 7 days of logs
log "Cleaning up old logs..."
find "$LOG_DIR" -name "export_*.log" -type f -mtime +7 -delete

log "========================================="
log "Finished"
log "========================================="

exit $EXIT_CODE
