#!/bin/bash

# Open backend in new Terminal tab
osascript -e 'tell application "Terminal" to do script "cd \"$(pwd)/modern_dashboard/backend\"; python3 main.py"'

# Open frontend in new Terminal tab
osascript -e 'tell application "Terminal" to do script "cd \"$(pwd)/modern_dashboard/frontend\"; npm install; npm run dev"' 