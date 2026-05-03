# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ...models import CommandEntry, ProxyProfile


def _action_widget(margins=(4, 2, 4, 2)):
    w = QWidget()
    from PyQt6.QtWidgets import QHBoxLayout
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(4)
    return w, lay


class ImportDialog(QDialog):
    """Gestion des conflits lors de l'import de configurations v2."""

    NEW       = "new"
    CONFLICT  = "conflict"
    IDENTICAL = "identical"

    def __init__(self, parent,
                 existing_proxies: Dict[str, ProxyProfile],
                 existing_commands: Dict[str, CommandEntry],
                 import_proxies: List[ProxyProfile],
                 import_commands: List[CommandEntry]):
        super().__init__(parent)
        self._import_proxies  = import_proxies
        self._import_commands = import_commands
        self.setWindowTitle(self.tr("Importer des configurations"))
        self.setMinimumWidth(660)
        self.setMinimumHeight(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # ── Section proxies ────────────────────────────────────────────────
        grp_proxy = QGroupBox(self.tr("Profils proxy"))
        pv = QVBoxLayout(grp_proxy)

        n_pnew = sum(1 for p in import_proxies if p.name not in existing_proxies)
        n_pcnf = sum(1 for p in import_proxies
                     if p.name in existing_proxies and p.to_dict() != existing_proxies[p.name].to_dict())
        n_psame = len(import_proxies) - n_pnew - n_pcnf
        pv.addWidget(QLabel(
            self.tr("{} proxy(s) — {} nouveau(x), {} conflit(s), {} identique(s).").format(
                len(import_proxies), n_pnew, n_pcnf, n_psame)
        ))

        self._proxy_tbl = QTableWidget(len(import_proxies), 3)
        self._proxy_tbl.setHorizontalHeaderLabels(["", self.tr("Nom"), self.tr("Action")])
        self._proxy_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._proxy_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._proxy_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._proxy_tbl.setColumnWidth(0, 32)
        self._proxy_tbl.setColumnWidth(1, 160)
        self._proxy_tbl.verticalHeader().setVisible(False)
        self._proxy_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._proxy_tbl.setShowGrid(False)
        pv.addWidget(self._proxy_tbl)
        layout.addWidget(grp_proxy)

        self._proxy_chks: List[QCheckBox] = []
        self._proxy_combos: List[Optional[QComboBox]] = []
        self._fill_table(self._proxy_tbl, import_proxies,
                         existing_proxies,
                         self._proxy_chks, self._proxy_combos)

        # ── Section commandes ──────────────────────────────────────────────
        grp_cmd = QGroupBox(self.tr("Commandes"))
        cv = QVBoxLayout(grp_cmd)

        n_cnew = sum(1 for c in import_commands if c.name not in existing_commands)
        n_ccnf = sum(1 for c in import_commands
                     if c.name in existing_commands and c.to_dict() != existing_commands[c.name].to_dict())
        n_csame = len(import_commands) - n_cnew - n_ccnf
        cv.addWidget(QLabel(
            self.tr("{} commande(s) — {} nouvelle(s), {} conflit(s), {} identique(s).").format(
                len(import_commands), n_cnew, n_ccnf, n_csame)
        ))

        self._cmd_tbl = QTableWidget(len(import_commands), 3)
        self._cmd_tbl.setHorizontalHeaderLabels(["", self.tr("Nom"), self.tr("Action")])
        self._cmd_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._cmd_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._cmd_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._cmd_tbl.setColumnWidth(0, 32)
        self._cmd_tbl.setColumnWidth(1, 200)
        self._cmd_tbl.verticalHeader().setVisible(False)
        self._cmd_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cmd_tbl.setShowGrid(False)
        cv.addWidget(self._cmd_tbl)
        layout.addWidget(grp_cmd)

        self._cmd_chks: List[QCheckBox] = []
        self._cmd_combos: List[Optional[QComboBox]] = []
        self._fill_table(self._cmd_tbl, import_commands,
                         existing_commands,
                         self._cmd_chks, self._cmd_combos)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Importer la sélection"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _fill_table(self, tbl, items, existing, chks, combos):
        for i, item in enumerate(items):
            key = item.name
            if key not in existing:
                status, status_txt, color = self.NEW, self.tr("Nouveau"), "#27ae60"
            elif item.to_dict() == existing[key].to_dict():
                status, status_txt, color = self.IDENTICAL, self.tr("Identique"), "#7f8c8d"
            else:
                status, status_txt, color = self.CONFLICT, self.tr("Conflit"), "#e67e22"

            chk_w = QWidget()
            chk_lay = QHBoxLayout(chk_w)
            chk_lay.setContentsMargins(6, 0, 6, 0)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(status != self.IDENTICAL)
            chk.setEnabled(status != self.IDENTICAL)
            chk_lay.addWidget(chk)
            tbl.setCellWidget(i, 0, chk_w)
            chks.append(chk)

            tbl.setItem(i, 1, QTableWidgetItem(key))

            if status == self.CONFLICT:
                combo = QComboBox()
                combo.addItem(self.tr("Écraser"), "overwrite")
                combo.addItem(self.tr("Ignorer"),  "skip")
                tbl.setCellWidget(i, 2, combo)
                combos.append(combo)
            else:
                action_txt = self.tr("Sera ajouté") if status == self.NEW else self.tr("Déjà à jour — ignoré")
                lbl = QLabel(f"  {action_txt}")
                lbl.setStyleSheet(f"color:{color};background:transparent;")
                tbl.setCellWidget(i, 2, lbl)
                combos.append(None)

    def get_result(self) -> Tuple[List[Tuple], List[Tuple]]:
        """Retourne (proxy_results, command_results) sous forme [(item, action), ...]."""
        proxy_result = self._collect(self._import_proxies, self._proxy_chks, self._proxy_combos)
        cmd_result   = self._collect(self._import_commands, self._cmd_chks, self._cmd_combos)
        return proxy_result, cmd_result

    @staticmethod
    def _collect(items, chks, combos):
        result = []
        for i, item in enumerate(items):
            if not chks[i].isChecked():
                continue
            combo = combos[i]
            action = combo.currentData() if combo else "add"
            if action != "skip":
                result.append((item, action))
        return result
