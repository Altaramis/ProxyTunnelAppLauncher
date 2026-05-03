# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
import os

from .models import AppConfig, ProxyProfile, CommandEntry

CONFIG_FILE = "configs.json"
logger = logging.getLogger(__name__)


def load_config(path: str = CONFIG_FILE) -> AppConfig:
    if not os.path.exists(path):
        return AppConfig()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Impossible de charger %s : %s", path, e)
        return AppConfig()

    try:
        proxies  = [ProxyProfile.from_dict(p) for p in data.get("proxies", [])]
        pr       = data.get("port_range", [20000, 30000])
        commands = [CommandEntry.from_dict(c) for c in data.get("commands", [])]
        cfg = AppConfig(
            proxies=proxies,
            port_range=(int(pr[0]), int(pr[1])),
            commands=commands,
        )
    except Exception as e:
        logger.error("Erreur de désérialisation de %s : %s", path, e)
        return AppConfig()

    _validate_proxy_refs(cfg)
    return cfg


def save_config(cfg: AppConfig, path: str = CONFIG_FILE):
    data = {
        "port_range": list(cfg.port_range),
        "proxies": [p.to_dict() for p in cfg.proxies],
        "commands": [c.to_dict() for c in cfg.commands],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _validate_proxy_refs(cfg: AppConfig):
    proxy_names = {p.name for p in cfg.proxies}
    for cmd in cfg.commands:
        if cmd.proxy and cmd.proxy not in proxy_names:
            logger.warning(
                "Commande '%s' référence le proxy inexistant '%s' — référence effacée",
                cmd.name, cmd.proxy,
            )
            cmd.proxy = ""
