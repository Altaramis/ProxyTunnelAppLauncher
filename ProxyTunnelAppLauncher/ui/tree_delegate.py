from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QStyledItemDelegate

COL_ACTIONS = 5


class TreeDelegate(QStyledItemDelegate):
    def __init__(self, tree, parent=None):
        super().__init__(parent)
        self._tree = tree

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        painter.save()

        # Ligne horizontale au-dessus de chaque ligne (sauf la première)
        if index.row() > 0 and index.column() == 0:
            pen = QPen(QColor(160, 160, 160), 1, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            y = option.rect.top()
            painter.drawLine(0, y, self._tree.viewport().width(), y)

        # Ligne verticale à gauche de la colonne Actions
        if index.column() == COL_ACTIONS:
            pen = QPen(QColor(160, 160, 160), 1, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            x = option.rect.left()
            painter.drawLine(x, option.rect.top(), x, option.rect.bottom())

        painter.restore()
