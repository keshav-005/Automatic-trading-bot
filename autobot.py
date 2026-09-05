"""
Trading Bot Entry Script
Author: Computer Science Student Project

This script provides a clean 1-line execution entry point.
Running 'python autobot.py' will launch the demo simulation and open the web dashboard.
"""

import sys
from main import run_cli

if __name__ == "__main__":
    # Default to demo simulation if no arguments were passed
    if len(sys.argv) == 1:
        sys.argv.append("--mode")
        sys.argv.append("demo")
    run_cli()