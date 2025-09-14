#!/bin/bash

# Curve Tracker - Cron Job Wrapper
# This script runs the curve tracker every morning at 9:10 AM

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Log file for cron output
LOG_FILE="$SCRIPT_DIR/logs/cron_curve_tracker.log"
ERROR_LOG="$SCRIPT_DIR/logs/cron_curve_tracker_error.log"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to log errors
log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: $1" | tee -a "$ERROR_LOG"
}

# Start execution
log_message "Starting Curve Tracker cron job"

# Change to project directory
cd "$SCRIPT_DIR" || {
    log_error "Failed to change to project directory: $SCRIPT_DIR"
    exit 1
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is not installed or not in PATH"
    exit 1
fi

# Check if required files exist
if [ ! -f "curve_tracker.py" ]; then
    log_error "Main script not found: curve_tracker.py"
    exit 1
fi

if [ ! -f "Google Credentials.json" ]; then
    log_error "Google credentials not found: Google Credentials.json"
    exit 1
fi

# Install/update dependencies if needed
log_message "Checking Python dependencies..."
python3 -m pip install -r requirements.txt >> "$LOG_FILE" 2>&1

# Run the curve tracker
log_message "Executing curve tracker..."
python3 curve_tracker.py >> "$LOG_FILE" 2>&1

# Check exit status
if [ $? -eq 0 ]; then
    log_message "Curve Tracker completed successfully"
else
    log_error "Curve Tracker failed with exit code $?"
    exit 1
fi

log_message "Cron job completed"