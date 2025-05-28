#!/usr/bin/env python3
"""
Launch script for the Lead Recovery Dashboard

This script provides an easy way to start the Streamlit dashboard
with the correct configuration and dependencies.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = ["streamlit", "pandas", "plotly", "pyperclip"]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    return missing


def install_dependencies(packages):
    """Install missing dependencies."""
    print(f"Installing missing packages: {', '.join(packages)}")
    for package in packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def main():
    print("🚀 Lead Recovery Dashboard Launcher")
    print("=" * 50)

    # Check if we're in the right directory
    current_dir = Path.cwd()
    webui_dir = current_dir / "webui"

    if not webui_dir.exists():
        print("❌ Error: webui directory not found.")
        print("Please run this script from the project root directory.")
        sys.exit(1)

    # Check dependencies
    print("📦 Checking dependencies...")
    missing = check_dependencies()

    if missing:
        print(f"⚠️  Missing packages: {', '.join(missing)}")
        response = input("Install missing packages? (y/n): ")
        if response.lower() == "y":
            try:
                install_dependencies(missing)
                print("✅ Dependencies installed successfully!")
            except Exception as e:
                print(f"❌ Error installing dependencies: {e}")
                sys.exit(1)
        else:
            print("❌ Cannot proceed without required dependencies.")
            sys.exit(1)
    else:
        print("✅ All dependencies are installed!")

    # Check for data
    output_dir = current_dir / "output_run"
    if not output_dir.exists() or not any(output_dir.iterdir()):
        print("⚠️  No analysis data found in output_run directory.")
        print("💡 Run a recipe analysis first to generate data for the dashboard.")
        print("\nYou can:")
        print("1. Use the Recipe Builder: python -m streamlit run webui/app.py")
        print("2. Run a recipe manually: python -m lead_recovery run <recipe_name>")
        print("\nContinuing anyway... (dashboard will show empty state)")

    # Prepare environment
    env = os.environ.copy()

    # Set up paths
    project_root = str(current_dir)
    if project_root not in sys.path:
        env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"

    # Launch dashboard
    dashboard_path = webui_dir / "dashboard.py"

    print("\n🎯 Launching dashboard...")
    print(f"📂 Project root: {current_dir}")
    print("🌐 Dashboard will open in your default browser")
    print("🔗 URL: http://localhost:8501")
    print("\n" + "=" * 50)
    print("💡 Tips:")
    print("  • Use filters in the sidebar to focus on specific leads")
    print("  • Click 'Copy Message' to copy AI-suggested messages")
    print("  • Mark leads as 'Done' to track your progress")
    print("  • Use bulk actions to manage multiple leads at once")
    print("  • Check the Analytics section for insights")
    print("=" * 50)
    print("\n🚀 Starting Streamlit server...")

    try:
        # Run Streamlit
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.address",
            "localhost",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
            "--server.headless",
            "false",
        ]

        subprocess.run(cmd, env=env, cwd=str(current_dir))

    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"\n❌ Error running dashboard: {e}")
        print("💡 Try running manually: streamlit run webui/dashboard.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
