from typing import List, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from ...models import CommandEntry, ProxyProfile, resolve_text


class CommandDialog(QDialog):
    """Créer ou modifier une commande avec tunnel SOCKS5 automatique."""

    def __init__(self, parent=None, initial: Optional[CommandEntry] = None,
                 proxies: Optional[List[ProxyProfile]] = None,
                 global_vars: Optional[dict] = None,
                 existing_names: Optional[List[str]] = None):
        super().__init__(parent)
        self.result_command: Optional[CommandEntry] = None
        self._proxies = proxies or []
        self._global_vars = global_vars or {}
        self._existing_names = existing_names or []
        self._initial_name = initial.name if initial else None
        c = initial

        self.setWindowTitle("Nouvelle commande" if not c else f"Modifier — {c.name}")
        self.setMinimumWidth(520)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # ── Identification ─────────────────────────────────────────────────
        grp_id = QGroupBox("Identification")
        form_id = QFormLayout(grp_id)
        self.name_edit = QLineEdit(c.name if c else "")
        form_id.addRow("Nom (label)", self.name_edit)
        layout.addWidget(grp_id)

        # ── Connexion cible ────────────────────────────────────────────────
        grp_target = QGroupBox("Connexion cible")
        form_target = QFormLayout(grp_target)

        self.target_host_edit = QLineEdit(c.target_host if c else "192.168.0.1")
        form_target.addRow("IP distante", self.target_host_edit)

        self.target_port_spin = QSpinBox()
        self.target_port_spin.setRange(1, 65535)
        self.target_port_spin.setValue(c.target_port if c else 3389)
        form_target.addRow("Port distant", self.target_port_spin)

        self.proxy_combo = QComboBox()
        self.proxy_combo.addItem("— Aucun proxy —", "")
        for proxy in self._proxies:
            self.proxy_combo.addItem(proxy.name, proxy.name)
        if c and c.proxy:
            idx = self.proxy_combo.findData(c.proxy)
            if idx >= 0:
                self.proxy_combo.setCurrentIndex(idx)
            else:
                # proxy introuvable — item rouge
                self.proxy_combo.insertItem(1, f"!! Proxy manquant: {c.proxy}", c.proxy)
                self.proxy_combo.setCurrentIndex(1)
                self.proxy_combo.setItemData(1, "#e74c3c",
                                              Qt.ItemDataRole.ForegroundRole
                                              if hasattr(Qt, 'ItemDataRole') else 33)
        form_target.addRow("Proxy SOCKS5", self.proxy_combo)

        layout.addWidget(grp_target)

        # ── Commande ───────────────────────────────────────────────────────
        grp_cmd = QGroupBox("Commande")
        form_cmd = QFormLayout(grp_cmd)

        exe_row = QWidget()
        exe_lay = QHBoxLayout(exe_row)
        exe_lay.setContentsMargins(0, 0, 0, 0)
        exe_lay.setSpacing(4)
        self.cmd_edit = QLineEdit(c.command if c else "")
        self.cmd_edit.setPlaceholderText("ex : mstsc /v:{bind_ip}:{bind_port}")
        self.cmd_edit.textChanged.connect(self._update_preview)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.setToolTip("Parcourir…")
        browse_btn.clicked.connect(self._browse_executable)
        exe_lay.addWidget(self.cmd_edit)
        exe_lay.addWidget(browse_btn)
        form_cmd.addRow("Template", exe_row)

        # Boutons d'insertion de variables
        var_row = QWidget()
        var_lay = QHBoxLayout(var_row)
        var_lay.setContentsMargins(0, 0, 0, 0)
        var_lay.setSpacing(4)
        var_lay.addWidget(QLabel("Insérer :"))
        for var, tip in (("{bind_ip}", "IP locale du tunnel (127.0.0.1)"),
                         ("{bind_port}", "Port local alloué automatiquement")):
            btn = QPushButton(var)
            btn.setToolTip(tip)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-family:monospace;padding:0 6px;background:#2980b9;color:white;border-radius:2px;")
            btn.clicked.connect(lambda _, v=var: self._insert_var(v))
            var_lay.addWidget(btn)
        if self._global_vars:
            sep = QLabel("  |")
            sep.setStyleSheet("color:gray;")
            var_lay.addWidget(sep)
            for vname in sorted(self._global_vars.keys()):
                raw = self._global_vars[vname]
                resolved = resolve_text(raw, self._global_vars)
                tip = f"= {resolved}" if resolved == raw else f"Template : {raw}\nRésolu   : {resolved}"
                btn = QPushButton(f"{{{vname}}}")
                btn.setToolTip(tip)
                btn.setFixedHeight(22)
                btn.setStyleSheet("font-family:monospace;padding:0 4px;font-weight:bold;font-style:italic;")
                btn.clicked.connect(lambda _, v=f"{{{vname}}}": self._insert_var(v))
                var_lay.addWidget(btn)
        var_lay.addStretch()
        form_cmd.addRow("", var_row)

        # Preview
        self.preview_edit = QLineEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("Aperçu de la commande résolue…")
        self.preview_edit.setStyleSheet("color:gray;")
        form_cmd.addRow("Aperçu", self.preview_edit)

        self.console_chk = QCheckBox("Ouvrir dans une fenêtre console (SSH, telnet…)")
        self.console_chk.setChecked(c.console if c else False)
        form_cmd.addRow("", self.console_chk)

        layout.addWidget(grp_cmd)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._update_preview()

    def _insert_var(self, var: str):
        pos = self.cmd_edit.cursorPosition()
        text = self.cmd_edit.text()
        self.cmd_edit.setText(text[:pos] + var + text[pos:])
        self.cmd_edit.setCursorPosition(pos + len(var))
        self.cmd_edit.setFocus()

    def _update_preview(self):
        resolved = resolve_text(self.cmd_edit.text(), self._global_vars,
                                "127.0.0.1", "20000")
        self.preview_edit.setText(resolved)

    def _browse_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner l'exécutable", "",
            "Exécutables (*.exe *.bat *.cmd);;Tous les fichiers (*)"
        )
        if path:
            current = self.cmd_edit.text().strip()
            if not current:
                self.cmd_edit.setText(f'"{path}" {{local_ip}} {{local_port}}'
                                      if " " in path else f"{path} {{local_ip}} {{local_port}}")
            else:
                pos = self.cmd_edit.cursorPosition()
                text = self.cmd_edit.text()
                insert = f'"{path}"' if " " in path else path
                self.cmd_edit.setText(text[:pos] + insert + text[pos:])

    def _on_accept(self):
        from PyQt6.QtCore import Qt as _Qt
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom ne peut pas être vide.")
            return
        if name != self._initial_name and name in self._existing_names:
            QMessageBox.warning(self, "Erreur",
                                f"Le nom « {name} » est déjà utilisé par une autre commande.")
            return
        target_host = self.target_host_edit.text().strip()
        if not target_host:
            QMessageBox.warning(self, "Erreur", "L'IP distante ne peut pas être vide.")
            return
        cmd = self.cmd_edit.text().strip()
        if not cmd:
            QMessageBox.warning(self, "Erreur", "La commande ne peut pas être vide.")
            return
        proxy = self.proxy_combo.currentData() or ""
        self.result_command = CommandEntry(
            name=name,
            target_host=target_host,
            target_port=self.target_port_spin.value(),
            proxy=proxy,
            command=cmd,
            order=0,
            console=self.console_chk.isChecked(),
        )
        self.accept()


# Import here to avoid circular at module level
try:
    from PyQt6.QtCore import Qt
except ImportError:
    pass
