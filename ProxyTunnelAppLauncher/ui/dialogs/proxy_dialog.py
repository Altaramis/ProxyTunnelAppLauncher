import socket
import threading
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...models import ProxyProfile


class ProxyProfileDialog(QDialog):
    """Créer ou modifier un profil proxy SOCKS5."""

    def __init__(self, parent=None, initial: Optional[ProxyProfile] = None,
                 existing_names: Optional[List[str]] = None):
        super().__init__(parent)
        self.result_proxy: Optional[ProxyProfile] = None
        self._existing_names = existing_names or []
        self._initial_name = initial.name if initial else None

        self.setWindowTitle("Nouveau proxy" if not initial else f"Modifier — {initial.name}")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)

        grp = QGroupBox("Proxy SOCKS5")
        form = QFormLayout(grp)

        self.name_edit = QLineEdit(initial.name if initial else "")
        self.host_edit = QLineEdit(initial.host if initial else "127.0.0.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(initial.port if initial else 1080)
        self.user_edit = QLineEdit(initial.user or "" if initial else "")
        self.pass_edit = QLineEdit(initial.password or "" if initial else "")
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Nom",           self.name_edit)
        form.addRow("Host",          self.host_edit)
        form.addRow("Port",          self.port_spin)
        form.addRow("Utilisateur",   self.user_edit)
        form.addRow("Mot de passe",  self.pass_edit)

        # Bouton test
        test_row = QWidget()
        test_lay = QHBoxLayout(test_row)
        test_lay.setContentsMargins(0, 0, 0, 0)
        self._test_label = QLabel("")
        btn_test = QPushButton("Tester la connexion")
        btn_test.clicked.connect(self._test_connection)
        test_lay.addWidget(btn_test)
        test_lay.addWidget(self._test_label)
        test_lay.addStretch()
        form.addRow("", test_row)

        layout.addWidget(grp)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _test_connection(self):
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        self._test_label.setText("Test en cours…")
        self._test_label.setStyleSheet("color:#e67e22;")

        def probe():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(3)
                    s.connect((host, port))
                result, style = "Accessible ✓", "color:#27ae60;font-weight:bold;"
            except Exception as e:
                result, style = f"Erreur : {e}", "color:#e74c3c;"
            self._test_label.setText(result)
            self._test_label.setStyleSheet(style)

        threading.Thread(target=probe, daemon=True).start()

    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom ne peut pas être vide.")
            return
        if name != self._initial_name and name in self._existing_names:
            QMessageBox.warning(self, "Erreur", f"Le nom « {name} » est déjà utilisé.")
            return
        host = self.host_edit.text().strip()
        if not host:
            QMessageBox.warning(self, "Erreur", "L'hôte ne peut pas être vide.")
            return
        self.result_proxy = ProxyProfile(
            name=name,
            host=host,
            port=self.port_spin.value(),
            user=self.user_edit.text().strip() or None,
            password=self.pass_edit.text().strip() or None,
        )
        self.accept()


class ProxyManagerDialog(QDialog):
    """Gérer la liste des profils proxy."""

    def __init__(self, parent, proxies: List[ProxyProfile],
                 commands_by_proxy: Optional[dict] = None):
        super().__init__(parent)
        self._proxies: List[ProxyProfile] = list(proxies)
        self._commands_by_proxy = commands_by_proxy or {}
        self._renames: dict = {}
        self.setWindowTitle("Profils proxy SOCKS5")
        self.setMinimumSize(560, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom", "Host:Port", "Utilisateur", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 120)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Ajouter un proxy")
        add_btn.setStyleSheet("background:#27ae60;color:white;border-radius:3px;")
        add_btn.clicked.connect(self._add_proxy)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        layout.addWidget(btns)

        self._rebuild_table()

    def _rebuild_table(self):
        self.table.setRowCount(0)
        for proxy in self._proxies:
            self._add_row(proxy)

    def _add_row(self, proxy: ProxyProfile):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(proxy.name))
        self.table.setItem(row, 1, QTableWidgetItem(f"{proxy.host}:{proxy.port}"))
        self.table.setItem(row, 2, QTableWidgetItem(proxy.user or ""))

        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        btn_edit = QPushButton("Modifier")
        btn_edit.setStyleSheet("background:#5d6d7e;color:white;border-radius:3px;")
        btn_edit.clicked.connect(lambda _, p=proxy: self._edit_proxy(p))

        btn_del = QPushButton("Supprimer")
        btn_del.setStyleSheet("background:#c0392b;color:white;border-radius:3px;")
        btn_del.clicked.connect(lambda _, p=proxy: self._delete_proxy(p))

        lay.addWidget(btn_edit)
        lay.addWidget(btn_del)
        self.table.setCellWidget(row, 3, w)

    def _add_proxy(self):
        existing_names = [p.name for p in self._proxies]
        dlg = ProxyProfileDialog(self, existing_names=existing_names)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_proxy:
            self._proxies.append(dlg.result_proxy)
            self._rebuild_table()

    def _edit_proxy(self, proxy: ProxyProfile):
        existing_names = [p.name for p in self._proxies]
        dlg = ProxyProfileDialog(self, initial=proxy, existing_names=existing_names)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_proxy:
            idx = next((i for i, p in enumerate(self._proxies) if p.name == proxy.name), None)
            if idx is not None:
                self._proxies[idx] = dlg.result_proxy
            if proxy.name != dlg.result_proxy.name:
                original = next((k for k, v in self._renames.items() if v == proxy.name), proxy.name)
                self._renames[original] = dlg.result_proxy.name
            self._rebuild_table()

    def get_renames(self) -> dict:
        return dict(self._renames)

    def _delete_proxy(self, proxy: ProxyProfile):
        refs = self._commands_by_proxy.get(proxy.name, [])
        if refs:
            msg = (f"Le proxy « {proxy.name} » est utilisé par "
                   f"{len(refs)} commande(s).\nSupprimer quand même ?")
            if QMessageBox.question(self, "Confirmer", msg,
                                    QMessageBox.StandardButton.Yes |
                                    QMessageBox.StandardButton.No
                                    ) != QMessageBox.StandardButton.Yes:
                return
        self._proxies = [p for p in self._proxies if p.name != proxy.name]
        self._rebuild_table()

    def get_proxies(self) -> List[ProxyProfile]:
        return list(self._proxies)
