from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from ...models import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, parent, settings: AppSettings, port_range: tuple):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._settings = settings
        self._port_range = list(port_range)

        layout = QVBoxLayout(self)

        # ── Journal fichier ────────────────────────────────────────────────
        grp_log = QGroupBox("Journal fichier (log)")
        form_log = QFormLayout(grp_log)

        self.enabled_chk = QCheckBox("Activer le journal fichier")
        self.enabled_chk.setChecked(settings.log_file_enabled)
        self.enabled_chk.toggled.connect(self._update_enabled)
        form_log.addRow("", self.enabled_chk)

        path_row = _hrow()
        self.path_edit = QLineEdit(settings.log_file_path)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_log_file)
        path_row.layout().addWidget(self.path_edit)
        path_row.layout().addWidget(browse_btn)
        form_log.addRow("Fichier", path_row)

        self.max_mb_spin = QSpinBox()
        self.max_mb_spin.setRange(1, 500)
        self.max_mb_spin.setSuffix(" Mo")
        self.max_mb_spin.setValue(settings.log_file_max_mb)
        form_log.addRow("Taille max", self.max_mb_spin)

        self.backup_spin = QSpinBox()
        self.backup_spin.setRange(0, 20)
        self.backup_spin.setSuffix(" fichier(s) de rotation")
        self.backup_spin.setValue(settings.log_file_backup_count)
        form_log.addRow("Rotation", self.backup_spin)

        layout.addWidget(grp_log)

        # ── Plage de ports locaux ──────────────────────────────────────────
        grp_ports = QGroupBox("Plage de ports locaux")
        form_ports = QFormLayout(grp_ports)

        self.port_min_spin = QSpinBox()
        self.port_min_spin.setRange(1024, 65534)
        self.port_min_spin.setValue(port_range[0])
        form_ports.addRow("Port min", self.port_min_spin)

        self.port_max_spin = QSpinBox()
        self.port_max_spin.setRange(1025, 65535)
        self.port_max_spin.setValue(port_range[1])
        form_ports.addRow("Port max", self.port_max_spin)

        info = QLabel("Utilisée pour allouer automatiquement un port local à chaque tunnel.")
        info.setStyleSheet("color:gray;font-style:italic;")
        form_ports.addRow("", info)

        layout.addWidget(grp_ports)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._update_enabled(self.enabled_chk.isChecked())

    def _update_enabled(self, enabled: bool):
        for w in (self.path_edit, self.max_mb_spin, self.backup_spin):
            w.setEnabled(enabled)

    def _browse_log_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Choisir le fichier de log", self.path_edit.text(),
            "Fichiers log (*.log);;Tous les fichiers (*)"
        )
        if path:
            self.path_edit.setText(path)

    def _on_accept(self):
        pmin = self.port_min_spin.value()
        pmax = self.port_max_spin.value()
        if pmin >= pmax:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erreur", "Le port min doit être inférieur au port max.")
            return
        if pmax - pmin < 100:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Avertissement",
                                "La plage de ports est très réduite (< 100 ports). "
                                "Certaines commandes simultanées pourraient échouer.")
        self._settings.log_file_enabled     = self.enabled_chk.isChecked()
        self._settings.log_file_path        = self.path_edit.text().strip() or "ProxyTunnelAppLauncher.log"
        self._settings.log_file_max_mb      = self.max_mb_spin.value()
        self._settings.log_file_backup_count = self.backup_spin.value()
        self._port_range = [pmin, pmax]
        self.accept()

    def get_port_range(self) -> tuple:
        return (self._port_range[0], self._port_range[1])


def _hrow():
    from PyQt6.QtWidgets import QWidget
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    return w
