#!/usr/bin/env bash
# Refresh ABA Liga dates: scrape the calendar, save CSV, sync filtered teams to macOS Calendar.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 aba.py "$@"
