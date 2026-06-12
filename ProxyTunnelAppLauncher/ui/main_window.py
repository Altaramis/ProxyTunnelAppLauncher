# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import copy
import logging
import logging.handlers
import os
import queue
import sys
import time
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import __version__
from ..config_io import load_config, save_config
from ..models import AppConfig, AppSettings, CommandEntry, PortRangeExhaustedError
from ..settings_io import load_settings, save_settings
from ..tunnel_manager import TunnelManager
from .command_tree import (COL_ACTIONS, COL_NAME, COL_PROXY,
                            COL_STATUS, COL_TARGET, ROLE, CommandTree)
from .dialogs.command_dialog import CommandDialog
from .dialogs.import_dialog import ImportDialog
from .dialogs.proxy_dialog import ProxyManagerDialog
from .dialogs.settings_dialog import SettingsDialog
from .dialogs.variables_dialog import VariablesDialog
from .log_window import LogWindow
from .tree_delegate import TreeDelegate

logger = logging.getLogger(__name__)


def _action_widget(margins=(4, 2, 4, 2), spacing=4):
    w = QWidget()
    from PyQt6.QtWidgets import QHBoxLayout
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return w, lay


def _dark_palette() -> QPalette:
    p = QPalette()
    dark    = QColor(53,  53,  53)
    darker  = QColor(35,  35,  35)
    mid     = QColor(75,  75,  75)
    text    = QColor(220, 220, 220)
    hi      = QColor(42,  130, 218)
    p.setColor(QPalette.ColorRole.Window,         dark)
    p.setColor(QPalette.ColorRole.WindowText,      text)
    p.setColor(QPalette.ColorRole.Base,            darker)
    p.setColor(QPalette.ColorRole.AlternateBase,   dark)
    p.setColor(QPalette.ColorRole.ToolTipBase,     dark)
    p.setColor(QPalette.ColorRole.ToolTipText,     text)
    p.setColor(QPalette.ColorRole.Text,            text)
    p.setColor(QPalette.ColorRole.Button,          mid)
    p.setColor(QPalette.ColorRole.ButtonText,      text)
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 100, 100))
    p.setColor(QPalette.ColorRole.Highlight,       hi)
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Link,            hi)
    p.setColor(QPalette.ColorRole.Midlight,        mid)
    return p


def _light_palette() -> QPalette:
    p = QPalette()
    white = QColor(255, 255, 255)
    bg    = QColor(245, 245, 245)
    text  = QColor(20,  20,  20)
    hi    = QColor(0,   120, 215)
    p.setColor(QPalette.ColorRole.Window,          bg)
    p.setColor(QPalette.ColorRole.WindowText,       text)
    p.setColor(QPalette.ColorRole.Base,             white)
    p.setColor(QPalette.ColorRole.AlternateBase,    QColor(235, 235, 235))
    p.setColor(QPalette.ColorRole.ToolTipBase,      white)
    p.setColor(QPalette.ColorRole.ToolTipText,      text)
    p.setColor(QPalette.ColorRole.Text,             text)
    p.setColor(QPalette.ColorRole.Button,           bg)
    p.setColor(QPalette.ColorRole.ButtonText,       text)
    p.setColor(QPalette.ColorRole.BrightText,       QColor(200, 0, 0))
    p.setColor(QPalette.ColorRole.Highlight,        hi)
    p.setColor(QPalette.ColorRole.HighlightedText,  white)
    p.setColor(QPalette.ColorRole.Link,             hi)
    return p


class MainWindow(QMainWindow):
    CONFIG_FILE   = "configs.json"
    SETTINGS_FILE = "settings.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ProxyTunnel AppLauncher  v{__version__}")
        self.resize(1100, 660)
        if getattr(sys, "frozen", False):
            _logo_dir = os.path.dirname(sys.executable)
        else:
            _logo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _logo_path = os.path.join(_logo_dir, "logo.png")
        if os.path.exists(_logo_path):
            self.setWindowIcon(QIcon(_logo_path))

        self.settings = load_settings(self.SETTINGS_FILE)
        self.app_config = AppConfig()

        self.log_q = queue.Queue()
        self._log_window = LogWindow(self)

        self.tunnel_manager = TunnelManager(
            log_fn=self._log_from_manager,
            port_range=(20000, 30000),
        )
        self.tunnel_manager.session_ended.connect(self._on_session_ended)

        self._file_logger = logging.getLogger("ProxyTunnelAppLauncher")
        self._reconfigure_file_logger()

        self._sort_col: int = -1
        self._sort_dir: int = 1
        self._build_ui()
        self._apply_theme(self.settings.theme)
        self._load_default_config()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(500)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._poll_log_queue)
        self._log_timer.start(200)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        self.tree = CommandTree()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels([
            self.tr("Nom"), self.tr("Statut"), self.tr("Cible"),
            self.tr("Proxy"), self.tr("Actions"),
        ])
        hdr = self.tree.header()
        hdr.setSectionResizeMode(COL_NAME,    QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_STATUS,  QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_TARGET,  QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_PROXY,   QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(COL_ACTIONS, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setColumnWidth(COL_NAME,   170)
        self.tree.setColumnWidth(COL_STATUS, 170)
        self.tree.setColumnWidth(COL_TARGET, 160)
        self.tree.setColumnWidth(COL_PROXY,  140)
        hdr.setSectionsMovable(False)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(False)
        self.tree.commands_reordered.connect(self._on_commands_reordered)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self._delegate = TreeDelegate(self.tree, self.tree)
        self.tree.setItemDelegate(self._delegate)
        layout.addWidget(self.tree)

        # ── Bottom bar ────────────────────────────────────────────────────
        bottom = QWidget()
        bb = QHBoxLayout(bottom)
        bb.setContentsMargins(0, 2, 0, 2)
        bb.setSpacing(6)

        for key, slot, style in [
            ("Ajouter",      self._add_command,       "background:#27ae60;color:white;border-radius:3px;"),
            ("Tout arrêter", self._stop_all,           "background:#c0392b;color:white;border-radius:3px;"),
            ("Exporter",     self._export_config,      ""),
            ("Importer",     self._import_config,      ""),
            ("Variables",    self._open_variables,     ""),
            ("Proxies",      self._open_proxy_manager, ""),
            ("Paramètres",   self._open_settings,      ""),
            ("Journal",      self._open_log_window,    ""),
        ]:
            btn = QPushButton(self.tr(key))
            if style:
                btn.setStyleSheet(style)
            btn.clicked.connect(slot)
            bb.addWidget(btn)
            if key in ("Ajouter", "Tout arrêter"):
                sep = QLabel(" | ")
                sep.setStyleSheet("color:gray;")
                bb.addWidget(sep)

        bb.addStretch()

        theme_btn = QToolButton()
        theme_btn.setText(self.tr("Thème ▾"))
        theme_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        theme_menu = QMenu(theme_btn)
        for t in ("Système", "Clair", "Sombre"):
            action = theme_menu.addAction(self.tr(t))
            action.triggered.connect(lambda _, th=t: self._apply_theme(th))
        theme_btn.setMenu(theme_menu)
        bb.addWidget(theme_btn)
        layout.addWidget(bottom)

        # ── Status bar ────────────────────────────────────────────────────
        self._sb_cmds    = QLabel()
        self._sb_running = QLabel()
        self._sb_log     = QLabel()
        sb = self.statusBar()
        for w in (self._sb_cmds, self._sb_running, self._sb_log):
            sb.addWidget(w)
        self._update_status_bar()

    # ── Theme ─────────────────────────────────────────────────────────────

    def _apply_theme(self, theme: str):
        self.settings.theme = theme
        app = QApplication.instance()
        if theme == "Sombre":
            app.setPalette(_dark_palette())
        elif theme == "Clair":
            app.setPalette(_light_palette())
        else:
            app.setPalette(app.style().standardPalette())
        if hasattr(self, "tree"):
            self._rebuild_tree()

    # ── Tree build ────────────────────────────────────────────────────────

    def _rebuild_tree(self):
        self.tree.clear()
        palette   = QApplication.instance().palette()
        bg_colors = (
            palette.color(QPalette.ColorRole.Base),
            palette.color(QPalette.ColorRole.AlternateBase),
        )
        cmds = list(self.app_config.commands)
        if self._sort_col != -1:
            cmds = sorted(cmds, key=self._sort_key(self._sort_col),
                          reverse=(self._sort_dir == -1))
        for idx, cmd in enumerate(cmds):
            bg = bg_colors[idx % 2]
            item = self._make_command_item(cmd, bg)
            self.tree.addTopLevelItem(item)
            self.tree.setItemWidget(item, COL_STATUS, self._make_status_widget(cmd))
            self.tree.setItemWidget(item, COL_ACTIONS, self._make_action_widget(cmd))

    def _on_header_clicked(self, col: int):
        if col == COL_ACTIONS:
            return
        hdr = self.tree.header()
        if self._sort_col == col:
            if self._sort_dir == 1:
                self._sort_dir = -1
            else:
                self._sort_col = -1
                hdr.setSortIndicatorShown(False)
                self.tree.setDragEnabled(True)
                self.tree.setAcceptDrops(True)
                self._rebuild_tree()
                return
        else:
            self._sort_col = col
            self._sort_dir = 1
        hdr.setSortIndicatorShown(True)
        hdr.setSortIndicator(col, Qt.SortOrder.AscendingOrder if self._sort_dir == 1
                             else Qt.SortOrder.DescendingOrder)
        self.tree.setDragEnabled(False)
        self.tree.setAcceptDrops(False)
        self._rebuild_tree()

    def _sort_key(self, col):
        if col == COL_NAME:
            return lambda c: c.name.lower()
        if col == COL_STATUS:
            return lambda c: 0 if self.tunnel_manager.is_running(c.name) else 1
        if col == COL_TARGET:
            return lambda c: f"{c.target_host}:{c.target_port:05d}"
        if col == COL_PROXY:
            return lambda c: c.proxy.lower()
        return lambda c: 0

    def _make_command_item(self, cmd: CommandEntry, bg: QColor):
        from PyQt6.QtWidgets import QTreeWidgetItem
        item = QTreeWidgetItem()
        item.setData(COL_NAME, ROLE, cmd.name)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
            Qt.ItemFlag.ItemIsDragEnabled
        )
        item.setText(COL_NAME, cmd.name)
        item.setText(COL_TARGET, f"{cmd.target_host}:{cmd.target_port}")

        proxy_name = cmd.proxy or "—"
        item.setText(COL_PROXY, proxy_name)
        if cmd.proxy and not any(p.name == cmd.proxy for p in self.app_config.proxies):
            item.setForeground(COL_PROXY, QBrush(QColor("#e74c3c")))

        resolved = self._resolve_cmd_tooltip(cmd)
        for col in range(self.tree.columnCount()):
            item.setBackground(col, QBrush(bg))
            if resolved != cmd.command:
                item.setToolTip(col, self.tr("Template : {}\nRésolu   : {}").format(
                    cmd.command, resolved))
        return item

    def _resolve_cmd_tooltip(self, cmd: CommandEntry) -> str:
        from ..models import resolve_text
        port = self.tunnel_manager.get_local_port(cmd.name)
        if port:
            return resolve_text(cmd.command, self.settings.variables, "127.0.0.1", str(port))
        return resolve_text(cmd.command, self.settings.variables, "127.0.0.1", "?")

    def _make_status_widget(self, cmd: CommandEntry) -> QWidget:
        w = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        running = self.tunnel_manager.is_running(cmd.name)
        if running:
            port = self.tunnel_manager.get_local_port(cmd.name)
            lbl = QLabel(self.tr("  ● En cours  127.0.0.1:{}").format(port))
            lbl.setStyleSheet("color:#27ae60;font-weight:bold;background:transparent;")
        else:
            lbl = QLabel(self.tr("  ○ Arrêté"))
            lbl.setStyleSheet("color:#7f8c8d;background:transparent;")
        lay.addWidget(lbl)
        return w

    def _make_action_widget(self, cmd: CommandEntry) -> QWidget:
        w, lay = _action_widget()
        running = self.tunnel_manager.is_running(cmd.name)

        launch_label = self.tr("Relancer") if (cmd.keep_alive and running) else self.tr("Lancer")
        btn_launch = QPushButton(launch_label)
        btn_launch.setObjectName("btn_launch")
        btn_launch.setEnabled(True if cmd.keep_alive else not running)
        btn_launch.setStyleSheet(
            "QPushButton { background:#2980b9; color:white; border-radius:3px; }"
            "QPushButton:disabled { background:#95a5a6; color:#ecf0f1; border-radius:3px; }"
        )
        btn_launch.clicked.connect(lambda _, c=cmd: self._launch_command(c))

        btn_kill = QPushButton(self.tr("Tuer"))
        btn_kill.setObjectName("btn_kill")
        btn_kill.setEnabled(running)
        btn_kill.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border-radius:3px; }"
            "QPushButton:disabled { background:#95a5a6; color:#ecf0f1; border-radius:3px; }"
        )
        btn_kill.clicked.connect(lambda _, n=cmd.name: self.tunnel_manager.kill(n))

        btn_edit = QPushButton(self.tr("Modifier"))
        btn_edit.setStyleSheet("background:#5d6d7e;color:white;border-radius:3px;")
        btn_edit.clicked.connect(lambda _, c=cmd: self._edit_command(c))

        for b in (btn_launch, btn_kill, btn_edit):
            lay.addWidget(b)
        return w

    # ── Status refresh ────────────────────────────────────────────────────

    def _update_status_bar(self):
        n_cmds    = len(self.app_config.commands)
        n_running = sum(1 for c in self.app_config.commands
                        if self.tunnel_manager.is_running(c.name))
        self._sb_cmds.setText(self.tr("  Commandes : {}  ").format(n_cmds))
        self._sb_running.setText(self.tr("  Actives : {} / {}  ").format(n_running, n_cmds))
        lw_status = self.tr("Journal ouvert") if self._log_window.isVisible() else ""
        self._sb_log.setText(f"  {lw_status}" if lw_status else "")

    def _refresh_status(self):
        self._update_status_bar()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            name = item.data(COL_NAME, ROLE)
            if not isinstance(name, str):
                continue
            cmd = next((c for c in self.app_config.commands if c.name == name), None)
            if not cmd:
                continue
            running = self.tunnel_manager.is_running(name)
            # Update status widget label
            sw = self.tree.itemWidget(item, COL_STATUS)
            if sw:
                lbl = sw.findChild(QLabel)
                if lbl:
                    if running:
                        port = self.tunnel_manager.get_local_port(name)
                        lbl.setText(self.tr("  ● En cours  127.0.0.1:{}").format(port))
                        lbl.setStyleSheet("color:#27ae60;font-weight:bold;background:transparent;")
                    else:
                        lbl.setText(self.tr("  ○ Arrêté"))
                        lbl.setStyleSheet("color:#7f8c8d;background:transparent;")
            # Update action buttons
            aw = self.tree.itemWidget(item, COL_ACTIONS)
            if aw:
                bl = aw.findChild(QPushButton, "btn_launch")
                bk = aw.findChild(QPushButton, "btn_kill")
                if bl:
                    if cmd.keep_alive:
                        bl.setEnabled(True)
                        bl.setText(self.tr("Relancer") if running else self.tr("Lancer"))
                    else:
                        bl.setEnabled(not running)
                if bk:
                    bk.setEnabled(running)

    def _on_session_ended(self, command_name: str):
        self._refresh_status()

    def _on_item_double_clicked(self, item, column):
        name = item.data(COL_NAME, ROLE)
        if not isinstance(name, str):
            return
        cmd = next((c for c in self.app_config.commands if c.name == name), None)
        if cmd and (cmd.keep_alive or not self.tunnel_manager.is_running(name)):
            self._launch_command(cmd)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        name = item.data(COL_NAME, ROLE)
        if not isinstance(name, str):
            return
        cmd = next((c for c in self.app_config.commands if c.name == name), None)
        if not cmd:
            return

        running = self.tunnel_manager.is_running(name)
        menu = QMenu(self)

        act_launch_label = self.tr("Relancer") if (cmd.keep_alive and running) else self.tr("Lancer")
        act_launch = menu.addAction(act_launch_label)
        act_launch.setEnabled(cmd.keep_alive or not running)
        act_kill = menu.addAction(self.tr("Tuer"))
        act_kill.setEnabled(running)
        menu.addSeparator()
        act_edit = menu.addAction(self.tr("Modifier…"))
        act_dup  = menu.addAction(self.tr("Dupliquer"))
        menu.addSeparator()
        act_del  = menu.addAction(self.tr("Supprimer"))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == act_launch:
            self._launch_command(cmd)
        elif chosen == act_kill:
            self.tunnel_manager.kill(name)
        elif chosen == act_edit:
            self._edit_command(cmd)
        elif chosen == act_dup:
            self._duplicate_command(cmd)
        elif chosen == act_del:
            self._delete_command(cmd)

    # ── Command actions ───────────────────────────────────────────────────

    def _launch_command(self, cmd: CommandEntry):
        proxy = next((p for p in self.app_config.proxies if p.name == cmd.proxy), None)
        if not proxy:
            QMessageBox.warning(
                self, self.tr("Proxy manquant"),
                self.tr("Le profil proxy « {} » est introuvable.\n"
                        "Veuillez configurer un proxy valide pour cette commande."
                        ).format(cmd.proxy or self.tr("(aucun)"))
            )
            return
        try:
            self.tunnel_manager.launch(cmd, proxy)
        except PortRangeExhaustedError as e:
            QMessageBox.critical(self, self.tr("Plage de ports épuisée"), str(e))
        except OSError as e:
            QMessageBox.critical(self, self.tr("Erreur tunnel"), str(e))
        except RuntimeError as e:
            QMessageBox.critical(self, self.tr("Erreur"), str(e))

    def _add_command(self):
        existing_names = [c.name for c in self.app_config.commands]
        dlg = CommandDialog(
            self,
            proxies=self.app_config.proxies,
            global_vars=self.settings.variables,
            existing_names=existing_names,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_command:
            cmd = dlg.result_command
            cmd.order = len(self.app_config.commands)
            self.app_config.commands.append(cmd)
            self._rebuild_tree()

    def _edit_command(self, cmd: CommandEntry):
        existing_names = [c.name for c in self.app_config.commands if c.name != cmd.name]
        dlg = CommandDialog(
            self,
            initial=cmd,
            proxies=self.app_config.proxies,
            global_vars=self.settings.variables,
            existing_names=existing_names,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_command:
            new_cmd = dlg.result_command
            new_cmd.order = cmd.order
            idx = next((i for i, c in enumerate(self.app_config.commands) if c.name == cmd.name), None)
            if idx is not None:
                self.app_config.commands[idx] = new_cmd
            if cmd.name != new_cmd.name:
                self.tunnel_manager.rename_session(cmd.name, new_cmd.name)
            self._rebuild_tree()

    def _duplicate_command(self, cmd: CommandEntry):
        new_cmd = copy.deepcopy(cmd)
        base = cmd.name
        existing = {c.name for c in self.app_config.commands}
        new_name = self.tr("{} (copie)").format(base)
        i = 2
        while new_name in existing:
            new_name = self.tr("{} (copie {})").format(base, i)
            i += 1
        new_cmd.name = new_name
        new_cmd.order = len(self.app_config.commands)
        self.app_config.commands.append(new_cmd)
        self._rebuild_tree()

    def _delete_command(self, cmd: CommandEntry):
        if self.tunnel_manager.is_running(cmd.name):
            self.tunnel_manager.kill(cmd.name)
        if QMessageBox.question(
            self, self.tr("Confirmer"),
            self.tr("Supprimer « {} » ?").format(cmd.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.app_config.commands = [c for c in self.app_config.commands if c.name != cmd.name]
            _renumber(self.app_config.commands)
            self._rebuild_tree()

    def _stop_all(self):
        self.tunnel_manager.stop_all()
        self._rebuild_tree()

    def _on_commands_reordered(self, new_order: list):
        cmd_map = {c.name: c for c in self.app_config.commands}
        self.app_config.commands = [cmd_map[n] for n in new_order if n in cmd_map]
        _renumber(self.app_config.commands)
        self._rebuild_tree()

    # ── Proxy manager ─────────────────────────────────────────────────────

    def _open_proxy_manager(self):
        commands_by_proxy: dict = {}
        for c in self.app_config.commands:
            if c.proxy:
                commands_by_proxy.setdefault(c.proxy, []).append(c.name)
        dlg = ProxyManagerDialog(self, self.app_config.proxies, commands_by_proxy)
        dlg.exec()
        self.app_config.proxies = dlg.get_proxies()
        renames = dlg.get_renames()
        if renames:
            for cmd in self.app_config.commands:
                if cmd.proxy in renames:
                    cmd.proxy = renames[cmd.proxy]
        self._rebuild_tree()

    # ── Settings & variables ──────────────────────────────────────────────

    def _open_variables(self):
        dlg = VariablesDialog(self, self.settings.variables)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings.variables = dlg.get_result()
            self.tunnel_manager.global_vars = self.settings.variables
            save_settings(self.settings, self.SETTINGS_FILE)

    def _open_settings(self):
        dlg = SettingsDialog(self, self.settings, self.app_config.port_range)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_range = dlg.get_port_range()
            self.app_config.port_range = new_range
            self.tunnel_manager.set_port_range(*new_range)
            self._reconfigure_file_logger()
            save_settings(self.settings, self.SETTINGS_FILE)

    def _reconfigure_file_logger(self):
        for h in list(self._file_logger.handlers):
            h.close()
            self._file_logger.removeHandler(h)
        level = getattr(logging, self.settings.log_file_level, logging.INFO)
        self._file_logger.setLevel(level)
        if not self.settings.log_file_enabled:
            return
        try:
            fh = logging.handlers.RotatingFileHandler(
                self.settings.log_file_path,
                maxBytes=self.settings.log_file_max_mb * 1024 * 1024,
                backupCount=self.settings.log_file_backup_count,
                encoding="utf-8",
            )
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self._file_logger.addHandler(fh)
        except Exception as e:
            self._log(f"Impossible d'ouvrir le fichier de log : {e}", level="ERROR")

    # ── Export / Import ───────────────────────────────────────────────────

    def _export_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Exporter les configurations"), "configs_export.json",
            self.tr("JSON (*.json)")
        )
        if not path:
            return
        try:
            save_config(self.app_config, path)
            self._log(f"Exporté vers {path}")
        except Exception as e:
            QMessageBox.critical(self, self.tr("Erreur"), str(e))

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Importer des configurations"), "", self.tr("JSON (*.json)")
        )
        if not path:
            return
        try:
            import_cfg = load_config(path)
        except Exception as e:
            QMessageBox.critical(self, self.tr("Erreur"), str(e))
            return

        if not import_cfg.proxies and not import_cfg.commands:
            QMessageBox.information(self, self.tr("Importer"),
                                    self.tr("Aucune donnée trouvée dans le fichier."))
            return

        existing_proxies = {p.name: p for p in self.app_config.proxies}
        existing_cmds    = {c.name: c for c in self.app_config.commands}

        dlg = ImportDialog(self, existing_proxies, existing_cmds,
                           import_cfg.proxies, import_cfg.commands)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        proxy_results, cmd_results = dlg.get_result()

        for proxy, action in proxy_results:
            if action == "add":
                self.app_config.proxies.append(proxy)
            elif action == "overwrite":
                idx = next((i for i, p in enumerate(self.app_config.proxies)
                            if p.name == proxy.name), None)
                if idx is not None:
                    self.app_config.proxies[idx] = proxy
                else:
                    self.app_config.proxies.append(proxy)

        added = overwritten = 0
        for cmd, action in cmd_results:
            if action == "add":
                cmd.order = len(self.app_config.commands)
                self.app_config.commands.append(cmd)
                added += 1
            elif action == "overwrite":
                was_running = self.tunnel_manager.is_running(cmd.name)
                if was_running:
                    self.tunnel_manager.kill(cmd.name)
                idx = next((i for i, c in enumerate(self.app_config.commands)
                            if c.name == cmd.name), None)
                if idx is not None:
                    cmd.order = self.app_config.commands[idx].order
                    self.app_config.commands[idx] = cmd
                else:
                    cmd.order = len(self.app_config.commands)
                    self.app_config.commands.append(cmd)
                overwritten += 1

        self._rebuild_tree()
        self._log(f"Import terminé — {added} ajouté(s), {overwritten} écrasé(s)")

    # ── Logging ───────────────────────────────────────────────────────────

    def _log_from_manager(self, level: str, message: str):
        ts = time.strftime("%H:%M:%S")
        text = f"{ts} {message}"
        self.log_q.put((level, text))
        getattr(self._file_logger, level.lower(), self._file_logger.info)(message)

    def _log(self, *parts, level="INFO"):
        ts = time.strftime("%H:%M:%S")
        text = f"{ts} " + " ".join(map(str, parts))
        self.log_q.put((level, text))
        getattr(self._file_logger, level.lower(), self._file_logger.info)(" ".join(map(str, parts)))

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_q.get_nowait()
                level, msg = item if isinstance(item, tuple) else ("INFO", item)
                self._log_window.append_entry(level, msg)
        except queue.Empty:
            pass

    def _open_log_window(self):
        self._log_window.show()
        self._log_window.raise_()
        self._log_window.activateWindow()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def _load_default_config(self):
        try:
            self.app_config = load_config(self.CONFIG_FILE)
            self.tunnel_manager.global_vars = self.settings.variables
            self.tunnel_manager.set_port_range(*self.app_config.port_range)
            self._log(f"Configurations chargées depuis {self.CONFIG_FILE}")
        except Exception as e:
            self._log(f"Erreur chargement config: {e}", level="ERROR")
        self._rebuild_tree()

    def closeEvent(self, event):
        self.tunnel_manager.stop_all()
        try:
            save_config(self.app_config, self.CONFIG_FILE)
        except Exception:
            pass
        save_settings(self.settings, self.SETTINGS_FILE)
        event.accept()


def _renumber(commands):
    for i, cmd in enumerate(commands):
        cmd.order = i
