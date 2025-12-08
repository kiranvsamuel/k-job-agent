#!/usr/bin/env python3
"""
Entry point for running the API from the api directory
"""
import os
import sys

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from .app import app

if __name__ == '__main__':
    # Use port 5001 to avoid AirPlay conflict on macOS
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)