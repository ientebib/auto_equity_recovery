# Dashboard Service Setup

This project includes a `dashboard_service.plist` example for running the Streamlit dashboard on macOS using `launchd`.

1. **Set `PROJECT_DIR`**: Replace `/path/to/lead_recovery_project` in the plist with the absolute path to your local clone. The plist defines a `PROJECT_DIR` environment variable that is used throughout the file.
2. **Update Working Directory and Logs**: Ensure the `WorkingDirectory`, `StandardOutPath`, and `StandardErrorPath` values all point to your project directory.
3. **Load the service**:
   ```bash
   launchctl load ~/Library/LaunchAgents/dashboard_service.plist
   ```
   After editing, reload with `launchctl unload` and `launchctl load`.

If you do not want to track your personalized plist file in version control, it is ignored via `.gitignore`.

