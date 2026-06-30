#!/bin/bash
# Generate daily Obsidian journal — silent, no output.
# Just the file write happens; cron engine discards this since deliver=local.

python3 /Users/mrchriswdixon/.hermes/scripts/obsidian-daily-journal.py 2>&1
exit 0
