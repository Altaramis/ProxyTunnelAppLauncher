# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


class VariablesDialog(QDialog):
    """Gestion des variables globales utilisables dans tous les champs de saisie."""

    def __init__(self, parent, variables: dict):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Variables globales"))
        self.setMinimumSize(540, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Ces variables peuvent être utilisées dans n'importe quel champ de saisie "
            "sous la forme <b>{nom}</b>. Les variables peuvent aussi en référencer d'autres."
        ))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([self.tr("Nom"), self.tr("Valeur")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 150)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        layout.addWidget(self.table)

        for name, value in sorted(variables.items()):
            self._add_row(name, value)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(self.tr("Ajouter une variable"))
        add_btn.setStyleSheet("background:#27ae60;color:white;border-radius:3px;")
        add_btn.clicked.connect(self._add_empty_row)
        del_btn = QPushButton(self.tr("Supprimer la sélection"))
        del_btn.setStyleSheet("background:#c0392b;color:white;border-radius:3px;")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._result: dict = dict(variables)

    def _add_row(self, name="", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def _add_empty_row(self):
        self._add_row()
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def _delete_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _on_accept(self):
        self._result = {}
        for row in range(self.table.rowCount()):
            ni = self.table.item(row, 0)
            vi = self.table.item(row, 1)
            name  = ni.text().strip() if ni else ""
            value = vi.text() if vi else ""
            if name:
                self._result[name] = value
        self.accept()

    def get_result(self) -> dict:
        return self._result
