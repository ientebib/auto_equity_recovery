#!/bin/bash
# Script to set up a cron job to run the lead recovery pipeline every 10 minutes during business hours

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_SCRIPT="$PROJECT_DIR/automate_pipeline.py"
LOG_FILE="$PROJECT_DIR/cron_lead_recovery.log"

# Check if the automation script exists and is executable
if [ ! -f "$AUTOMATION_SCRIPT" ]; then
    echo "Error: Automation script not found at $AUTOMATION_SCRIPT"
    exit 1
fi

if [ ! -x "$AUTOMATION_SCRIPT" ]; then
    echo "Making automation script executable..."
    chmod +x "$AUTOMATION_SCRIPT"
fi

echo "Checking for existing cron jobs..."
# Create a temporary crontab file
TEMP_CRONTAB=$(mktemp)
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || true

# List any existing lead recovery-related jobs
if grep -q "lead[-_]recovery\|$PROJECT_DIR" "$TEMP_CRONTAB"; then
    echo "Found existing lead recovery related cron jobs:"
    grep -E "lead[-_]recovery|$PROJECT_DIR" "$TEMP_CRONTAB" | sed 's/^/  /'
    
    echo "Removing all existing lead recovery cron jobs..."
    grep -v -E "lead[-_]recovery|$PROJECT_DIR" "$TEMP_CRONTAB" > "${TEMP_CRONTAB}.new"
    mv "${TEMP_CRONTAB}.new" "$TEMP_CRONTAB"
    echo "Successfully cleared existing jobs."
else
    echo "No existing lead recovery cron jobs found."
fi

# Add the new cron job to run every 10 minutes from 10:30am to 6:30pm Mexico City time (weekdays only)
echo "# Lead Recovery Pipeline - runs every 10 minutes from 10:30am to 6:30pm Mexico City time (Mon-Fri)" >> "$TEMP_CRONTAB"

# Get the path to the Python interpreter in the virtual environment
PYTHON_PATH="$PROJECT_DIR/fresh_env/bin/python"
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Warning: Python not found at $PYTHON_PATH, will use system Python"
    PYTHON_PATH="python"
fi

# Use more efficient */10 format, but only for the hours we want (10:30 through 18:30)
# Start at 10:30
echo "30 10 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH $AUTOMATION_SCRIPT >> $LOG_FILE 2>&1" >> "$TEMP_CRONTAB"
# 10:40 and 10:50
echo "40,50 10 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH $AUTOMATION_SCRIPT >> $LOG_FILE 2>&1" >> "$TEMP_CRONTAB"
# Every 10 minutes from 11am to 6:20pm
echo "*/10 11-18 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH $AUTOMATION_SCRIPT >> $LOG_FILE 2>&1" >> "$TEMP_CRONTAB"
# Final run at 6:30pm
echo "30 18 * * 1-5 cd $PROJECT_DIR && $PYTHON_PATH $AUTOMATION_SCRIPT >> $LOG_FILE 2>&1" >> "$TEMP_CRONTAB"

# Install the new crontab
crontab "$TEMP_CRONTAB"
echo "✅ Cron job installed to run every 10 minutes from 10:30am to 6:30pm Mexico City time, Monday to Friday"

# Clean up
rm "$TEMP_CRONTAB"

echo ""
echo "Done! The lead recovery pipeline will run on this schedule:"
echo "- Starting at 10:30am"
echo "- Every 10 minutes"
echo "- Until 6:30pm" 
echo "- Monday through Friday"
echo ""
echo "Log file: $LOG_FILE"
echo ""
echo "You can check current cron jobs with: crontab -l" 