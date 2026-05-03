import sys

from PyQt6.QtWidgets import QApplication

from . import __version__
from .ui.main_window import MainWindow


def main():
    if "--version" in sys.argv:
        print(f"ProxyTunnel AppLauncher {__version__}")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
