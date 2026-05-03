#!/usr/bin/env python3
# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lanceur direct — alternative à `python -m ProxyTunnelAppLauncher`."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from ProxyTunnelAppLauncher.__main__ import main

if __name__ == "__main__":
    main()
