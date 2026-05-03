# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

LEVEL_COLORS = {
    "DEBUG":   "#7f8c8d",
    "INFO":    None,
    "WARNING": "#e67e22",
    "ERROR":   "#e74c3c",
}


class LogWindow(QWidget):
    """Fenêtre de journal indépendante, persistante pendant toute la session."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(self.tr("Journal — ProxyTunnel AppLauncher"))
        self.resize(900, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton(self.tr("Effacer"))
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumBlockCount(20000)
        self.log_text.setPlaceholderText(self.tr("Aucun événement pour l'instant…"))
        layout.addWidget(self.log_text)

    def append_entry(self, level: str, message: str):
        color_hex = LEVEL_COLORS.get(level)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if color_hex:
            fmt.setForeground(QColor(color_hex))
        else:
            fmt.setForeground(
                QApplication.instance().palette().color(QPalette.ColorRole.Text)
            )
        cursor.setCharFormat(fmt)
        cursor.insertText(message + "\n")
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def _clear(self):
        self.log_text.clear()
