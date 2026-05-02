from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

COL_NAME    = 0
COL_STATUS  = 1
COL_TARGET  = 2
COL_PROXY   = 3
COL_ACTIONS = 4

ROLE = Qt.ItemDataRole.UserRole  # stores command name (str)


class CommandTree(QTreeWidget):
    """Arbre à liste plate de CommandEntry avec réordonnancement par drag-and-drop."""

    commands_reordered = pyqtSignal(list)  # [command_name...] nouvel ordre

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def mousePressEvent(self, event):
        if self.itemAt(event.pos()) is None:
            self.clearSelection()
        super().mousePressEvent(event)

    def dropEvent(self, event):
        dragged = self.currentItem()
        if not dragged:
            event.ignore()
            return

        pos    = event.position().toPoint()
        target = self.itemAt(pos)
        if target is None or target is dragged:
            event.ignore()
            return

        drag_name   = dragged.data(COL_NAME, ROLE)
        target_name = target.data(COL_NAME, ROLE)
        if not isinstance(drag_name, str) or not isinstance(target_name, str):
            event.ignore()
            return
        if drag_name == target_name:
            event.ignore()
            return

        names = [self.topLevelItem(i).data(COL_NAME, ROLE)
                 for i in range(self.topLevelItemCount())]
        drag_idx   = names.index(drag_name)
        target_idx = names.index(target_name)

        rect = self.visualItemRect(target)
        insert_at = target_idx if pos.y() < rect.top() + rect.height() // 2 else target_idx + 1

        new_names = [n for n in names if n != drag_name]
        adj = insert_at - (1 if drag_idx < insert_at else 0)
        new_names.insert(adj, drag_name)

        if new_names != names:
            self.commands_reordered.emit(new_names)

        event.accept()
