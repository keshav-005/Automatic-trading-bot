"""
Vercel Serverless Function Entrypoint
Author: Computer Science Student Project

Vercel looks for serverless functions inside the 'api/' directory by default.
This file forwards requests to our Trading Bot Dashboard engine.
"""

import os
import sys

# Ensure repository root is in Python module search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.server import DashboardRequestHandler, wsgi_app

# Vercel entrypoint exports
handler = DashboardRequestHandler
app = wsgi_app
application = wsgi_app
