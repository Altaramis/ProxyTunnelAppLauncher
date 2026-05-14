# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict


DEFAULT_VARIABLES: Dict[str, str] = {
    "localhost": "127.0.0.1",
    "ssh_port": "22",
    "rdp_port": "3389",
}


def resolve_text(text: str, global_vars: dict,
                 bind_ip: str = "", bind_port: str = "") -> str:
    """Résout variables globales puis {bind_ip}/{bind_port} dans un texte.
    Jusqu'à 5 passes pour les variables imbriquées."""
    if not text:
        return text
    for _ in range(5):
        prev = text
        for k, v in global_vars.items():
            text = text.replace(f"{{{k}}}", v)
        text = (text
                .replace("{bind_ip}", bind_ip)
                .replace("{bind_port}", bind_port)
                .replace("{local_ip}", bind_ip)    # alias déprécié
                .replace("{local_port}", bind_port)  # alias déprécié
                .replace("{bind_host}", bind_ip))   # alias v1
        if text == prev:
            break
    return text


class PortRangeExhaustedError(Exception):
    pass


@dataclass
class ProxyProfile:
    name: str
    host: str
    port: int
    user: Optional[str] = None
    password: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
        }

    @staticmethod
    def from_dict(d: dict) -> "ProxyProfile":
        return ProxyProfile(
            name=d["name"],
            host=d["host"],
            port=int(d["port"]),
            user=d.get("user"),
            password=d.get("password"),
        )


@dataclass
class CommandEntry:
    name: str
    target_host: str
    target_port: int
    proxy: str
    command: str
    order: int = 0
    console: bool = False
    keep_alive: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "target_host": self.target_host,
            "target_port": self.target_port,
            "proxy": self.proxy,
            "command": self.command,
            "order": self.order,
            "console": self.console,
            "keep_alive": self.keep_alive,
        }

    @staticmethod
    def from_dict(d: dict) -> "CommandEntry":
        return CommandEntry(
            name=d["name"],
            target_host=d["target_host"],
            target_port=int(d["target_port"]),
            proxy=d.get("proxy", ""),
            command=d.get("command", ""),
            order=int(d.get("order", 0)),
            console=bool(d.get("console", False)),
            keep_alive=bool(d.get("keep_alive", False)),
        )


@dataclass
class AppConfig:
    version: int = 2
    proxies: List[ProxyProfile] = field(default_factory=list)
    port_range: tuple = (20000, 30000)
    commands: List[CommandEntry] = field(default_factory=list)


@dataclass
class AppSettings:
    theme: str = "Système"
    log_file_enabled: bool = False
    log_file_path: str = "ProxyTunnelAppLauncher.log"
    log_file_max_mb: int = 5
    log_file_backup_count: int = 3
    log_file_level: str = "INFO"
    language: str = "fr_FR"
    variables: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_VARIABLES))

    def to_dict(self) -> dict:
        return {
            "theme": self.theme,
            "log_file_enabled": self.log_file_enabled,
            "log_file_path": self.log_file_path,
            "log_file_max_mb": self.log_file_max_mb,
            "log_file_backup_count": self.log_file_backup_count,
            "log_file_level": self.log_file_level,
            "language": self.language,
            "variables": self.variables,
        }

    @staticmethod
    def from_dict(d: dict) -> "AppSettings":
        return AppSettings(
            theme=d.get("theme", "Système"),
            log_file_enabled=bool(d.get("log_file_enabled", False)),
            log_file_path=d.get("log_file_path", "ProxyTunnelAppLauncher.log"),
            log_file_max_mb=int(d.get("log_file_max_mb", 5)),
            log_file_backup_count=int(d.get("log_file_backup_count", 3)),
            log_file_level=d.get("log_file_level", "INFO"),
            language=d.get("language", "fr_FR"),
            variables=d.get("variables", dict(DEFAULT_VARIABLES)),
        )
