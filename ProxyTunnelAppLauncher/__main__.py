# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

from PyQt6.QtCore import QTranslator
from PyQt6.QtWidgets import QApplication

from . import __version__
from .settings_io import load_settings
from .ui.main_window import MainWindow


def main():
    if "--version" in sys.argv:
        print(f"ProxyTunnel AppLauncher {__version__}")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    settings = load_settings()
    if settings.language != "fr_FR":
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        qm_path = os.path.join(base, "translations", f"{settings.language}.qm")
        translator = QTranslator(app)
        if translator.load(qm_path):
            app.installTranslator(translator)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
