#!/usr/bin/env python3
"""Lanceur direct — alternative à `python -m ProxyTunnelAppLauncher`."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from ProxyTunnelAppLauncher.__main__ import main

if __name__ == "__main__":
    main()
